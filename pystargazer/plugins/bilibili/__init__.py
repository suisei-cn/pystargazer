import asyncio

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair
from pystargazer.utils import get_option as _get_option
from .apis import Bilibili
from .models import Dynamic
from .schemas import card_schema, dyn_schemas

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


@app.scheduled("interval", minutes=5, misfire_grace_time=10)
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

    dyn: Dynamic
    events = (
        Event(
            dyn.type.to_event(),
            name,
            {"text": dyn.text, "images": dyn.photos, "link": dyn.link}
        )
        for name, dyn_set in valid_dyns.items()
        for dyn in dyn_set[1]
    )
    await asyncio.gather(*(app.send_event(event) for event in events))
