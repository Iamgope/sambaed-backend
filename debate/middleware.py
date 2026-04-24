from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


def _bearer_from_headers(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            part = value.decode("latin-1").strip()
            if part.lower().startswith("bearer "):
                return part[7:].strip() or None
    return None


def _token_from_query(scope) -> str | None:
    query_string = scope.get("query_string", b"").decode()
    params = parse_qs(query_string)
    token_list = params.get("token", [])
    return token_list[0] if token_list else None


@database_sync_to_async
def get_user_from_token(token: str) -> User | AnonymousUser:
    try:
        validated = AccessToken(token)
        return User.objects.get(id=validated['user_id'])
    except (TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Attach a User to the WebSocket scope from ``Authorization: Bearer <jwt>``.

    Falls back to ``?token=<jwt>`` if the header is absent.
    """

    async def __call__(self, scope, receive, send):
        token = _bearer_from_headers(scope) or _token_from_query(scope)
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
