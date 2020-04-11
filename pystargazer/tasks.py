import asyncio
from itertools import compress
from typing import List

from starlette.applications import Starlette
from starlette.responses import Response

from .bilibili import Bilibili
from .twitter import Twitter
from .youtube import EventType, ResourceType, Youtube


async def broadcast(app: Starlette, messages: List[dict]):
    for client in app.state.ws_clients:
        print("current loop", id(asyncio.get_running_loop()))
        print("sending message")
        print(messages)
        await asyncio.gather(*(client.send_json(msg) for msg in messages))
        print("message sent")


async def on_ping(request):
    await broadcast(request.app, [{"name": "test", "title": "pong", "text": "Lorem Ipsum.", "images": []}])
    return Response()


async def bilibili_task(app: Starlette):
    if not app.state.ws_clients:
        return

    bilibili: Bilibili = app.state.bilibili

    b_since: dict = app.state.bilibili_since

    vtubers: dict = app.state.vtubers
    b_ids = [vtuber.get("bilibili") for vtuber in vtubers.values()]
    b_valid_ids = list(filter(bool, b_ids))
    b_names = list(compress(vtubers, b_ids))

    dyns = await asyncio.gather(*(bilibili.fetch(b_id, b_since.get(b_name, 1))
                                  for b_name, b_id in zip(b_names, b_valid_ids)))

    valid_dyns = {name: dyn for name, dyn in zip(b_names, dyns) if dyn[1]}
    since = {name: dyn[0] for name, dyn in valid_dyns.items()}
    b_since.update(since)

    messages = [{"name": name, "title": "Bilibili 翻译", "text": dyn[1][0], "images": dyn[1][1]}
                for name, dyn in valid_dyns.items()
                if dyn[1][0] == "分享图片"]
    await broadcast(app, messages)


async def twitter_task(app: Starlette):
    if not app.state.ws_clients:
        return

    twitter: Twitter = app.state.twitter

    t_since: dict = app.state.twitter_since

    vtubers: dict = app.state.vtubers
    t_ids = [vtuber.get("twitter") for vtuber in vtubers.values()]
    t_valid_ids = list(filter(bool, t_ids))
    t_names = list(compress(vtubers, t_ids))

    tweets = await asyncio.gather(*(twitter.fetch(t_id, t_since.get(t_name, 1))
                                    for t_name, t_id in zip(t_names, t_valid_ids)))

    valid_tweets = {name: tweet for name, tweet in zip(t_names, tweets) if tweet[1]}
    since = {name: tweet[0] for name, tweet in valid_tweets.items()}
    t_since.update(since)

    messages = [{"name": name, "title": "Twitter 动态", "text": tweet[1][0], "images": tweet[1][1]}
                for name, tweet in valid_tweets.items()]
    await broadcast(app, messages)


async def youtube_task(app: Starlette):
    def get_vtuber(channel_id):
        return next(vtuber for vtuber, params in vtubers.items()
                    if params.get("youtube") == channel_id)

    vtubers: dict = app.state.vtubers
    youtube: Youtube = app.state.youtube

    channel_ids = [channel_id for vtuber in vtubers.values() if (channel_id := vtuber.get("youtube"))]
    print("start to subscribe")
    await asyncio.gather(*(youtube.subscribe(channel_id) for channel_id in channel_ids))

    print("start to listen to events")
    async for event in youtube.event():
        print("event received", event)
        try:
            name = get_vtuber(event.channel)
        except StopIteration:
            continue
        video = event.video

        if event.type == ResourceType.VIDEO:
            text = [
                f"{video.title}",
                f"链接：{video.link}"
            ]
            message = {"name": name, "title": "Youtube 视频",
                       "text": "\n".join(text), "images": [video.thumbnail]}
        elif event.type == ResourceType.BROADCAST:
            scheduled_start_time_print = video.scheduled_start_time.strftime("%Y-%m-%d %I:%M%p (CST)")
            # if event.event == EventType.SCHEDULE:
            #     text = [
            #         f"{video.title}",
            #         f"预定时间：{scheduled_start_time_print}",
            #         f"链接：{video.link}"
            #     ]
            #     message = {"name": name, "title": "Youtube 配信预告",
            #                "text": "\n".join(text), "images": [video.thumbnail]}
            # elif event.event == EventType.REMINDER:
            #     text = [
            #         f"{video.title}",
            #         f"预定时间：{scheduled_start_time_print}",
            #         f"链接：{video.link}"
            #     ]
            #     message = {"name": name, "title": "Youtube 配信开始（预定）",
            #                "text": "\n".join(text), "images": [video.thumbnail]}
            # elif event.event == EventType.LIVE:
            if event.event == EventType.LIVE:
                actual_start_print = video.actual_start_time.strftime("%Y-%m-%d %I:%M%p (CST)")
                text = [
                    f"{video.title}",
                    f"预定时间：{scheduled_start_time_print}",
                    f"开播时间：{actual_start_print}",
                    f"链接：{video.link}"
                ]
                message = {"name": name, "title": "Youtube 配信开始（上播）",
                           "text": "\n".join(text), "images": [video.thumbnail]}
            else:
                continue
        else:
            continue
        print(message)
        await broadcast(app, [message])
        print("message sent")
    print("job exit")
