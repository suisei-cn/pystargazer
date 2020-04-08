from typing import AsyncGenerator
from urllib.parse import urlparse

from tinydb import TinyDB, where
from tinydb.database import Document

from pystargazer.models import AbstractKVContainer, KVPair


class KVContainer(AbstractKVContainer):
    async def delete(self, obj: KVPair):
        self.table.remove(where("key") == obj.key)

    async def iter(self) -> AsyncGenerator[KVPair, None]:
        for doc in self.table.all():
            yield KVPair.load(doc)

    def __init__(self, url: str):
        super().__init__()
        parsed_url = urlparse(url)
        db = "/".join([
            parsed_url.netloc,
            *parsed_url.path[1:].split("/")[:-1]
        ])
        table = parsed_url.path.split("/")[-1]

        self.db = TinyDB(db)
        self.table = self.db.table(table)

    async def get(self, key: str) -> KVPair:
        doc: dict = self.table.search(where("key") == key)[0]
        return KVPair.load(doc) if doc else None

    async def has_field(self, field: str) -> AsyncGenerator[KVPair, None]:
        for doc in self.table.search(where(field).exists()):
            yield KVPair.load(doc)

    async def put(self, obj: KVPair):
        if old_doc := self.table.search(where("key") == obj.key)[0]:
            self.table.write_back([Document(obj.dump(), old_doc.doc_id)])
        else:
            self.table.insert(obj.dump())
