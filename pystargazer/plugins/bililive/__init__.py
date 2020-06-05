import asyncio
from typing import Dict

from httpx import AsyncClient

from pystargazer.app import app
from pystargazer.models import Event
from pystargazer.models import KVPair
from .apis import LiveClient, LiveRoom, LiveStatus, get_room_id

http = AsyncClient()
map_uid_client: Dict[int, LiveClient] = {}


async def get_vtuber_by_uid(uid: int) -> KVPair:
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("bilibili"):
        if int(vtuber.value["bilibili"]) == uid:
            return vtuber


@app.scheduled(None, misfire_grace_time=10)
async def init_ws():
    await asyncio.sleep(5)

    bili_uids = []
    async for vtuber in app.vtubers.has_field("bilibili"):
        bili_uids.append(int(vtuber.value["bilibili"]))

    global map_uid_client
    bili_roomids = await asyncio.gather(*(get_room_id(uid) for uid in bili_uids))
    map_uid_client = {entry[0]: LiveClient(entry[1], on_live=on_live) for entry in list(zip(bili_uids, bili_roomids)) if
                      entry[1]}
    await asyncio.gather(*(client.init_room() for client in map_uid_client.values()))
    for client in map_uid_client.values():
        client.start()


@app.on_shutdown
async def close_ws():
    async def stop_client(client: LiveClient):
        try:
            await client.stop()
        except RuntimeError:
            pass

    await asyncio.gather(*(stop_client(client) for client in map_uid_client.values()))


@app.on_update("vtubers")
async def on_update(obj: KVPair, added: dict, removed: dict, updated: dict):
    if "bilibili" in added:
        uid = int(added["bilibili"])
        if uid in map_uid_client.keys():
            return
        roomid = await get_room_id(uid)
        if not roomid:
            return
        map_uid_client[uid] = (client := LiveClient(roomid, on_live=on_live))
        await client.init_room()
        client.start()
    elif "bilibili" in removed:
        uid = removed["youtube"]
        if uid not in map_uid_client.keys():
            return
        await map_uid_client[uid].close()
        map_uid_client.pop(uid)
    elif "bilibili" in updated:
        old_uid, new_uid = updated["youtube"]
        if old_uid in map_uid_client.keys():
            await map_uid_client[old_uid].close()
            map_uid_client.pop(old_uid)
        if new_uid not in map_uid_client.keys():
            roomid = await get_room_id(new_uid)
            if roomid:
                map_uid_client[new_uid] = (client := LiveClient(roomid, on_live=on_live))
                await client.init_room()
                client.start()


@app.on_create("vtubers")
async def on_delete(obj: KVPair):
    if (uid := obj.value.get("bilibili")) and uid in map_uid_client:
        await map_uid_client[uid].close()
        map_uid_client.pop(uid)


async def on_live(client: LiveClient, command: dict):
    vtuber = await get_vtuber_by_uid(client.room_owner_uid)
    live_room = await LiveRoom.from_room_id(client.room_id)
    body = {
        "title": live_room.title,
        "link": f"https://live.bilibili.com/{client.room_id}",
        "images": [live_room.cover]
    }
    event = Event("bili_live", vtuber.key, body)
    await app.send_event(event)
