import asyncio
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.applications import Starlette
from starlette.routing import Route
from typing import Optional, List
from functools import partial, wraps

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ModuleNotFoundError:
    pass

_event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_event_loop)
_event_loop.set_debug(True)

_scheduler = AsyncIOScheduler(event_loop=_event_loop)
_routes = []
_startup = []
_shutdown = []
_dispatchers = []


def _lifespan(func_list: list):
    async def lifespan_func():
        for func in func_list:
            try:
                await func()
            except Exception:
                pass

    return lifespan_func


_app = Starlette(debug=True, routes=_routes, on_startup=[_lifespan(_startup)], on_shutdown=[_lifespan(_shutdown)])


# App instance
class App:
    def __init__(self):
        self.starlette = _app

    @staticmethod
    async def send_event(event):
        for _dispatcher in _dispatchers:
            try:
                await _dispatcher(event)
            except Exception:
                traceback.print_exc()


app = App()


# Plugin decorators
def on_startup(func):
    _startup.append(func)
    return func


def on_shutdown(func):
    _shutdown.append(func)
    return func


def route(url: str, methods: Optional[List[str]] = None):
    def wrapper(func):
        _app.add_route(url, func, methods=methods)
        return func

    return wrapper


def ws_route(url: str):
    def wrapper(func):
        _app.add_websocket_route(url, func)
        return func

    return wrapper


def scheduled(trigger: str, **kwargs):
    def wrapper(func):
        _scheduler.add_job(func, trigger, **kwargs)
        return func

    return wrapper


def dispatcher(func):
    _dispatchers.append(func)
    return func
