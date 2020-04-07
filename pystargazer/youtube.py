import datetime
from asyncio import Queue
from enum import Enum
from functools import partial
from itertools import cycle
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import dateutil.parser
import feedparser
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.base import JobLookupError
from dateutil import tz
from httpx import AsyncClient
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.status import HTTP_404_NOT_FOUND


class Video:
    def __init__(self, video_id: str, title: str, link: str):
        self.video_id: str = video_id
        self.title: str = title
        self.link: str = link
        self.type: Optional[ResourceType] = None
        self.description: str = ""
        self.thumbnail: str = ""
        self.scheduled_start_time: Optional[datetime.datetime] = None
        self.actual_start_time: Optional[datetime.datetime] = None

    def to_json(self):
        return repr(self)

    def __repr__(self):
        return f"<Video {self.video_id} title={self.title} link={self.link} type={self.type} " \
               f"description={self.description} thumbnail={self.thumbnail} " \
               f"scheduled_start_time={self.scheduled_start_time} actual_start_time={self.actual_start_time}>"


class ResourceType(Enum):
    VIDEO = "video"
    BROADCAST = "broadcast"


class EventType(Enum):
    PUBLISH = "publish"
    REMINDER = "reminder"
    SCHEDULE = "schedule"
    LIVE = "live"
    KILL = "kill"


class Event:
    def __init__(self, resource_type: ResourceType, event_type: EventType, channel: str, video: Video):
        self.type = resource_type
        self.event = event_type
        self.channel = channel
        self.video = video
        if self.type == ResourceType.BROADCAST and not video.scheduled_start_time:
            raise ValueError("Missing field(s): scheduled_start_time in video.")

    def to_json(self):
        return repr(self)

    def __repr__(self):
        return f"<Event type={self.type} event={self.event} channel={self.channel} video={self.video}>"


class Youtube:
    def __init__(self, tokens: List[str], callback_url: str, scheduler: BaseScheduler):
        self.token_g = cycle(tokens)
        self.callback_url = callback_url
        self.channel_list: Dict[str, List[Video]] = {}
        self.scheduler = scheduler
        self.http = AsyncClient(timeout=10)

        self.scheduler.add_job(self.tick, "interval", minutes=1, id="ytb_tick")
        self.scheduler.add_job(self.renewal, "interval", hours=8, id="ytb_renewal")
        self.event_queue: Queue[Event] = Queue()

    async def query_video(self, video: Video) -> bool:
        r = await self.http.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "liveStreamingDetails,snippet",
            "fields": "items(liveStreamingDetails,snippet)",
            "key": next(self.token_g),
            "id": video.video_id
        })

        if not (data := r.json()):
            return False

        try:
            item = data['items'][0]
        except IndexError:
            print("youtube data api malformed response", data)
            return False

        print("query result", str(item)[:200])
        print("query result", str(item)[-200:])

        if snippet := item.get("snippet"):
            video.description = f'{snippet.get("description")[:20]} ...'
            video.thumbnail = thumbnails.get("standard", {"url": None}).get("url") \
                if (thumbnails := snippet.get("thumbnails")) else None

        if streaming := item.get("liveStreamingDetails"):
            video.type = ResourceType.BROADCAST
            if scheduled_start_time := streaming.get("scheduledStartTime"):
                video.scheduled_start_time = dateutil.parser.parse(scheduled_start_time).astimezone(tz.tzlocal())
            if actual_start_time := streaming.get("actualStartTime"):
                video.actual_start_time = dateutil.parser.parse(actual_start_time).astimezone(tz.tzlocal())
        else:
            video.type = ResourceType.VIDEO

        return True

    async def _subscribe(self, channel_id: str, unsubscribe: bool = False):
        await self.http.post("https://pubsubhubbub.appspot.com/subscribe", data={
            "hub.callback": urljoin(self.callback_url, f"youtube_callback"),
            "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}",
            "hub.verify": "async",
            "hub.mode": "subscribe" if not unsubscribe else "unsubscribe",
            "hub.lease_seconds": 86400
        })

    async def subscribe(self, channel_id: str):
        if self.channel_list.get(channel_id) is not None:
            raise ValueError("Conflict channel id.")

        self.channel_list[channel_id] = []
        await self._subscribe(channel_id)

    async def unsubscribe(self, channel_id: str, pop: bool = True):
        if self.channel_list.get(channel_id) is None:
            raise ValueError("Not found.")

        for video in self.channel_list[channel_id]:
            try:
                self.scheduler.remove_job(f'reminder_{channel_id}_{video.video_id}')
            except JobLookupError:
                pass

        if pop:
            self.channel_list.pop(channel_id)

        await self._subscribe(channel_id, True)

    async def websub_callback(self, request: Request):
        if request.method == "GET":
            topic = request.query_params["hub.topic"]
            challenge = request.query_params["hub.challenge"]
            mode = request.query_params["hub.mode"]

            channel_id = parse_qs(urlparse(topic).query).get("channel_id")[0]

            accept = (mode == "subscribe" and channel_id in self.channel_list) \
                     or (mode == "unsubscribe" and channel_id not in self.channel_list)

            if not accept:
                print(f"Rejecting {mode}: {channel_id}")
                return Response(None, status_code=HTTP_404_NOT_FOUND)

            print(f"Accepting {mode}: {channel_id}")
            return PlainTextResponse(challenge)

        elif request.method == "POST":
            body = (await request.body()).decode("utf-8")
            print(body)
            if "deleted-entry" in body:
                return Response()
            feed = feedparser.parse(body)
            video_id, video_link = feed.entries[0].yt_videoid, feed.entries[0].link
            video_title = feed.entries[0].title

            channel_id = feed.entries[0].yt_channelid

            video = Video(video_id=video_id, title=video_title, link=video_link)

            print(f"Adding video {video_id}")

            try:
                old_video = \
                    next(_video for _video in self.channel_list[channel_id] if video.video_id == _video.video_id)
                print("Duplicate video id detected. Checking...")
            except StopIteration:
                old_video = None

            if not await self.query_video(video):
                print("Query failure. Ignoring.")
                return Response()

            dup = old_video and all([
                old_video.title == video.title,
                old_video.scheduled_start_time == video.scheduled_start_time
            ])

            if dup:
                print("Duplicate video. Ignoring.")
                return Response()

            if video.type == ResourceType.VIDEO:
                event = Event(resource_type=video.type, event_type=EventType.PUBLISH, channel=channel_id,
                              video=video)
                await self.event_queue.put(event)
            elif video.type == ResourceType.BROADCAST and not video.actual_start_time:
                print("Raising broadcast event")

                if old_video:
                    self.channel_list[channel_id].remove(old_video)

                self.channel_list[channel_id].append(video)  # for actual start event

                event_schedule = Event(resource_type=video.type, event_type=EventType.SCHEDULE,
                                       channel=channel_id, video=video)
                event_reminder = Event(resource_type=video.type, event_type=EventType.REMINDER,
                                       channel=channel_id, video=video)

                # set a reminder
                job_id = f"reminder_{channel_id}_{video.video_id}"
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id=job_id)
                self.scheduler.add_job(partial(self.event_queue.put, event_reminder), trigger="cron", id=job_id,
                                       year=video.scheduled_start_time.year, month=video.scheduled_start_time.month,
                                       day=video.scheduled_start_time.day, hour=video.scheduled_start_time.hour,
                                       minute=video.scheduled_start_time.minute,
                                       second=video.scheduled_start_time.second)

                print("schedule", event_schedule)
                print("reminder", event_reminder)

                # for scheduled
                await self.event_queue.put(event_schedule)

            return Response()

    async def event(self) -> AsyncGenerator[Event, None]:
        while True:
            item = await self.event_queue.get()
            if item.event == EventType.KILL:
                break
            yield item

    async def tick(self):
        remove_list: List[Tuple[str, Video]] = []
        for channel_id, videos in self.channel_list.items():
            for video in videos:
                if not video.scheduled_start_time:
                    remove_list.append((channel_id, video))
                    print("video doesn't have scheduled start time", video)
                elif datetime.datetime.now().replace(tzinfo=tz.tzlocal()) >= video.scheduled_start_time:
                    if not await self.query_video(video):
                        remove_list.append((channel_id, video))
                        print("video query failure. deleting")
                    if video.actual_start_time:
                        # broadcast has started
                        event = Event(resource_type=ResourceType.BROADCAST, event_type=EventType.LIVE,
                                      channel=channel_id, video=video)
                        await self.event_queue.put(event)
                        remove_list.append((channel_id, video))
        for channel_id, video in remove_list:
            self.channel_list[channel_id].remove(video)

    async def renewal(self):
        for channel_id in self.channel_list:
            await self._subscribe(channel_id)

    async def cleanup(self):
        for channel_id in self.channel_list:
            await self.unsubscribe(channel_id, pop=False)
        self.channel_list.clear()
        await self.event_queue.put(Event(resource_type=ResourceType.VIDEO, event_type=EventType.KILL,
                                         channel="", video=Video("", "", "")))
        self.scheduler.remove_job("ytb_tick")
        self.scheduler.remove_job("ytb_renewal")
