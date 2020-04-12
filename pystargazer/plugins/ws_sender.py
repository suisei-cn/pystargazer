from typing import List

from starlette.endpoints import WebSocket, WebSocketEndpoint

from pystargazer.app import app
from pystargazer.models import Event

ws_clients: List[WebSocket] = []


@app.ws_route("/event")
class EventEndPoint(WebSocketEndpoint):
    async def on_connect(self, websocket: WebSocket) -> None:
        await super().on_connect(websocket)
        ws_clients.append(websocket)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        await super().on_disconnect(websocket, close_code)
        ws_clients.remove(websocket)


@app.dispatcher
async def ws_send(event: Event):
    msg: dict = {"name": event.vtuber, "images": event.data.get("images", [])}
    print("ws event:", event.to_json())
    if event.type == "tweet":
        msg["title"] = "Twitter 推文"
        msg["text"] = event.data["text"]
    elif event.type == "bili_dyn":
        msg["title"] = "Bilibili 翻译"
        msg["text"] = event.data["text"]
    elif event.type == "youtube_video":
        msg["title"] = "Youtube 视频"
        msg["text"] = "\n".join([
            event.data["title"],
            f"链接：{event.data['link']}"
        ])
    elif event.type == "youtube_broadcast_live":
        msg["title"] = "Youtube 配信开始（上播）"
        msg["text"] = "\n".join([
            event.data["title"],
            f"预定时间：{event.data['scheduled_start_time']}",
            f"开播时间：{event.data['actual_start_time']}",
            f"链接：{event.data['link']}"
        ])
    elif event.type == "youtube_broadcast_reminder":
        msg["title"] = "Youtube 配信开始（预定）"
        msg["text"] = "\n".join([
            event.data["title"],
            f"预定时间：{event.data['scheduled_start_time']}",
            f"链接：{event.data['link']}"
        ])
    elif event.type == "youtube_broadcast_schedule":
        msg["title"] = "Youtube 配信预告"
        msg["text"] = "\n".join([
            event.data["title"],
            f"预定时间：{event.data['scheduled_start_time']}",
            f"链接：{event.data['link']}"
        ])
    print("ws constructed:", msg)
    if msg.get("title"):
        for client in ws_clients:
            await client.send_json(msg)
