import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict


@dataclass
class Event:
    msg: str


@dataclass
class KVPair:
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
    async def put(self, obj: KVPair):
        return NotImplemented

    @abstractmethod
    async def iter(self) -> AsyncGenerator[KVPair, None]:
        return NotImplemented

    @abstractmethod
    async def delete(self, obj: KVPair):
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

    def get(self, key: str):
        return self._tokens[key]

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
