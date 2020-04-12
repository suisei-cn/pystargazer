import asyncio
import datetime
from dataclasses import dataclass
from enum import Enum
from functools import partial
from itertools import cycle
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import dateutil.parser
import feedparser
from apscheduler.schedulers.base import JobLookupError
from dateutil import tz
from httpx import AsyncClient, NetworkError, TimeoutException
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.status import HTTP_404_NOT_FOUND

from pystargazer.app import app
from pystargazer.models import Event
from pystargazer.models import KVPair


class ResourceType(Enum):
    VIDEO = "video"
    BROADCAST = "broadcast"


class YoutubeEventType(Enum):
    PUBLISH = "publish"
    REMINDER = "reminder"
    SCHEDULE = "schedule"
    LIVE = "live"


@dataclass
class Video:
    video_id: str
    title: str
    link: str
    type: Optional[ResourceType] = None
    description: str = ""
    thumbnail: str = ""
    scheduled_start_time: Optional[datetime.datetime] = None
    actual_start_time: Optional[datetime.datetime] = None


@dataclass
class YoutubeEvent:
    __slots__ = ["type", "event", "channel", "video"]
    type: ResourceType
    event: YoutubeEventType
    channel: str
    video: Video

    def __post_init__(self):
        if self.type == ResourceType.BROADCAST and not self.video.scheduled_start_time:
            raise ValueError("Missing field(s): scheduled_start_time in video.")


token_g: Iterator[str] = cycle(app.credentials.get("youtube"))
callback_url: str = app.credentials.get("base_url")
channel_list: Dict[str, List[Video]] = {}
read_list: List[Video] = []
scheduler = app.scheduler
http = AsyncClient()


async def get_option(key: str):
    if (my_config := await app.configs.get("youtube")) is not None:
        if my_config.value.get(key) == "true":
            return True
    return False


# use one-shot schedule instead of on_startup to ensure callback can handle validation in time
@app.scheduled(None)
async def init_subscribe():
    channel_ids: List[str] = []
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("youtube"):
        channel_ids.append(vtuber.value["youtube"])

    print("channel_ids:", channel_ids)
    print("start to subscribe")
    await asyncio.gather(*(subscribe(channel_id) for channel_id in channel_ids))
    print("subscribe finished")


@app.route("/help/youtube", methods=["GET"])
async def youtube_help(request: Request):
    return PlainTextResponse(
        "Field: youtube\n"
        "Configs[/configs/youtube]:\n"
        "  video_disabled live_disabled reminder_disabled schedule_disabled"
    )


async def get_vtuber(channel_id: str) -> KVPair:
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("youtube"):
        if vtuber.value["youtube"] == channel_id:
            return vtuber


async def send_youtube_event(ytb_event: YoutubeEvent):
    # noinspection PyTypeChecker
    vtuber = await get_vtuber(ytb_event.channel)
    video = ytb_event.video

    event: Optional[Event] = None
    if ytb_event.type == ResourceType.VIDEO and not await get_option("video_disabled"):
        event = Event("youtube_video", vtuber.key, {
            "title": video.title,
            "description": video.description,
            "images": [video.thumbnail],
            "link": video.link
        })
    elif ytb_event.type == ResourceType.BROADCAST:
        scheduled_start_time_print = video.scheduled_start_time.strftime("%Y-%m-%d %I:%M%p (CST)")
        if ytb_event.event == YoutubeEventType.LIVE and not await get_option("live_disabled"):
            actual_start_time_print = video.actual_start_time.strftime("%Y-%m-%d %I:%M%p (CST)")
            event = Event("youtube_broadcast_live", vtuber.key, {
                "title": video.title,
                "description": video.description,
                "link": video.link,
                "scheduled_start_time": scheduled_start_time_print,
                "actual_start_time": actual_start_time_print
            })
        elif ytb_event.event == YoutubeEventType.REMINDER and not await get_option("reminder_disabled"):
            event = Event("youtube_broadcast_reminder", vtuber.key, {
                "title": video.title,
                "description": video.description,
                "link": video.link,
                "scheduled_start_time": scheduled_start_time_print,
            })
        elif ytb_event.event == YoutubeEventType.SCHEDULE and not await get_option("schedule_disabled"):
            event = Event("youtube_broadcast_schedule", vtuber.key, {
                "title": video.title,
                "description": video.description,
                "link": video.link,
                "scheduled_start_time": scheduled_start_time_print,
            })
    if event:
        await app.send_event(event)


async def query_video(video: Video) -> bool:
    while True:
        try:
            r = await http.get("https://www.googleapis.com/youtube/v3/videos", params={
                "part": "liveStreamingDetails,snippet",
                "fields": "items(liveStreamingDetails,snippet)",
                "key": next(token_g),
                "id": video.video_id
            })
            break
        except (NetworkError, TimeoutException):
            pass

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
        video.description = f'{snippet.get("description")} ...'
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


async def _subscribe(channel_id: str, reverse: bool = False):
    while True:
        try:
            await http.post("https://pubsubhubbub.appspot.com/subscribe", data={
                "hub.callback": urljoin(callback_url, f"youtube_callback"),
                "hub.topic": f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}",
                "hub.verify": "async",
                "hub.mode": "subscribe" if not reverse else "unsubscribe",
                "hub.lease_seconds": 86400
            })
            break
        except (NetworkError, TimeoutException):
            pass


async def subscribe(channel_id: str):
    if channel_list.get(channel_id) is not None:
        raise ValueError("Conflict channel id.")

    channel_list[channel_id] = []
    await _subscribe(channel_id)


async def unsubscribe(channel_id: str, pop: bool = True):
    if channel_list.get(channel_id) is None:
        raise ValueError("Not found.")

    for video in channel_list[channel_id]:
        try:
            scheduler.remove_job(f'reminder_{channel_id}_{video.video_id}')
        except JobLookupError:
            pass

    if pop:
        channel_list.pop(channel_id)

    await _subscribe(channel_id, True)


@app.route("/youtube_callback", methods=["GET", "POST"])
class WebsubEndpoint(HTTPEndpoint):
    # noinspection PyMethodMayBeStatic
    async def get(self, request: Request):
        topic = request.query_params["hub.topic"]
        challenge = request.query_params["hub.challenge"]
        mode = request.query_params["hub.mode"]

        channel_id = parse_qs(urlparse(topic).query).get("channel_id")[0]

        accept = (mode == "subscribe" and channel_id in channel_list) or (
                mode == "unsubscribe" and channel_id not in channel_list)

        if not accept:
            print(f"Rejecting {mode}: {channel_id}")
            return Response(None, status_code=HTTP_404_NOT_FOUND)

        print(f"Accepting {mode}: {channel_id}")
        return PlainTextResponse(challenge)

    # noinspection PyMethodMayBeStatic
    async def post(self, request: Request):
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
                next(_video for _video in channel_list[channel_id] if video.video_id == _video.video_id)
            print("Duplicate video id detected. Checking...")
        except StopIteration:
            old_video = None

        if not await query_video(video):
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
            try:
                old_video = next(_video for _video in read_list if video.video_id == _video.video_id)
            except StopAsyncIteration:
                old_video = None
            if not old_video:
                event = YoutubeEvent(type=video.type, event=YoutubeEventType.PUBLISH, channel=channel_id,
                                     video=video)
                await send_youtube_event(event)
                read_list.append(video)
        elif video.type == ResourceType.BROADCAST and not video.actual_start_time:
            print("Raising broadcast event")

            if old_video:
                channel_list[channel_id].remove(old_video)

            channel_list[channel_id].append(video)  # for actual start event

            event_schedule = YoutubeEvent(type=video.type, event=YoutubeEventType.SCHEDULE,
                                          channel=channel_id, video=video)
            event_reminder = YoutubeEvent(type=video.type, event=YoutubeEventType.REMINDER,
                                          channel=channel_id, video=video)

            # set a reminder
            job_id = f"reminder_{channel_id}_{video.video_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id=job_id)
            scheduler.add_job(partial(send_youtube_event, event_reminder), trigger="cron", id=job_id,
                              year=video.scheduled_start_time.year, month=video.scheduled_start_time.month,
                              day=video.scheduled_start_time.day, hour=video.scheduled_start_time.hour,
                              minute=video.scheduled_start_time.minute,
                              second=video.scheduled_start_time.second)

            print("schedule", event_schedule)
            print("reminder", event_reminder)

            # for scheduled
            await send_youtube_event(event_schedule)

        return Response()


# noinspection PyUnusedLocal
@app.on_update("vtubers")
async def on_update(obj: KVPair, added: dict, removed: dict, updated: dict):
    if "youtube" in added:
        await subscribe(added["youtube"])
    elif "youtube" in removed:
        await unsubscribe(removed["youtube"])
    elif "youtube" in updated:
        old_id, new_id = updated["youtube"]
        await unsubscribe(old_id)
        await subscribe(new_id)


@app.on_delete("vtubers")
async def on_delete(obj: KVPair):
    if yid := obj.value.get("youtube"):
        await unsubscribe(yid)


@app.scheduled("interval", minutes=1, id="ytb_tick")
async def tick():
    remove_list: List[Tuple[str, Video]] = []
    for channel_id, videos in channel_list.items():
        for video in videos:
            if not video.scheduled_start_time:
                remove_list.append((channel_id, video))
                print("video doesn't have scheduled start time", video)
            elif datetime.datetime.now().replace(tzinfo=tz.tzlocal()) >= video.scheduled_start_time:
                if not await query_video(video):
                    remove_list.append((channel_id, video))
                    print("video query failure. deleting")
                if video.actual_start_time:
                    # broadcast has started
                    event = YoutubeEvent(type=ResourceType.BROADCAST, event=YoutubeEventType.LIVE,
                                         channel=channel_id, video=video)
                    await send_youtube_event(event)
                    remove_list.append((channel_id, video))
    for channel_id, video in remove_list:
        channel_list[channel_id].remove(video)


@app.scheduled("interval", hours=8, id="ytb_renewal")
async def renewal():
    for channel_id in channel_list:
        await _subscribe(channel_id)


# @app.on_shutdown
async def cleanup():
    for channel_id in channel_list:
        await unsubscribe(channel_id, pop=False)
    channel_list.clear()
    scheduler.remove_job("ytb_tick")
    scheduler.remove_job("ytb_renewal")
