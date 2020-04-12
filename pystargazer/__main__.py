import importlib
import os
from os import path

from starlette.applications import Starlette
from uvicorn.main import Config, Server

from .app import app
from .models import KVContainer

plugin_dir = path.join(path.dirname(path.abspath(__file__)), "plugins")
plugins_path = [file[:-3] for file in os.listdir(plugin_dir) if file.endswith(".py")]
plugins = {plugin.__name__: plugin for plugin in
           [importlib.import_module(f"pystargazer.plugins.{plugin_path}") for plugin_path in plugins_path]}

app._vtubers = KVContainer(app.credentials.get("vtubers_storage"), "vtubers")
app._configs = KVContainer(app.credentials.get("configs_storage"), "configs")
app._states = KVContainer(app.credentials.get("plugins_storage"), "states")

'''
credential = Credential("./data/tokens.json")
twitter = Twitter(credential.twitter_token)
youtube = Youtube(credential.youtube_tokens, credential.youtube_callback, sched)
bilibili = Bilibili()
'''

'''
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
'''

app.scheduler.start()
# noinspection PyProtectedMember
debug = os.environ.get("debug") == "true"
app._starlette = Starlette(debug=debug,
                           routes=app._routes, on_startup=app._startup, on_shutdown=app._shutdown)

config = Config(app.starlette, host="0.0.0.0", port=8000 if debug else 80, log_level="info", lifespan="on")
server = Server(config)
# noinspection PyProtectedMember
app._loop.run_until_complete(server.serve())
