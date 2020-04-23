import importlib
import os
from os import path

from uvicorn.main import Config, Server

from .app import app
from .models import KVContainer

debug = os.environ.get("debug") == "true"

app._vtubers = KVContainer(app.credentials.get("vtubers_storage"), "vtubers")
app._configs = KVContainer(app.credentials.get("configs_storage"), "configs")
app._states = KVContainer(app.credentials.get("plugins_storage"), "states")

plugin_dir = path.join(path.dirname(path.abspath(__file__)), "plugins")
plugins_path = [file[:-3] for file in os.listdir(plugin_dir) if file.endswith(".py")]
plugins = {plugin.__name__: plugin for plugin in
           [importlib.import_module(f"pystargazer.plugins.{plugin_path}") for plugin_path in plugins_path]}

app.scheduler.start()
app.init_starlette(debug)

config = Config(app.starlette, host="0.0.0.0", port=8000 if debug else 80, log_level="info", lifespan="on")
server = Server(config)
# noinspection PyProtectedMember
app.loop.run_until_complete(server.serve())
