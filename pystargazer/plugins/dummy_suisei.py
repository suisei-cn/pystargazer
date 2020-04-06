from starlette.requests import Request
from starlette.responses import PlainTextResponse
from pystargazer import route, on_startup, on_shutdown, scheduled, app


@on_startup
async def startup():
    print("Start")


@on_shutdown
async def shutdown():
    print("Stop")


@route("/")
async def hihihi(request: Request):
    return PlainTextResponse("噫hihihi")


@scheduled("interval", seconds=3)
async def eeehihihi():
    await app.send_event("eeehihihi")
