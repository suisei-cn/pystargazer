import asyncio
import json
import logging

from httpx import AsyncClient, HTTPError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair
from pystargazer.utils import get_option as _get_option


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

        try:
            r = (await self.client.get(url, params=payload)).json()
        except HTTPError:
            logging.error("Bilibili api fetch error.")
            return since_id, []

        # noinspection PyTypeChecker
        cards = r["data"]["cards"]

        rtn_id = since_id
        dyn_list = []

        counter = 0

        for raw_card in cards:
            msg_type = raw_card["desc"]["type"]
            card = json.loads(raw_card["card"])
            if not (dyn := card.get("item")):
                continue
            if not (dyn_id := dyn.get("id")):
                continue

            counter += 1
            if counter == 1:
                rtn_id = dyn_id
            elif counter == 6:
                break

            if dyn_id == since_id:
                break

            dyn_description = dyn["description"]
            dyn_photos = [entry["img_src"] for entry in dyn_pictures] if (dyn_pictures := dyn.get("pictures")) else []

            dyn_list.append((dyn_description, dyn_photos))

        return rtn_id, dyn_list


bilibili = Bilibili()

get_option = _get_option(app, "bilibili")


@app.route("/help/bilibili", methods=["GET"])
async def youtube_help(request: Request):
    return PlainTextResponse(
        "Field: bilibili\n"
        "Configs[/configs/bilibili]:\n"
        "  disabled"
    )


@app.on_startup
async def bilibili_setup():
    try:
        await app.plugin_state.get("bilibili_since")
    except KeyError:
        await app.plugin_state.put(KVPair("bilibili_since", {}))


@app.scheduled("interval", minutes=1, misfire_grace_time=10)
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
            {"text": dyn[0], "images": dyn[1]}
        )
        for name, dyn_set in valid_dyns.items()
        for dyn in dyn_set[1]
        if dyn[0] != "转发动态"
    )
    await asyncio.gather(*(app.send_event(event) for event in events))
