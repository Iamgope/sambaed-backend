from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


class AppVersionMiddleware:
    """Reads X-App-Version header and attaches it to request.app_version."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.app_version = request.headers.get("X-App-Version", "")
        return self.get_response(request)



def _bearer_from_headers(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            part = value.decode("latin-1").strip()
            if part.lower().startswith("bearer "):
                return part[7:].strip() or None
    return None


@database_sync_to_async
def get_user_from_token(token: str) -> User | AnonymousUser:
    try:
        validated = AccessToken(token)
        return User.objects.get(id=validated['user_id'])
    except (TokenError, User.DoesNotExist):
        return AnonymousUser()


def _app_version_from_headers(scope):
    for name, value in scope.get("headers", []):
        if name == b"x-app-version":
            part = value.decode("latin-1").strip()
            return int(part)
    return None


class JWTAuthMiddleware(BaseMiddleware):
    """Attach a User to the WebSocket scope from ``Authorization: Bearer <jwt>``.

    Falls back to ``?token=<jwt>`` if the header is absent.
    """

    async def __call__(self, scope, receive, send):
        token = _bearer_from_headers(scope)
        app_version = _app_version_from_headers(scope)
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        scope["app_version"] = app_version
        return await super().__call__(scope, receive, send)
