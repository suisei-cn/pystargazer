import asyncio
import logging
from json import JSONDecodeError

import fastjsonschema
from httpx import AsyncClient, HTTPError, Headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair
from pystargazer.utils import get_option as _get_option

raw_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {
                "type": "number"
            },
            "id_str": {
                "type": "string"
            },
            "text": {
                "type": "string"
            },
            "entities": {
                "type": "object",
                "properties": {
                    "media": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "number"
                                },
                                "id_str": {
                                    "type": "string"
                                },
                                "media_url": {
                                    "type": "string"
                                },
                                "media_url_https": {
                                    "type": "string"
                                },
                                "url": {
                                    "type": "string"
                                },
                                "type": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "id",
                                "id_str",
                                "media_url",
                                "media_url_https",
                                "url",
                                "type"
                            ]
                        }
                    }
                }
            },
            "retweeted_status": {
                "type": "object",
                "properties": {}
            }
        },
        "required": [
            "id",
            "id_str",
            "text",
            "entities"
        ]
    }
}

schema = fastjsonschema.compile(raw_schema)


class Twitter:
    def __init__(self, token: str):
        self.client = AsyncClient()
        self.client.headers = Headers({
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "holo observatory bot/1.0.0"
        })

    async def fetch(self, user_id: int, since_id: int = 1):
        url = "https://api.twitter.com/1.1/statuses/user_timeline.json"
        payload = {
            "user_id": user_id,
            "since_id": since_id,
            "exclude_replies": True,
            "include_rts": True
        }

        try:
            resp = await self.client.get(url, params=payload)
        except HTTPError:
            logging.error("Twitter api fetch error.")
            return since_id, None

        try:
            r = resp.json()
            schema(r)
        except (JSONDecodeError, fastjsonschema.JsonSchemaException):
            logging.error(f"Malformed Twitter API response: {resp.text}")
            return since_id, None

        if not r:
            return since_id, None

        tweet_list = []
        for _, tweet in zip(range(5), r):
            is_rt = "retweeted_status" in tweet.keys()
            tweet_text = tweet["text"]
            tweet_media = tweet["entities"].get("media", [])
            tweet_photos = [medium["media_url"] for medium in tweet_media if medium["type"] == "photo"]
            tweet_list.append((tweet_text, tweet_photos, is_rt))

        return r[0]["id"], tweet_list


twitter = Twitter(app.credentials.get("twitter"))

get_option = _get_option(app, "twitter")


@app.route("/help/twitter", methods=["GET"])
async def youtube_help(request: Request):
    return PlainTextResponse(
        "Field: twitter\n"
        "Configs[/configs/twitter]:\n"
        "  disabled"
    )


@app.on_startup
async def twitter_startup():
    try:
        await app.plugin_state.get("twitter_since")
    except KeyError:
        await app.plugin_state.put(KVPair("twitter_since", {}))


@app.scheduled("interval", minutes=1, misfire_grace_time=10)
async def twitter_task():
    if await get_option("disabled"):
        return

    t_since: KVPair = await app.plugin_state.get("twitter_since")

    t_valid_ids = []
    t_names = []
    # noinspection PyTypeChecker
    async for vtuber in app.vtubers.has_field("twitter"):
        t_names.append(vtuber.key)
        t_valid_ids.append(vtuber.value["twitter"])

    tweets = await asyncio.gather(*(twitter.fetch(t_id, t_since.value.get(t_name, 1))
                                    for t_name, t_id in zip(t_names, t_valid_ids)))

    valid_tweets = {name: tweet for name, tweet in zip(t_names, tweets) if tweet[1]}
    since = {name: tweet[0] for name, tweet in valid_tweets.items()}
    t_since.value.update(since)
    await app.plugin_state.put(t_since)

    events = (
        Event(
            "t_rt" if tweet[2] else "t_tweet",
            name,
            {"text": tweet[0], "images": tweet[1]}
        )
        for name, tweet_set in valid_tweets.items()
        for tweet in tweet_set[1])
    await asyncio.gather(*(app.send_event(event) for event in events))
