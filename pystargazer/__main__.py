import importlib
import logging
import os
from os import path

from uvicorn.main import Config, Server

from .app import app
from .models import KVContainer
from .utils import strtobool

debug = strtobool(os.environ.get("DEBUG"))
access_log = strtobool(os.environ.get("ACCESS_LOG"), True)
host = os.environ.get("HOST", "0.0.0.0")
port = int(os.environ.get("PORT", "80"))

app._vtubers = KVContainer(app.credentials.get("vtubers_storage"), "vtubers")
app._configs = KVContainer(app.credentials.get("configs_storage"), "configs")
app._states = KVContainer(app.credentials.get("plugins_storage"), "states")

plugin_dir = path.join(path.dirname(path.abspath(__file__)), "plugins")
plugins_path = [file[:-3] for file in os.listdir(plugin_dir) if file.endswith(".py")]
plugins = {plugin.__name__: plugin for plugin in
           [importlib.import_module(f"pystargazer.plugins.{plugin_path}") for plugin_path in plugins_path]}

if not debug:
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
app.scheduler.start()
app.init_starlette(debug)

config = Config(app.starlette, host=host, port=port, lifespan="on",
                access_log=access_log, log_level=logging.DEBUG if debug else None)
server = Server(config)
# noinspection PyProtectedMember
app.loop.run_until_complete(server.serve())
