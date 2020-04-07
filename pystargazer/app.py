import asyncio
import traceback
from asyncio import AbstractEventLoop
from typing import Awaitable, Callable, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from .models import AbstractKVContainer, Credential, Event

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

        # storage
        self.credentials: Credential = Credential("data/tokens.json")
        self._vtubers: Optional[AbstractKVContainer] = None
        self._configs: Optional[AbstractKVContainer] = None
        self._states: Optional[AbstractKVContainer] = None

        # starlette object
        self._starlette: Optional[Starlette] = None

    @property
    def starlette(self) -> Starlette:
        if not self._starlette:
            raise RuntimeError("Starlette object hasn't been initialized.")
        return self._starlette

    @property
    def vtubers(self) -> AbstractKVContainer:
        if not self._vtubers:
            raise RuntimeError("Vtubers storage hasn't been initialized.")
        return self._vtubers

    @property
    def configs(self) -> AbstractKVContainer:
        if not self._configs:
            raise RuntimeError("Configs storage hasn't been initialized.")
        return self._configs

    @property
    def plugin_state(self) -> AbstractKVContainer:
        if not self._states:
            raise RuntimeError("Plugin state hasn't been initialized.")
        return self._states

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
