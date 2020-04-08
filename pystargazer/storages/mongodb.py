from typing import AsyncGenerator, Optional, Tuple
from urllib.parse import urlparse

import motor.motor_asyncio
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase

from pystargazer.app import app
from pystargazer.models import AbstractKVContainer, KVPair


class MongoKVContainer(AbstractKVContainer):
    async def delete(self, obj: KVPair) -> KVPair:
        # TODO inconsistent behavior: won't return pop object like FileKVContainer
        await self.collections.delete_one({"key": obj.key})
        return obj

    async def iter(self) -> AsyncGenerator[KVPair, None]:
        async for doc in self.collections.find():
            yield KVPair.load(doc)

    def __init__(self, url: str):
        super().__init__()
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        db, collection = parsed_url.path[1:].split("/")

        self.client: AgnosticClient = motor.motor_asyncio.AsyncIOMotorClient(host)
        self.db: AgnosticDatabase = self.client[db]
        self.collections: AgnosticCollection = self.db[collection]

    async def _init(self):
        await self.collections.create_index("key", unique=True)

    async def get(self, key: str) -> KVPair:
        doc: dict = await self.collections.find_one({"key": key})
        return KVPair.load(doc) if doc else None

    async def has_field(self, field: str) -> AsyncGenerator[KVPair, None]:
        async for doc in self.collections.find({field: {"$exists": True}}):
            yield KVPair.load(doc)

    async def put(self, obj: KVPair) -> Tuple[Optional[KVPair], KVPair]:
        if old_doc := (await self.collections.find_one({"key": obj.key})):
            await self.collections.replace_one({"_id": old_doc["_id"]}, obj.dump())
            return KVPair.load(old_doc), obj
        else:
            await self.collections.insert_one(obj.dump())
            return None, obj


# noinspection PyUnresolvedReferences,PyProtectedMember
@app.on_startup
async def init_storage():
    for obj in app.__dict__.values():
        if isinstance(obj, KVContainer):
            await obj._init()


def get_container():
    return MongoKVContainer
