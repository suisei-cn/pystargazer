import asyncio

from httpx import AsyncClient, Headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair


class Twitter:
    def __init__(self, token: str):
        self.client = AsyncClient()
        self.client.headers = Headers({
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "holo observatory bot/1.0.0 (cy.n01@outlook.com)"
        })

    async def fetch(self, user_id: int, since_id: int = 1):
        url = "https://api.twitter.com/1.1/statuses/user_timeline.json"
        payload = {
            "user_id": user_id,
            "since_id": since_id,
            "exclude_replies": True,
            "include_rts": True
        }

        r = (await self.client.get(url, params=payload)).json()
        if not r:
            return since_id, None

        tweet = r[0]
        tweet_id = tweet["id"]
        tweet_text = tweet["text"]
        tweet_media = tweet["entities"].get("media", [])
        tweet_photos = [medium["media_url"] for medium in tweet_media if medium["type"] == "photo"]

        return tweet_id, (tweet_text, tweet_photos)


twitter = Twitter(app.credentials.get("twitter"))


async def get_option(key: str):
    if (my_config := await app.configs.get("twitter")) is not None:
        if my_config.value.get(key) == "true":
            return True
    return False


@app.route("/help/twitter", methods=["GET"])
async def youtube_help(request: Request):
    return PlainTextResponse(
        "Field: twitter\n"
        "Configs[/configs/twitter]:\n"
        "  disabled"
    )


@app.on_startup
async def twitter_startup():
    if await app.plugin_state.get("twitter_since") is None:
        await app.plugin_state.put(KVPair("twitter_since", {}))


@app.scheduled("interval", minutes=1)
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
            "tweet",
            name,
            {"text": tweet[1][0], "images": tweet[1][1]}
        )
        for name, tweet in valid_tweets.items())
    await asyncio.gather(*(app.send_event(event) for event in events))
