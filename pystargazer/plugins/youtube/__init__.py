import asyncio
import datetime
import logging
from functools import partial
from itertools import tee
from typing import Dict, Iterator, List, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import feedparser
from apscheduler.schedulers.base import JobLookupError
from dateutil import tz
# noinspection PyPackageRequirements
from httpcore import TimeoutException  # work around httpx issue #949
from httpx import AsyncClient, NetworkError
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.status import HTTP_404_NOT_FOUND

from pystargazer.app import app
from pystargazer.models import Event
from pystargazer.models import KVPair
from .models import ResourceType, Video, YoutubeEvent, YoutubeEventType

callback_url: str = app.credentials.get("base_url")
channel_list: Dict[str, List[Video]] = {}
read_list: List[Video] = []
scheduler = app.scheduler
http = AsyncClient()


@app.on_startup
async def startup():
    global channel_list
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("youtube"):
        channel_list[vtuber.value["youtube"]] = []

    await load_state()


@app.on_shutdown
async def shutdown():
    await dump_state()


@app.scheduled("interval", minutes=1, misfire_grace_time=10)
async def state_snapshot():
    await dump_state()


# use one-shot schedule instead of on_startup to ensure callback can handle validation in time
@app.scheduled(None, misfire_grace_time=10)
async def init_subscribe():
    await asyncio.sleep(5)

    channel_ids: List[str] = []
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("youtube"):
        channel_ids.append(vtuber.value["youtube"])

    logging.info(f"Subscribing: {channel_ids}")
    await asyncio.gather(*(subscribe(channel_id) for channel_id in channel_ids))
    logging.info("Subscribe finished")


# noinspection PyUnusedLocal
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

    scheduled_start_time_print = video.scheduled_start_time.strftime("%Y-%m-%d %I:%M%p (CST)") \
        if video.scheduled_start_time else None
    actual_start_time_print = video.actual_start_time.strftime("%Y-%m-%d %I:%M%p (CST)") \
        if video.actual_start_time else None

    body = {
        "title": video.title,
        "description": video.description,
        "link": video.link,
        "images": [video.thumbnail] if ytb_event.event != YoutubeEventType.SCHEDULE and video.thumbnail else []
    }
    if scheduled_start_time_print:
        body["scheduled_start_time"] = scheduled_start_time_print
    if actual_start_time_print:
        body["actual_start_time"] = actual_start_time_print

    event = Event(ytb_event.event.value, vtuber.key, body)

    await app.send_event(event)


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
    if channel_id not in channel_list:
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
            logging.info(f"Rejecting {mode}: {channel_id}")
            return Response(None, status_code=HTTP_404_NOT_FOUND)

        logging.info(f"Accepting {mode}: {channel_id}")
        return PlainTextResponse(challenge)

    # noinspection PyMethodMayBeStatic
    async def post(self, request: Request):
        def parse_feed(data: str) -> Tuple[str, str, str, str]:
            feed = feedparser.parse(data)
            entry = feed.entries[0]
            return entry.yt_videoid, entry.link, entry.title, entry.yt_channelid

        body = (await request.body()).decode("utf-8")
        logging.debug(body)
        if "deleted-entry" in body:
            return Response()

        video_id, video_link, video_title, channel_id = parse_feed(body)
        video = Video(video_id)

        logging.info(f"Adding video {video_id}")

        if not await video.fetch():
            logging.warning("Query failure. Ignoring.")
            return Response()

        if video.type == ResourceType.VIDEO:
            # check whether the video is already in the read_list
            try:
                next(_video for _video in read_list if video.video_id == _video.video_id)
                logging.info("Duplicate video. Ignoring.")
                return Response()
            except StopIteration:
                pass
            event = YoutubeEvent(type=video.type, event=YoutubeEventType.PUBLISH, channel=channel_id, video=video)
            await send_youtube_event(event)
            read_list.append(video)
        elif video.type == ResourceType.BROADCAST and not video.actual_start_time:
            if not video.scheduled_start_time:
                logging.warning("Malformed video object: missing scheduled start time.")
                return Response()

            try:
                existing_entry = \
                    next(_video for _video in channel_list[channel_id] if video.video_id == _video.video_id)
                logging.debug("Duplicate video id detected. Checking...")
            except StopIteration:
                existing_entry = None

            dup = existing_entry and all([
                existing_entry.title == video.title,
                existing_entry.scheduled_start_time == video.scheduled_start_time
            ])

            if dup:
                logging.info("Duplicate entry. Ignoring.")
                return Response()

            if existing_entry:
                logging.info("Merging new state into existing entry.")
                existing_entry.merge(video)
                video = existing_entry
            else:
                channel_list[channel_id].append(video)  # for actual start event

            event_schedule = YoutubeEvent(type=video.type, event=YoutubeEventType.SCHEDULE,
                                          channel=channel_id, video=video)
            event_reminder = YoutubeEvent(type=video.type, event=YoutubeEventType.REMINDER,
                                          channel=channel_id, video=video)

            # set a reminder
            job_id = f"reminder_{channel_id}_{video.video_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id=job_id)
            reminder_time = video.scheduled_start_time - datetime.timedelta(minutes=30)
            if reminder_time > datetime.datetime.now().replace(tzinfo=tz.tzlocal()):
                scheduler.add_job(partial(send_youtube_event, event_reminder), trigger="cron", id=job_id,
                                  year=reminder_time.year, month=reminder_time.month,
                                  day=reminder_time.day, hour=reminder_time.hour,
                                  minute=reminder_time.minute,
                                  second=reminder_time.second)

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


@app.scheduled("interval", minutes=1, id="ytb_tick", misfire_grace_time=10)
async def tick():
    def batch_remove(iterable: Iterator[Tuple[str, Video]]):
        for ch_id, video in iterable:
            channel_list[ch_id].remove(video)

    def split(seq, condition):
        l1, l2 = tee((condition(item), item) for item in seq)
        return (i for p, i in l1 if p), (i for p, i in l2 if not p)

    async def check_send(ch_id, video) -> bool:
        """ send message and return is_delete """
        if video.actual_start_time:
            if (now - video.actual_start_time).total_seconds() < 10800:  # broadcast has started
                event = YoutubeEvent(type=ResourceType.BROADCAST, event=YoutubeEventType.LIVE,
                                     channel=ch_id, video=video)
                await send_youtube_event(event)
            return True
        return False

    now = datetime.datetime.now().replace(tzinfo=tz.tzlocal())
    # batch update objects
    video_list: List[Tuple[str, Video]] = [(channel, video)
                                           for channel, videos in channel_list.items()
                                           for video in videos]
    video_map, malformed_map = split(video_list, lambda x: x[1].scheduled_start_time)
    pending_map = list(filter(lambda x: (now - x[1].scheduled_start_time).total_seconds() > -600, video_map))
    # noinspection PyTypeChecker
    fetch_map: Iterator[Tuple[Tuple[str, Video], bool]] = zip(
        pending_map,
        (await asyncio.gather(*(video.fetch() for _, video in pending_map))))
    # remove failed objects
    success_map: List[Tuple[str, Video]]
    error_map: List[Tuple[str, Video]]
    success_map, error_map = [[x[0] for x in iterable] for iterable in split(fetch_map, lambda x: x[1])]
    # noinspection PyTypeChecker
    send_map: Iterator[Tuple[Tuple[str, Video], bool]] = zip(
        success_map,
        (await asyncio.gather(*(check_send(*video_tuple) for video_tuple in success_map)))
    )
    remove_map: Iterator[Tuple[str, Video]] = map(lambda x: x[0], filter(lambda x: x[1], send_map))

    batch_remove(malformed_map)
    batch_remove(error_map)
    batch_remove(remove_map)


@app.scheduled("interval", hours=8, id="ytb_renewal", misfire_grace_time=600)
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


async def load_state():
    global channel_list
    global read_list
    try:
        channel_state = await app.plugin_state.get("youtube_live_state")
    except KeyError:
        logging.warning("Missing live state dict. Ignoring.")
        channel_state = KVPair("youtube_live_state", {})
    try:
        read_state = await app.plugin_state.get("youtube_video_state")
    except KeyError:
        logging.warning("Missing video state dict. Ignoring.")
        read_state = KVPair("youtube_video_state", {"videos": []})

    for channel, videos in channel_state.value.items():
        for _video in videos:
            video = Video.load(_video)
            if await video.fetch() and not video.actual_start_time:
                logging.debug(f"Load saved broadcast: {video}")
                event_reminder = YoutubeEvent(type=video.type, event=YoutubeEventType.REMINDER,
                                              channel=channel, video=video)

                # set a reminder
                job_id = f"reminder_{channel}_{video.video_id}"
                reminder_time = video.scheduled_start_time - datetime.timedelta(minutes=30)
                if reminder_time > datetime.datetime.now().replace(tzinfo=tz.tzlocal()):
                    scheduler.add_job(partial(send_youtube_event, event_reminder), trigger="cron", id=job_id,
                                      year=reminder_time.year, month=reminder_time.month,
                                      day=reminder_time.day, hour=reminder_time.hour,
                                      minute=reminder_time.minute,
                                      second=reminder_time.second)
                channel_list[channel].append(video)

    read_list = [Video.load(video) for video in read_state.value["videos"]]


async def dump_state():
    channel_state = {channel: [video.dump() for video in videos] for channel, videos in channel_list.items()}
    read_state = {"videos": [video.dump() for video in read_list]}

    await app.plugin_state.put(KVPair("youtube_live_state", channel_state))
    await app.plugin_state.put(KVPair("youtube_video_state", read_state))
