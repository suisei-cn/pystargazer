from typing import AsyncGenerator
from urllib.parse import urlparse

import motor.motor_asyncio
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase

from pystargazer.app import app
from pystargazer.models import AbstractKVContainer, KVPair


class KVContainer(AbstractKVContainer):
    async def delete(self, obj: KVPair):
        await self.collections.delete_many({"key": obj.key})

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

    async def put(self, obj: KVPair):
        if old_doc := (await self.collections.find_one({"key": obj.key})):
            await self.collections.replace_one({"_id": old_doc["_id"]}, obj.dump())
        else:
            await self.collections.insert_one(obj.dump())


# noinspection PyUnresolvedReferences,PyProtectedMember
@app.on_startup
async def init_storage():
    for obj in app.__dict__.values():
        if isinstance(obj, KVContainer):
            await obj._init()
