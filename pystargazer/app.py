import asyncio
import traceback
from asyncio import AbstractEventLoop
from typing import Awaitable, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from .models import KVContainer, Credential, Event, KVPair

T_Life = Callable[[None], Awaitable[None]]
T_Dispatcher = Callable[[Event], Awaitable[None]]


class App:
    def __init__(self):
        # Initialize event loop
        self._loop: AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.set_debug(True)

        # hook containers
        # lifespan
        self._startup: List[T_Life] = []
        self._shutdown: List[T_Life] = []
        self._routes: List[Route] = []
        self._dispatchers: List[T_Dispatcher] = []
        # storage related
        self._on_update: Dict[str, List[Callable[[KVPair, dict, dict, dict], Awaitable[None]]]] = {}
        self._on_create: Dict[str, List[Callable[[KVPair], Awaitable[None]]]] = {}
        self._on_delete: Dict[str, List[Callable[[KVPair], Awaitable[None]]]] = {}

        # job scheduler
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler(event_loop=self._loop)

        # storage
        self.credentials: Credential = Credential("data/tokens.json")
        self._vtubers: Optional[KVContainer] = None
        self._configs: Optional[KVContainer] = None
        self._states: Optional[KVContainer] = None

        # starlette object
        self._starlette: Optional[Starlette] = None

    @property
    def starlette(self) -> Starlette:
        if not self._starlette:
            raise RuntimeError("Starlette object hasn't been initialized.")
        return self._starlette

    @property
    def vtubers(self) -> KVContainer:
        if not self._vtubers:
            raise RuntimeError("Vtubers storage hasn't been initialized.")
        return self._vtubers

    @property
    def configs(self) -> KVContainer:
        if not self._configs:
            raise RuntimeError("Configs storage hasn't been initialized.")
        return self._configs

    @property
    def plugin_state(self) -> KVContainer:
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

    # Storage events
    async def hook_create(self, storage_name: str, obj: KVPair):
        for callback in self._on_create.get(storage_name, []):
            try:
                await callback(obj)
            except Exception:
                traceback.print_exc()

    async def hook_update(self, storage_name: str, obj: KVPair, added: dict, removed: dict, updated: dict):
        for callback in self._on_update.get(storage_name, []):
            try:
                await callback(obj, added, removed, updated)
            except Exception:
                traceback.print_exc()

    async def hook_delete(self, storage_name: str, obj: KVPair):
        for callback in self._on_delete.get(storage_name, []):
            try:
                await callback(obj)
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

    def on_update(self, storage_name: str):
        def wrapper(func):
            if self._on_update.get(storage_name) is None:
                self._on_update[storage_name] = []
            self._on_update[storage_name].append(func)

        return wrapper

    def on_create(self, storage_name: str):
        def wrapper(func):
            if self._on_create.get(storage_name) is None:
                self._on_create[storage_name] = []
            self._on_create[storage_name].append(func)

        return wrapper

    def on_delete(self, storage_name: str):
        def wrapper(func):
            if self._on_delete.get(storage_name) is None:
                self._on_delete[storage_name] = []
            self._on_delete[storage_name].append(func)

        return wrapper


app: App = App()
