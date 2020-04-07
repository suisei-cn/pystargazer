from asyncio import AbstractEventLoop
import asyncio
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from typing import Optional, List, Awaitable, Callable
from .models import Event

T_Life = Callable[[None], Awaitable[None]]
T_Dispatcher = Callable[[Event], Awaitable[None]]


class App:
    def __init__(self):
        # Initialize event loop
        self._loop: AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.set_debug(True)

        # hook containers
        self._startup: List[T_Life] = []
        self._shutdown: List[T_Life] = []
        self._routes: List[Route] = []
        self._dispatchers: List[T_Dispatcher] = []

        # job scheduler
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(event_loop=self._loop)

        # starlette object
        self.starlette: Optional[Starlette] = None

        # Starlette(debug=True, routes=[], on_startup=[_lifespan(_startup)], on_shutdown=[_lifespan(_shutdown)])

    def get_starlette(self) -> Starlette:
        if not self.starlette:
            raise RuntimeError("Starlette object hasn't been initialized.")
        return self.starlette

    async def send_event(self, event: Event):
        for _dispatcher in self._dispatchers:
            # noinspection PyBroadException
            try:
                await _dispatcher(event)
            except Exception:
                traceback.print_exc()

    # Plugin decorators
    def on_startup(self, func: T_Life):
        self._startup.append(func)
        return func

    def on_shutdown(self, func: T_Life):
        self._shutdown.append(func)
        return func

    def route(self, url: str, methods: Optional[List[str]] = None):
        def wrapper(func):
            self._routes.append(Route(url, func, methods=methods))
            return func

        return wrapper

    def ws_route(self, url: str):
        def wrapper(func):
            self._routes.append(WebSocketRoute(url, func))
            return func

        return wrapper

    def scheduled(self, trigger: str, **kwargs):
        def wrapper(func):
            self.scheduler.add_job(func, trigger, **kwargs)
            return func

        return wrapper

    def dispatcher(self, func: T_Dispatcher):
        self._dispatchers.append(func)
        return func


app: App = App()
