import asyncio

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pystargazer.app import app
from pystargazer.models import Event, KVPair
from .apis import Twitter
from .schemas import schema
from .models import Tweet

twitter = Twitter(app.credentials.get("twitter"))


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

    tweet: Tweet
    events = (
        Event(
            "t_rt" if tweet.is_rt else "t_tweet",
            name,
            {"text": tweet.text, "images": tweet.photos, "link": tweet.link}
        )
        for name, tweet_set in valid_tweets.items()
        for tweet in tweet_set[1])
    await asyncio.gather(*(app.send_event(event) for event in events))
