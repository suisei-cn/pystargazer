import importlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from urllib.parse import urlparse

from .utils import compare_dict


@dataclass
class Event:
    __slots__ = ["type", "vtuber", "data"]
    type: str
    vtuber: str
    data: dict

    def to_json(self):
        return {
            "type": self.type,
            "vtuber": self.vtuber,
            "data": self.data,
        }


@dataclass
class KVPair:
    __slots__ = ["key", "value"]
    key: str
    value: Dict[str, Any]

    def __post_init__(self):
        if "key" in self.value:
            raise ValueError("Key field in value.")

    @classmethod
    def load(cls, doc: dict):
        return cls(doc["key"], {k: v for k, v in doc.items() if k not in ["_id", "key"]})

    def dump(self):
        return {"key": self.key, **self.value}


class AbstractKVContainer(ABC):
    @abstractmethod
    async def get(self, key: str) -> KVPair:
        return NotImplemented

    @abstractmethod
    async def has_field(self, field: str) -> AsyncGenerator[KVPair, None]:
        return NotImplemented

    @abstractmethod
    async def put(self, obj: KVPair) -> Tuple[Optional[KVPair], KVPair]:
        return NotImplemented

    @abstractmethod
    async def iter(self) -> AsyncGenerator[KVPair, None]:
        return NotImplemented

    @abstractmethod
    async def delete(self, obj: KVPair) -> KVPair:
        return NotImplemented


class Credential:
    def __init__(self, fn):
        if not os.path.exists(fn):
            with open(fn, mode="w"):
                pass

        self.f = open(fn, mode="r+")

        try:
            self._tokens = json.load(self.f)
        except json.JSONDecodeError:
            self._tokens = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._tokens.get(key, default)

    def put(self, key: str, obj):
        self._tokens[key] = obj
        self._save()

    def __del__(self):
        self.f.close()

    def _save(self):
        self.f.seek(0)
        json.dump(self._tokens, self.f, ensure_ascii=False)
        self.f.truncate()
        self.f.flush()


storages = {}


class KVContainer:
    @staticmethod
    def _get_kv_container(url: str):
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        if storage := storages.get(scheme):
            return storage(url)
        else:
            module = importlib.import_module(f"pystargazer.storages.{scheme}")
            container = module.get_container()
            storages[scheme] = container
            return container(url)

    def __init__(self, url, container_name):
        self.name = container_name
        self.container: AbstractKVContainer = self._get_kv_container(url)

    async def get(self, key: str, default=None) -> KVPair:
        if default is None:
            default = {}
        if (rtn := await self.container.get(key)) is None:
            rtn = KVPair(key, default)
            await self.put(rtn)
        return rtn

    def has_field(self, field: str) -> AsyncGenerator[KVPair, None]:
        # noinspection PyTypeChecker
        return self.container.has_field(field)

    async def put(self, obj: KVPair) -> Tuple[Optional[KVPair], KVPair]:
        old_obj, new_obj = await self.container.put(obj)
        if old_obj:
            added, removed, updated = compare_dict(old_obj.value, new_obj.value)
            await app.app.hook_update(self.name, new_obj, added, removed, updated)
        else:
            await app.app.hook_create(self.name, new_obj)
        return old_obj, new_obj

    def iter(self) -> AsyncGenerator[KVPair, None]:
        # noinspection PyTypeChecker
        return self.container.iter()

    async def delete(self, obj: KVPair) -> KVPair:
        obj = await self.delete(obj)
        await app.app.hook_delete(self.name, obj)
        return obj


import pystargazer.app as app
