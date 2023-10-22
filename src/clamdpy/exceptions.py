from __future__ import annotations


class ClamdException(Exception):
    pass


class UnknownCommand(ClamdException):
    """An unknown command was sent to clamd."""

    def __init__(self, command: str) -> None:
        self.command = command


class CommandReadTimedOut(ClamdException):
    """Clamd timed out when reading the command."""

    def __init__(self, command: str) -> None:
        self.command = command


class ResponseError(ClamdException):
    """Clamd answered with an error."""

    def __init__(self, command: str, error: str) -> None:
        self.command = command
        self.error = error


class BufferTooLongError(ResponseError):
    """The buffer sent with the `INSTREAM` command is too large."""

    def __init__(self, error: str) -> None:
        super().__init__("INSTREAM", error)


class ConnectionError(ClamdException):
    """Connection error when connecting or receiving data from clamd."""

    def __init__(self, msg: str, errorno: int | None = None) -> None:
        self.msg = msg
        self.errorno = errorno
