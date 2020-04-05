from urllib.parse import urljoin

from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT
from starlette.websockets import WebSocket


class EventEndPoint(WebSocketEndpoint):
    async def on_connect(self, websocket: WebSocket) -> None:
        await super().on_connect(websocket)
        state = websocket.app.state
        state.ws_clients.append(websocket)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        await super().on_disconnect(websocket, close_code)
        state = websocket.app.state
        state.ws_clients.remove(websocket)


async def on_create(request: Request):
    state = request.app.state

    vtb_name = (await request.body()).decode("utf-8")
    if state.vtubers.get(vtb_name) is not None:
        return PlainTextResponse("Conflict", status_code=HTTP_409_CONFLICT)

    state.vtubers[vtb_name] = {}

    state.vtubers.save()
    return RedirectResponse(url=urljoin(state.base_url, vtb_name), status_code=HTTP_201_CREATED)


async def on_delete(request: Request):
    state = request.app.state

    vtb_name = request.path_params["vtb_name"]
    if (vtuber := state.vtubers.get(vtb_name)) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

    if youtube_id := vtuber.get("youtube"):
        await state.youtube.unsubscribe(youtube_id)

    state.vtubers.pop(vtb_name)
    state.vtubers.save()
    return JSONResponse(list(state.vtubers))


async def on_delete_key(request: Request):
    state = request.app.state

    vtb_name = request.path_params["vtb_name"]
    if (vtuber := state.vtubers.get(vtb_name)) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
    key = request.path_params["key"]
    if vtuber.get(key) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

    value = vtuber.pop(key)

    if key == "youtube":
        await state.youtube.unsubscribe(value)

    state.vtubers.save()
    return JSONResponse(state.vtubers[vtb_name])


async def on_iter(request: Request):
    state = request.app.state
    return JSONResponse(list(state.vtubers))


async def on_put_key(request: Request):
    state = request.app.state

    vtb_name = request.path_params["vtb_name"]
    if (vtuber := state.vtubers.get(vtb_name)) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

    key = request.path_params["key"]
    value = (await request.body()).decode("utf-8")

    if key == "youtube":
        if old_key := vtuber.get(key):
            await state.youtube.unsubscribe(old_key)
        await state.youtube.subscribe(value)

    state.vtubers[vtb_name][key] = value

    state.vtubers.save()
    return JSONResponse(state.vtubers[vtb_name])


async def on_query(request: Request):
    state = request.app.state
    vtb_name = request.path_params["vtb_name"]
    if state.vtubers.get(vtb_name) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
    return JSONResponse(state.vtubers[vtb_name])


async def on_query_key(request: Request):
    state = request.app.state
    vtb_name = request.path_params["vtb_name"]
    key = request.path_params["key"]
    if state.vtubers.get(vtb_name) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
    vtuber = state.vtubers[vtb_name]
    if vtuber.get(key) is None:
        return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
    return JSONResponse(state.vtubers[vtb_name][key])
