import asyncio
import json

from httpx import AsyncClient
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair


class Bilibili:
    def __init__(self):
        self.client = AsyncClient()

    async def fetch(self, user_id: int, since_id: int = 1):
        url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
        payload = {
            "visitor_uid": 0,
            "host_uid": user_id,
            "offset_dynamic_id": 0,
            "need_top": 0
        }

        r = (await self.client.get(url, params=payload)).json()

        try:
            # noinspection PyTypeChecker
            dyn = json.loads(r["data"]["cards"][0]["card"])["item"]
        except json.JSONDecodeError:
            print("Bilibili Dynamic read error")
            return since_id, None

        dyn_id = dyn["id"]
        if dyn_id == since_id:
            return since_id, None

        dyn_description = dyn["description"]
        dyn_photos = [entry["img_src"] for entry in dyn["pictures"]]

        return dyn_id, (dyn_description, dyn_photos)


bilibili = Bilibili()


async def get_option(key: str):
    if (my_config := await app.configs.get("bilibili")) is not None:
        if my_config.value.get(key) == "true":
            return True
    return False


@app.route("/help/bilibili", methods=["GET"])
async def youtube_help(request: Request):
    return PlainTextResponse(
        "Field: bilibili\n"
        "Configs[/configs/bilibili]:\n"
        "  disabled"
    )


@app.on_startup
async def bilibili_setup():
    if await app.plugin_state.get("bilibili_since") is None:
        await app.plugin_state.put(KVPair("bilibili_since", {}))


@app.scheduled("interval", minutes=1)
async def bilibili_task():
    if await get_option("disabled"):
        return

    b_since: KVPair = await app.plugin_state.get("bilibili_since")

    b_valid_ids = []
    b_names = []
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("bilibili"):
        b_names.append(vtuber.key)
        b_valid_ids.append(vtuber.value["bilibili"])

    dyns = await asyncio.gather(*(bilibili.fetch(b_id, b_since.value.get(b_name, 1))
                                  for b_name, b_id in zip(b_names, b_valid_ids)))

    valid_dyns = {name: dyn for name, dyn in zip(b_names, dyns) if dyn[1]}
    since = {name: dyn[0] for name, dyn in valid_dyns.items()}
    b_since.value.update(since)
    await app.plugin_state.put(b_since)

    events = (
        Event(
            "bili_dyn",
            name,
            {"text": dyn[1][0], "images": dyn[1][1]}
        )
        for name, dyn in valid_dyns.items()
        if dyn[1][0] == "分享图片"
    )
    await asyncio.gather(*(app.send_event(event) for event in events))
