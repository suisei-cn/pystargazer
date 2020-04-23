from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from pystargazer.app import app


class SimpleAuthBackend(AuthenticationBackend):
    async def authenticate(self, request):
        if "Authorization" not in request.headers:
            return

        auth = request.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != 'bearer':
                return
        except ValueError:
            raise AuthenticationError('Invalid auth credentials')

        if credentials == app.credentials.get("admin_token"):
            return AuthCredentials(["admin"]), SimpleUser("admin")
        else:
            return


app.register_middleware(Middleware(AuthenticationMiddleware, backend=SimpleAuthBackend()))
