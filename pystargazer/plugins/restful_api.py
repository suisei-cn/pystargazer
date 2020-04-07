from urllib.parse import urljoin

from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from pystargazer.app import app
from pystargazer.models import KVPair


@app.route("/vtubers")
class RootEP(HTTPEndpoint):
    async def get(self, request: Request):
        vtb_names = []
        # noinspection PyTypeChecker
        async for doc in app.vtubers.iter():
            vtb_names.append(doc.key)

        return JSONResponse(vtb_names)

    async def post(self, request: Request):
        vtubers = app.vtubers

        vtb_name = (await request.body()).decode("utf-8")
        if (await vtubers.get(vtb_name)) is not None:
            return PlainTextResponse("Conflict", status_code=HTTP_409_CONFLICT)

        await vtubers.put(KVPair(vtb_name, {}))
        return RedirectResponse(url=urljoin(app.credentials.get("base_url"), vtb_name), status_code=HTTP_201_CREATED)


@app.route("/vtubers/{vtb_name}")
class EntryEP(HTTPEndpoint):
    async def get(self, request: Request):
        vtubers = app.vtubers

        vtb_name = request.path_params["vtb_name"]
        if (vtuber := await vtubers.get(vtb_name)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        return JSONResponse(vtuber.value)

    async def delete(self, request: Request):
        vtubers = app.vtubers

        vtb_name = request.path_params["vtb_name"]
        if (vtuber := await vtubers.get(vtb_name)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        '''
        if youtube_id := vtuber.value.get("youtube"):
            await state.youtube.unsubscribe(youtube_id)
        '''

        await vtubers.delete(KVPair(vtb_name, {}))
        return Response()


@app.route("/vtubers/{vtb_name}/{key}")
class KeyEP(HTTPEndpoint):
    async def get(self, request: Request):
        vtubers = app.vtubers

        vtb_name = request.path_params["vtb_name"]
        key = request.path_params["key"]
        if (vtuber := await vtubers.get(vtb_name)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        if (value := vtuber.value.get(key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        return JSONResponse(value)

    async def put(self, request: Request):
        vtubers = app.vtubers

        vtb_name = request.path_params["vtb_name"]
        if (vtuber := await vtubers.get(vtb_name)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        key = request.path_params["key"]
        value = (await request.body()).decode("utf-8")

        """
        if key == "youtube":
            if old_key := vtuber.get(key):
                await state.youtube.unsubscribe(old_key)
            await state.youtube.subscribe(value)
        """

        vtuber.value[key] = value

        await vtubers.put(vtuber)
        return Response()

    async def delete(self, request: Request):
        vtubers = app.vtubers

        vtb_name = request.path_params["vtb_name"]
        if (vtuber := await vtubers.get(vtb_name)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        key = request.path_params["key"]
        if vtuber.value.get(key) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        value = vtuber.value.pop(key)

        """
        if key == "youtube":
            await state.youtube.unsubscribe(value)
        """

        await vtubers.put(vtuber)
        return Response()
