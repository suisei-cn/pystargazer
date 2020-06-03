import logging

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event
from pystargazer.utils import get_option as _get_option

get_option = _get_option(app, "dummy_suisei")


@app.on_startup
async def startup():
    logging.info("Plugin Start")


@app.on_shutdown
async def shutdown():
    logging.info("Plugin Stop")


@app.on_create("vtubers")
async def on_create(obj):
    logging.debug("created", obj)


@app.on_delete("vtubers")
async def on_delete(obj):
    logging.debug("deleted", obj)


@app.on_update("vtubers")
async def on_update(obj, added, removed, updated):
    logging.debug("updated", obj, added, removed, updated)


@app.route("/")
async def hihihi(request: Request):
    return PlainTextResponse("噫hihihi")


@app.scheduled("interval", hours=3)
async def eeehihihi():
    if await get_option("enabled", False):
        return
    await app.send_event(Event("dummy_suisei", "suisei", {}))
