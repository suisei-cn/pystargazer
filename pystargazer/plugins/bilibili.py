import asyncio
import json
import logging

from httpx import AsyncClient, HTTPError
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair
from pystargazer.utils import get_option as _get_option


event_map = {
    1: "bili_rt_dyn",
    2: "bili_img_dyn",
    4: "bili_plain_dyn",
    8: "bili_video"
}


class Bilibili:
    def __init__(self):
        self.client = AsyncClient()

    @staticmethod
    def _parse(raw_card):
        dyn_type = raw_card["desc"]["type"]
        dyn_id = raw_card["desc"]["dynamic_id"]
        card = json.loads(raw_card["card"])
        if dyn_type == 2:
            if not (dyn := card.get("item")):
                return dyn_id

            dyn_text = dyn["description"]
            dyn_photos = [entry["img_src"] for entry in dyn_pictures] if (dyn_pictures := dyn.get("pictures")) else []
        elif dyn_type == 1:
            if not (dyn := card.get("item")):
                return dyn_id

            if not (raw_dyn_orig := card.get("origin")):
                return dyn_id

            rt_dyn_raw = {
                "desc": {
                    "type": dyn["orig_type"],
                    "dynamic_id": dyn["orig_dy_id"]
                },
                "card": raw_dyn_orig
            }
            rt_dyn = Bilibili._parse(rt_dyn_raw)

            if not isinstance(rt_dyn, tuple):
                return dyn_id
            dyn_text = f'{dyn["content"]}|RT {rt_dyn[1][0]}'
            dyn_photos = rt_dyn[1][1]
        elif dyn_type == 4:
            if not (dyn := card.get("item")):
                return dyn_id

            dyn_text = dyn["content"]
            dyn_photos = []
        elif dyn_type == 8:
            dyn_text = "\n".join([
                card["title"],
                f'https://www.bilibili.com/video/av{card["aid"]}'
            ])
            dyn_photos = [card["pic"]]
        else:
            return dyn_id

        return dyn_id, (dyn_text, dyn_photos, dyn_type)

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
            if isinstance((rtn := self._parse(raw_card)), tuple):
                dyn_id, dyn_entry = rtn
                if dyn_id == since_id:
                    break
                dyn_list.append(dyn_entry)
            else:
                dyn_id = rtn

            if dyn_id == since_id:
                break

            counter += 1
            if counter == 1:
                rtn_id = dyn_id
            elif counter == 6:
                break


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
            event_map.get(dyn[2], f"bili_{dyn[2]}"),
            name,
            {"text": dyn[0], "images": dyn[1]}
        )
        for name, dyn_set in valid_dyns.items()
        for dyn in dyn_set[1]
        if dyn[0] != "转发动态"
    )
    await asyncio.gather(*(app.send_event(event) for event in events))
