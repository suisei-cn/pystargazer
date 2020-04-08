from urllib.parse import urljoin

from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from pystargazer.app import app
from pystargazer.models import KVPair, AbstractKVContainer


def get_table(name: str) -> AbstractKVContainer:
    if name == "vtubers":
        return app.vtubers
    elif name == "configs":
        return app.configs
    else:
        raise KeyError("Table doesn't exist.")

@app.route("/api/{table}")
class RootEP(HTTPEndpoint):
    async def get(self, request: Request):
        table = get_table(request.path_params["table"])

        keys = []
        # noinspection PyTypeChecker
        async for doc in table.iter():
            keys.append(doc.key)

        return JSONResponse(keys)

    async def post(self, request: Request):
        table = get_table(request.path_params["table"])

        key = (await request.body()).decode("utf-8")
        if (await table.get(key)) is not None:
            return PlainTextResponse("Conflict", status_code=HTTP_409_CONFLICT)

        await table.put(KVPair(key, {}))
        return RedirectResponse(url=urljoin(app.credentials.get("base_url"), key), status_code=HTTP_201_CREATED)


@app.route("/api/{table}/{prime_key}")
class EntryEP(HTTPEndpoint):
    async def get(self, request: Request):
        table = get_table(request.path_params["table"])

        key = request.path_params["prime_key"]
        if (value := await table.get(key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        return JSONResponse(value.value)

    async def delete(self, request: Request):
        table = get_table(request.path_params["table"])

        key = request.path_params["prime_key"]
        if await table.get(key) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        await table.delete(KVPair(key, {}))
        return Response()


@app.route("/api/{table}/{prime_key}/{key}")
class KeyEP(HTTPEndpoint):
    async def get(self, request: Request):
        table = get_table(request.path_params["table"])

        prime_key = request.path_params["prime_key"]
        key = request.path_params["key"]
        if (prime_value := await table.get(prime_key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        if (value := prime_value.value.get(key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        return JSONResponse(value)

    async def put(self, request: Request):
        table = get_table(request.path_params["table"])

        prime_key = request.path_params["prime_key"]
        if (prime_value := await table.get(prime_key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        key = request.path_params["key"]
        value = (await request.body()).decode("utf-8")

        prime_value.value[key] = value

        await table.put(prime_value)
        return Response()

    async def delete(self, request: Request):
        table = get_table(request.path_params["table"])

        prime_key = request.path_params["prime_key"]
        if (vtuber := await table.get(prime_key)) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)
        key = request.path_params["key"]
        if vtuber.value.get(key) is None:
            return PlainTextResponse("Not Found", status_code=HTTP_404_NOT_FOUND)

        await table.put(vtuber)
        return Response()
