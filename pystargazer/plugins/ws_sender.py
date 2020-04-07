from typing import List

from starlette.endpoints import WebSocket, WebSocketEndpoint

from pystargazer.app import app
from pystargazer.models import Event

ws_clients: List[WebSocket] = []


@app.ws_route("/ws")
class EventEndPoint(WebSocketEndpoint):
    async def on_connect(self, websocket: WebSocket) -> None:
        await super().on_connect(websocket)
        ws_clients.append(websocket)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        await super().on_disconnect(websocket, close_code)
        ws_clients.remove(websocket)


@app.dispatcher
async def ws_send(event: Event):
    for client in ws_clients:
        await client.send_json(event.msg)
