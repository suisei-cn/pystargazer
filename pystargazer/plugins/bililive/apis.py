import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from inspect import isawaitable
from json import JSONDecodeError
from typing import Optional

import aiohttp
from fastjsonschema.exceptions import JsonSchemaException
# noinspection PyPackageRequirements
from httpcore import TimeoutException
from httpx import AsyncClient, HTTPError, Headers, NetworkError

from .blivedm import BLiveClient
from .schemas import room_info_schema

http = AsyncClient(headers=Headers(
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'})
)


class LiveStatus(Enum):
    DISABLED = 0
    LIVE = 1
    PREPARE = 2


@dataclass
class LiveRoom:
    room_id: int
    title: str
    uid: int
    cover: str
    status: LiveStatus

    @classmethod
    async def from_room_id(cls, room_id: int):
        retry = True
        while retry:
            try:
                retry = False
                r = await http.get(f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}")
                r.raise_for_status()
            except TimeoutException:
                retry = True
            except (HTTPError, NetworkError):
                logging.exception(f"Error occur when fetching live room info.")
                return None

        try:
            # noinspection PyUnboundLocalVariable
            room_info_schema(json_data := r.json())
        except (JSONDecodeError, JsonSchemaException):
            logging.error(f"Malformed Bilibili Live API response: {r.text}")
            return None

        data = json_data['data']
        return cls(room_id, data["title"], data["uid"], data["cover"], LiveStatus(data["live_status"]))


async def get_room_id(uid: int) -> Optional[int]:
    retry = True
    while retry:
        try:
            retry = False
            r = await http.get(f"http://api.live.bilibili.com/bili/living_v2/{uid}")
            r.raise_for_status()
        except TimeoutException:
            retry = True
        except (HTTPError, NetworkError):
            logging.exception(f"Error occur when fetching room id.")
            return None

    try:
        # noinspection PyUnboundLocalVariable
        json_data = r.json()["data"]
    except JSONDecodeError:
        logging.error(f"Malformed Bilibili Live API response: {r.text}")
        return None

    if (url := json_data.get("url")) and url:
        return int(url.split("/")[-1])
    else:
        return None


class LiveClient(BLiveClient):
    def __init__(self, room_id, uid=0,
                 session: aiohttp.ClientSession = None, heartbeat_interval=30, ssl=True, loop=None,
                 on_live=None, on_prepare=None):
        super().__init__(room_id, uid, session, heartbeat_interval, ssl, loop)
        self.on_live = on_live
        self.on_prepare = on_prepare
        self._live = False

    def __repr__(self):
        return f"<LiveClient {self.room_id}>"

    async def init_room(self):
        for i in range(5):
            if await super().init_room():
                logging.info(f"Bili live {self.room_id} init success.")
                return
            logging.info(f"Failed to init room {self.room_id}. Retry {i + 1}/5")
            await asyncio.sleep(1)
        logging.error(f"Failed to init room {self.room_id}. Giving up.")

    async def _on_live(self, command: dict):
        logging.debug(f"Client {self.room_id} received live command.")
        if self._live:
            return
        self._live = True
        if isawaitable(self.on_live):
            await self.on_live(self, command)
        elif callable(self.on_live):
            self.on_live(self, command)

    async def _on_prepare(self, command):
        logging.debug(f"Client {self.room_id} received live command.")
        if not self._live:
            return
        self._live = False
        if isawaitable(self.on_live):
            await self.on_prepare(self, command)
        elif callable(self.on_prepare):
            self.on_prepare(self, command)

    _COMMAND_HANDLERS = BLiveClient._COMMAND_HANDLERS.copy()
    # noinspection PyTypeChecker
    _COMMAND_HANDLERS['LIVE'] = _on_live
    # noinspection PyTypeChecker
    _COMMAND_HANDLERS['PREPARING'] = _on_prepare
