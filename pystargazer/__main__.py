import importlib
import pkgutil
import logging
from os import environ, listdir, path

from uvicorn.main import Config, Server

from .app import app
from .models import KVContainer
from .utils import strtobool

debug = strtobool(environ.get("DEBUG"))
access_log = strtobool(environ.get("ACCESS_LOG"), True)
host = environ.get("HOST", "0.0.0.0")
port = int(environ.get("PORT", "80"))
builtin_plugins = strtobool(environ.get("ENABLE_BUILTIN_PLUGINS"), True)
plugin_dir = environ.get("PLUGIN_DIR", None)

app._vtubers = KVContainer(app.credentials.get("vtubers_storage"), "vtubers")
app._configs = KVContainer(app.credentials.get("configs_storage"), "configs")
app._states = KVContainer(app.credentials.get("plugins_storage"), "states")

search_path = [path for path in
               [path.join(path.dirname(path.abspath(__file__)), "plugins") if builtin_plugins else None,
                plugin_dir]
               if path]
app._plugins = {module_name: loader.find_module(module_name).load_module(module_name)
                for loader, module_name, is_pkg in pkgutil.walk_packages(["./my_pkg/plugins"])}

if not debug:
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
app.scheduler.start()
app.init_starlette(debug)

config = Config(app.starlette, host=host, port=port, lifespan="on",
                access_log=access_log, log_level=logging.DEBUG if debug else None)
server = Server(config)
# noinspection PyProtectedMember
app.loop.run_until_complete(server.serve())
