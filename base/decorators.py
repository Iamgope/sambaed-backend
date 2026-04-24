import logging
import functools
from collections.abc import Awaitable, Callable

from base.exception import ServiceException
from base.response import status_400, status_500

logger = logging.getLogger(__name__)


def handle_exception(func: callable) -> callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceException as e:
            return status_400(message=e.message)
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e=}", exc_info=True)
            return status_500(message="Something went wrong")
    return wrapper


def websocket_catch_service_exception(default_message: str = "Request failed"):
    """
    Async consumer decorator: on ServiceException, call ``self._send_error(...)`` and
    return. For async methods of ``AsyncWebsocketConsumer`` subclasses.
    """

    def decorator(
        method: Callable[..., Awaitable],
    ) -> Callable[..., Awaitable]:
        @functools.wraps(method)
        async def wrapper(self, *args, **kwargs):
            try:
                return await method(self, *args, **kwargs)
            except ServiceException as e:
                await self._send_error(e.message or default_message)

        return wrapper

    return decorator
