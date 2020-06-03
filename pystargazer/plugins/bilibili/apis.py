import datetime
import json
import logging
from typing import Optional, Tuple, Union

import fastjsonschema
from httpx import AsyncClient, HTTPError, Headers

from .schemas import card_schema, dyn_schemas


def parse_card(raw_card) -> Optional[Union[int, tuple]]:
    try:
        card_schema(raw_card)
        card = json.loads(raw_card["card"])
    except (json.JSONDecodeError, fastjsonschema.JsonSchemaException):
        logging.error(f"Malformed Bilibili dynamic card: {raw_card}")
        return None

    dyn_type = raw_card["desc"]["type"]
    dyn_id = raw_card["desc"]["dynamic_id"]

    try:
        dyn_schemas[dyn_type](card)
    except fastjsonschema.JsonSchemaException:
        logging.error(f"Malformed Bilibili dynamic: {card}")
        return dyn_id
    except KeyError:
        return dyn_id

    if dyn_type == 1:  # forward
        dyn = card["item"]

        raw_dyn_orig = card["origin"]

        rt_dyn_raw = {
            "desc": {
                "type": dyn["orig_type"],
                "dynamic_id": dyn["orig_dy_id"]
            },
            "card": raw_dyn_orig
        }
        rt_dyn = parse_card(rt_dyn_raw)
        if not isinstance(rt_dyn, tuple):
            return dyn_id

        dyn_text = f'{dyn["content"]}\nRT {rt_dyn[1][0]}'
        dyn_photos = rt_dyn[1][1]
    elif dyn_type == 2:  # pic
        dyn = card["item"]

        dyn_text = dyn["description"]
        dyn_photos = [entry["img_src"] for entry in dyn["pictures"]]
    elif dyn_type == 4:  # plaintext
        dyn = card["item"]

        dyn_text = dyn["content"]
        dyn_photos = []
    elif dyn_type == 8:  # video
        dyn_text = "\n".join([
            card["title"],
            f'https://www.bilibili.com/video/av{card["aid"]}'
        ])
        dyn_photos = [card["pic"]]
    else:
        return dyn_id

    return dyn_id, (dyn_text, dyn_photos, dyn_type)


class Bilibili:
    def __init__(self):
        self.client = AsyncClient()
        self.client.headers = Headers({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 "
                          "Safari/537.36"
        })
        self.disabled_until: Optional[datetime.datetime] = None

    async def fetch(self, user_id: int, since_id: int = 1) -> Tuple[int, list]:
        if self.disabled_until:
            if self.disabled_until < datetime.datetime.now():
                logging.info("Bilibili crawler resumed.")
                self.disabled_until = None
            else:
                return since_id, []

        url = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
        payload = {
            "visitor_uid": 0,
            "host_uid": user_id,
            "offset_dynamic_id": 0,
            "need_top": 0
        }

        try:
            resp = await self.client.get(url, params=payload)
        except HTTPError:
            logging.error("Bilibili api fetch error.")
            return since_id, []

        try:
            r = resp.json()
        except json.JSONDecodeError:
            logging.error(f"Malformed Bilibili API response: {resp.text}")
            return since_id, []

        try:
            cards = r["data"]["cards"]
        except TypeError:
            if r.get("code") == -412:
                logging.error("Bilibili API Throttled. Crawler paused.")
                self.disabled_until = datetime.datetime.now() + datetime.timedelta(minutes=30)
                return since_id, []
            else:
                logging.error(f"Malformed Bilibili API response: {resp.text}")
                return since_id, []
        except KeyError:
            logging.error(f"Malformed Bilibili API response: {resp.text}")
            return since_id, []

        dyn_id = rtn_id = since_id
        dyn_list = []

        counter = 0

        for raw_card in cards:
            if isinstance((rtn := parse_card(raw_card)), tuple):
                dyn_id, dyn_entry = rtn
                if dyn_id == since_id:
                    break
                dyn_list.append(dyn_entry)
            elif rtn:
                dyn_id = rtn

            if dyn_id == since_id:
                break

            counter += 1
            if counter == 1:
                rtn_id = dyn_id
            elif counter == 6:
                break

        return rtn_id, dyn_list
