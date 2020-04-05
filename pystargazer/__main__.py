import asyncio
from functools import partial

import uvloop
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.applications import Starlette
from starlette.routing import Mount, Route, WebSocketRoute
from uvicorn.main import Config, Server

from .bilibili import Bilibili
from .endpoints import EventEndPoint, on_create, on_delete, on_delete_key, on_iter, on_put_key, on_query, on_query_key
from .state import FileDict
from .tasks import bilibili_task, on_ping, twitter_task, youtube_task
from .tokens import Credential
from .twitter import Twitter
from .youtube import Youtube

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)
event_loop.set_debug(True)

sched = AsyncIOScheduler(event_loop=event_loop)

credential = Credential("./data/tokens.json")
twitter = Twitter(credential.twitter_token)
youtube = Youtube(credential.youtube_tokens, credential.youtube_callback, sched)
bilibili = Bilibili()

routes = [
    WebSocketRoute("/event", EventEndPoint),
    Mount('/vtubers', routes=[
        Route("/", on_iter, methods=["GET"]),
        Route("/", on_create, methods=["POST"]),
        Route("/{vtb_name}", on_query, methods=["GET"]),
        Route("/{vtb_name}", on_delete, methods=["DELETE"]),
        Route("/{vtb_name}/{key}", on_query_key, methods=["GET"]),
        Route("/{vtb_name}/{key}", on_put_key, methods=["PUT"]),
        Route("/{vtb_name}/{key}", on_delete_key, methods=["DELETE"]),
    ]),
    Route("/ping", on_ping, methods=["POST"])
]


async def shutdown():
    # await app.state.youtube.cleanup()
    pass


app = Starlette(debug=True, routes=routes, on_shutdown=[shutdown])

app.state.ws_clients = []
app.state.vtubers = FileDict("./data/vtubers.json")
app.state.twitter_since = FileDict("./data/twitter_since.json")
app.state.bilibili_since = FileDict("./data/bilibili_since.json")
app.state.base_url = credential.youtube_callback

app.state.twitter = twitter
app.state.youtube = youtube
app.state.bilibili = bilibili

sched.add_job(partial(twitter_task, app), 'interval', minutes=1)
sched.add_job(partial(bilibili_task, app), 'interval', minutes=1)
sched.add_job(partial(youtube_task, app))
sched.start()

config = Config(app, host="0.0.0.0", port=80, log_level="info", lifespan="on")
server = Server(config)
event_loop.run_until_complete(server.serve())
