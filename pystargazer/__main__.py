import pkgutil
import logging
from os import environ, path

from uvicorn.main import Config, Server

from .app import app
from .models import KVContainer
from .utils import strtobool

debug = strtobool(environ.get("DEBUG"))
access_log = strtobool(environ.get("ACCESS_LOG"), True)
host = environ.get("HOST", "0.0.0.0")
port = int(environ.get("PORT", "80"))
builtin_plugins = strtobool(environ.get("ENABLE_BUILTIN_PLUGINS"), True)
plugin_blacklist = [plugin.strip() for plugin in environ.get("PLUGIN_BLACKLIST", "").split(",")]
plugin_dir = environ.get("PLUGIN_DIR", None)
telemetry = environ.get("TELEMETRY", "")
telemetry_release = environ.get("TELEMETRY_RELEASE", None)

if telemetry:
    import sentry_sdk
    sentry_sdk.init(telemetry, release=telemetry_release)

if not debug:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

app._vtubers = KVContainer(app.credentials.get("vtubers_storage"), "vtubers")
app._configs = KVContainer(app.credentials.get("configs_storage"), "configs")
app._states = KVContainer(app.credentials.get("plugins_storage"), "states")

search_path = [path for path in
               [path.join(path.dirname(path.abspath(__file__)), "plugins") if builtin_plugins else None,
                plugin_dir]
               if path]
app._plugins = {module_name: loader.find_module(module_name).load_module(module_name)
                for loader, module_name, is_pkg in pkgutil.iter_modules(search_path)
                if module_name not in plugin_blacklist}
logging.info(f"Loaded plugins: {list(app.plugins.keys())}")

if not debug:
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
app.scheduler.start()
app.init_starlette(debug)

config = Config(app.starlette, host=host, port=port, lifespan="on",
                access_log=access_log, log_level=logging.DEBUG if debug else None)
server = Server(config)
# noinspection PyProtectedMember
app.loop.run_until_complete(server.serve())
