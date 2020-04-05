import json

from httpx import AsyncClient


class Bilibili:
    def __init__(self):
        self.client = AsyncClient()

    async def fetch(self, user_id: int, since_id: int = 1):
        url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
        payload = {
            "visitor_uid": 0,
            "host_uid": user_id,
            "offset_dynamic_id": 0,
            "need_top": 0
        }

        r = (await self.client.get(url, params=payload)).json()

        try:
            # noinspection PyTypeChecker
            dyn = json.loads(r["data"]["cards"][0]["card"])["item"]
        except json.JSONDecodeError:
            print("Bilibili Dynamic read error")
            return since_id, None

        dyn_id = dyn["id"]
        if dyn_id == since_id:
            return since_id, None

        dyn_description = dyn["description"]
        dyn_photos = [entry["img_src"] for entry in dyn["pictures"]]

        return dyn_id, (dyn_description, dyn_photos)
