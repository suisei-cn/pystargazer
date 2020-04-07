from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event


@app.on_startup
async def startup():
    print("Start")


@app.on_shutdown
async def shutdown():
    print("Stop")


@app.route("/")
async def hihihi(request: Request):
    return PlainTextResponse("噫hihihi")


@app.scheduled("interval", seconds=3)
async def eeehihihi():
    await app.send_event(Event("eeehihihi"))
