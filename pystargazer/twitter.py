from httpx import AsyncClient, Headers


class Twitter:
    def __init__(self, token: str):
        self.client = AsyncClient()
        self.client.headers = Headers({
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "holo observatory bot/1.0.0 (user@example.com)"
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
