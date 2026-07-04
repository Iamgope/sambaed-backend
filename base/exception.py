import logging

logger = logging.getLogger(__name__)


class ExceptionType:
    WARNING = "WARNING"
    ERROR = "ERROR"


class ServiceException(Exception):
    @property
    def type(self):
        return self._type

    @property
    def error_code(self):
        return self._error_code

    @property
    def message(self):
        return self._message

    @property
    def error_message(self):
        return self._error_message

    def __init__(self, *args, **kwargs):
        logger.info(
            f"[ServiceException][__init__] :: args - {args} :: kwargs - {kwargs}"
        )
        self._type = kwargs.get("type", ExceptionType.WARNING)
        self._error_code = kwargs.get("error_code", 400)
        self._error_message = kwargs.get("error_message", None)
        self._message = kwargs.get("message", None)
        Exception.__init__(self, *args)
