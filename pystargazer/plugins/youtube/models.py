import datetime
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from itertools import cycle
from typing import Iterator, Optional

import dateutil.parser
from dateutil import tz
# noinspection PyPackageRequirements
from httpcore import TimeoutException  # work around httpx issue #949
from httpx import AsyncClient, NetworkError

from pystargazer.app import app

token_g: Iterator[str] = cycle(app.credentials.get("youtube"))
http = AsyncClient(timeout=10)


class ResourceType(Enum):
    VIDEO = "video"
    BROADCAST = "broadcast"


class YoutubeEventType(Enum):
    PUBLISH = "ytb_video"
    REMINDER = "ytb_reminder"
    SCHEDULE = "ytb_sched"
    LIVE = "ytb_live"


@dataclass
class Video:
    video_id: str
    title: str = ""
    link: str = ""
    type: Optional[ResourceType] = None
    description: str = ""
    thumbnail: str = ""
    scheduled_start_time: Optional[datetime.datetime] = None
    actual_start_time: Optional[datetime.datetime] = None

    def __post_init__(self):
        self.link = f"https://www.youtube.com/watch?v={self.video_id}"

    def dump(self):
        state_dict = asdict(self)
        state_dict["type"] = self.type.name
        state_dict["scheduled_start_time"] = datetime.datetime.timestamp(dt) \
            if (dt := self.scheduled_start_time) else None
        state_dict["actual_start_time"] = datetime.datetime.timestamp(dt) if (dt := self.actual_start_time) else None
        return state_dict

    @classmethod
    def load(cls, state_dict):
        _state_dict = state_dict.copy()
        _state_dict["type"] = ResourceType[state_dict["type"]]
        _state_dict["scheduled_start_time"] = datetime.datetime.fromtimestamp(ts).astimezone(tz.tzlocal()) \
            if (ts := state_dict["scheduled_start_time"]) else None
        _state_dict["actual_start_time"] = datetime.datetime.fromtimestamp(ts).astimezone(tz.tzlocal()) \
            if (ts := state_dict["actual_start_time"]) else None
        return cls(**_state_dict)

    def merge(self, obj):
        if not isinstance(obj, Video) or self.video_id != obj.video_id:
            raise ValueError("Object can't be merged.")
        self.__dict__.update(obj.__dict__)

    async def fetch(self) -> bool:
        while True:
            try:
                r = await http.get("https://www.googleapis.com/youtube/v3/videos", params={
                    "part": "liveStreamingDetails,snippet",
                    "fields": "items(liveStreamingDetails,snippet)",
                    "key": next(token_g),
                    "id": self.video_id
                })
                break
            except (NetworkError, TimeoutException):
                pass

        if not (data := r.json()):
            return False

        try:
            item = data['items'][0]
        except IndexError:
            logging.error(f"Youtube data api malformed response: {data}")
            return False

        if snippet := item.get("snippet"):
            self.title = f'{snippet.get("title")}'
            self.description = f'{snippet.get("description")} ...'
            self.thumbnail = thumbnails.get("standard", {"url": None}).get("url") \
                if (thumbnails := snippet.get("thumbnails")) else None

        if streaming := item.get("liveStreamingDetails"):
            self.type = ResourceType.BROADCAST
            if scheduled_start_time := streaming.get("scheduledStartTime"):
                self.scheduled_start_time = dateutil.parser.parse(scheduled_start_time).astimezone(tz.tzlocal())
            if actual_start_time := streaming.get("actualStartTime"):
                self.actual_start_time = dateutil.parser.parse(actual_start_time).astimezone(tz.tzlocal())
        else:
            self.type = ResourceType.VIDEO

        return True


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
