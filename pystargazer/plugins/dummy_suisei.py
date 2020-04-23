import logging

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event


@app.on_startup
async def startup():
    logging.info("Plugin Start")


@app.on_shutdown
async def shutdown():
    logging.info("Plugin Stop")


@app.on_create("vtubers")
async def on_create(obj):
    print("created", obj)


@app.on_delete("vtubers")
async def on_delete(obj):
    print("deleted", obj)


@app.on_update("vtubers")
async def on_update(obj, added, removed, updated):
    print("updated", obj, added, removed, updated)


@app.route("/")
async def hihihi(request: Request):
    return PlainTextResponse("噫hihihi")


@app.scheduled("interval", hours=3)
async def eeehihihi():
    if (my_config := await app.configs.get("dummy_suisei")) is not None:
        if my_config.value.get("disabled") == "true":
            return
    await app.send_event(Event("dummy_suisei", "suisei", {}))
