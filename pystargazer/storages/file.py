from typing import AsyncGenerator, Optional, Tuple
from urllib.parse import urlparse

from tinydb import TinyDB, where
from tinydb.database import Document

from pystargazer.models import AbstractKVContainer, KVPair


class FileKVContainer(AbstractKVContainer):
    async def delete(self, obj: KVPair) -> KVPair:
        doc: Document = self.table.search(where("key") == obj.key)[0]
        self.table.remove(doc_ids=[doc.doc_id])
        return KVPair.load(doc)

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
        docs: dict = self.table.search(where("key") == key)
        return KVPair.load(docs[0]) if docs else None

    async def has_field(self, field: str) -> AsyncGenerator[KVPair, None]:
        for doc in self.table.search(where(field).exists()):
            yield KVPair.load(doc)

    async def put(self, obj: KVPair) -> Tuple[Optional[KVPair], KVPair]:
        if old_docs := self.table.search(where("key") == obj.key):
            old_doc = old_docs[0]
            doc = Document(obj.dump(), old_doc.doc_id)
            self.table.write_back([doc])
            return KVPair.load(old_doc), obj
        else:
            self.table.insert(obj.dump())
            return None, obj


def get_container():
    return FileKVContainer
