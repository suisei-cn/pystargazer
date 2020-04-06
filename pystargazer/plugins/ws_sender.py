from starlette.endpoints import WebSocketEndpoint, WebSocket
from pystargazer import dispatcher, ws_route
from typing import List

ws_clients: List[WebSocket] = []


@ws_route("/ws")
class EventEndPoint(WebSocketEndpoint):
    async def on_connect(self, websocket: WebSocket) -> None:
        await super().on_connect(websocket)
        ws_clients.append(websocket)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        await super().on_disconnect(websocket, close_code)
        ws_clients.remove(websocket)


@dispatcher
async def ws_send(event):
    for client in ws_clients:
        await client.send_json(event)
