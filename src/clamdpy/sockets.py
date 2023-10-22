from __future__ import annotations

import socket
import struct
import sys
from pathlib import Path
from typing import Literal, overload

from .exceptions import BufferTooLongError, CommandReadTimedOut, ConnectionError, ResponseError, UnknownCommand
from .models import ScanResult, VersionInfo
from .typing import StrPath, SupportsRead

UNKNOWN_COMMAND = "UNKNOWN COMMAND"
COMMAND_READ_TIMED_OUT = "COMMAND READ TIMED OUT"
DEFAULT_UNIX_SOCKET_PATH = "/var/run/clamav/clamd.ctl"


class ClamdNetworkSocket:
    """A class to interact with clamd with a network socket (`socket.AF_INET`)."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3310,
        timeout: float | None = None,
        max_chunk_size: int = 1024,
        line_terminator: Literal["n", "z"] = "n",
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_chunk_size = max_chunk_size
        self.line_terminator = line_terminator

    @property
    def _endline(self) -> Literal["\n", "\0"]:
        return "\n" if self.line_terminator == "n" else "\0"

    def _acquire_socket(self) -> socket.socket:
        try:
            clamd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clamd_socket.settimeout(self.timeout)
            clamd_socket.connect((self.host, self.port))
            return clamd_socket
        except OSError as e:
            if len(e.args) == 1:
                raise ConnectionError(f"Error while connecting to {self.host}:{self.port}: {e.args[0]}")
            raise ConnectionError(f"Error while connecting to {self.host}:{self.port}: {e.args[1]}", int(e.args[0]))

    def _command(self, command: str, *args: str, multiline: bool = True, raise_on_error: bool = True) -> str:
        with self._acquire_socket() as sock:
            self._send(sock, command, *args)
            recv = self._recv(sock, multiline=multiline)
            if recv == UNKNOWN_COMMAND:
                raise UnknownCommand(command)
            if recv == COMMAND_READ_TIMED_OUT:
                raise CommandReadTimedOut(command)
            if raise_on_error:
                response = recv.rsplit("ERROR", 1)
                if len(response) > 1:
                    raise ResponseError(command, response[0].strip())
            return recv

    def _send(self, sock: socket.socket, command: str, *args: str) -> None:
        cmd = f"{self.line_terminator}{command}"
        if args:
            cmd += f" {' '.join(args)}"
        cmd += self._endline

        sock.sendall(cmd.encode("utf-8"))

    def _recv(self, sock: socket.socket, multiline: bool = True) -> str:
        try:
            with sock.makefile("rb") as f:
                if multiline:
                    return f.read().decode("utf-8").strip(self._endline)
                else:
                    return f.readline().decode("utf-8").strip(self._endline)
        except OSError as e:
            if len(e.args) == 1:
                raise ConnectionError(f"Error while reading from socket: {e.args[0]}")
            raise ConnectionError(f"Error while reading from socket: {e.args[1]}", int(e.args[0]))

    @overload
    def _any_scan(self, command: str, path: StrPath, raw: Literal[True]) -> str:
        ...

    @overload
    def _any_scan(self, command: str, path: StrPath, raw: Literal[False] = ...) -> list[ScanResult]:
        ...

    def _any_scan(self, command: str, path: StrPath, raw: bool = False) -> list[ScanResult] | str:
        path = Path(path).absolute()
        result = self._command(command, str(path), raise_on_error=False)
        if raw:
            return result
        return [ScanResult._from_str(line, command) for line in result.split(self._endline)]

    def ping(self) -> str:
        """Check the server's state. It should reply with "PONG"."""

        return self._command("PING")

    def reload(self) -> str:
        """Reload the virus databases."""

        return self._command("RELOAD")

    def shutdown(self) -> None:
        """Perform a clean exit."""

        with self._acquire_socket() as sock:
            self._send(sock, "SHUTDOWN")

    @overload
    def version(self, raw: Literal[True]) -> str:
        ...

    @overload
    def version(self, raw: Literal[False] = ...) -> VersionInfo:
        ...

    def version(self, raw: bool = False) -> VersionInfo | str:
        """Print program and database versions.

        Args:
            raw: Whether the raw string response should be returned. Default: False.
        """
        rv = self._command("VERSION")
        if raw:
            return rv
        return VersionInfo._from_str(rv)

    def stats(self):
        """Replies with statistics about the scan queue, contents of scan queue, and memory
        usage. The exact reply format is subject to change in future releases.
        """

        return self._command("STATS")

    @overload
    def scan(self, path: StrPath, raw: Literal[True]) -> str:
        ...

    @overload
    def scan(self, path: StrPath, raw: Literal[False] = ...) -> list[ScanResult]:
        ...

    def scan(self, path: StrPath, raw: bool = False) -> list[ScanResult] | str:
        """Scan a file or a directory (recursively) with archive support enabled (if not disabled in clamd.conf).
        A full path is required.
        """

        return self._any_scan("SCAN", path, raw)  # type: ignore[call-overload]

    @overload
    def contscan(self, path: StrPath, raw: Literal[True]) -> str:
        ...

    @overload
    def contscan(self, path: StrPath, raw: Literal[False] = ...) -> list[ScanResult]:
        ...

    def contscan(self, path: StrPath, raw: bool = False) -> list[ScanResult] | str:
        """Scan file or directory (recursively) with archive support enabled and don't stop
        the scanning when a virus is found.
        """

        return self._any_scan("CONTSCAN", path, raw)  # type: ignore[call-overload]

    @overload
    def multiscan(self, path: StrPath, raw: Literal[True]) -> str:
        ...

    @overload
    def multiscan(self, path: StrPath, raw: Literal[False] = ...) -> list[ScanResult]:
        ...

    def multiscan(self, path: StrPath, raw: bool = False) -> list[ScanResult] | str:
        """Scan file in a standard way or scan directory (recursively) using multiple threads
        (to make the scanning faster on SMP machines).
        """

        return self._any_scan("MULTISCAN", path, raw)  # type: ignore[call-overload]

    @overload
    def instream(
        self,
        buff: SupportsRead[bytes],
        raw: Literal[True],
        max_chunk_size: int | None = ...,
    ) -> str:
        ...

    @overload
    def instream(
        self,
        buff: SupportsRead[bytes],
        raw: Literal[False] = ...,
        max_chunk_size: int | None = ...,
    ) -> ScanResult:
        ...

    def instream(
        self,
        buff: SupportsRead[bytes],
        raw: bool = False,
        max_chunk_size: int | None = None,
    ) -> ScanResult | str:
        """Scan a stream of data. The stream is sent to clamd in chunks, after INSTREAM,
        on the same socket on which the command was sent.
        """

        max_chunk_size = max_chunk_size or self.max_chunk_size
        with self._acquire_socket() as sock:
            self._send(sock, "INSTREAM")
            chunk = buff.read(max_chunk_size)
            while chunk:
                # 4 byte unsigned integer in network byte order:
                size = struct.pack(b"!L", len(chunk))
                sock.sendall(size + chunk)
                chunk = buff.read(max_chunk_size)

            sock.sendall(struct.pack(b"!L", 0))

            result = self._recv(sock)
            if "INSTREAM size limit exceeded" in result:
                raise BufferTooLongError(result.rsplit("ERROR", 1)[0].strip())
            if raw:
                return result
            return ScanResult._from_str(result, "INSTREAM", stream=True)


class ClamdUnixSocket(ClamdNetworkSocket):
    def __init__(
        self,
        path: StrPath = DEFAULT_UNIX_SOCKET_PATH,
        timeout: float | None = None,
        max_chunk_size: int = 1024,
        line_terminator: Literal["n", "z"] = "n",
    ) -> None:
        if sys.platform == "win32":
            raise RuntimeError(f"{self.__class__.__name__} cannot be used under win32.")
        self.socket_path = path
        self.timeout = timeout
        self.max_chunk_size = max_chunk_size
        self.line_terminator = line_terminator

    def _acquire_socket(self) -> socket.socket:
        try:
            clamd_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            clamd_socket.settimeout(self.timeout)
            clamd_socket.connect(str(self.socket_path))
            return clamd_socket
        except OSError as e:
            if len(e.args) == 1:
                raise ConnectionError(f"Error while connecting to {self.socket_path}: {e.args[0]}")
            raise ConnectionError(f"Error while connecting to {self.socket_path}: {e.args[1]}", int(e.args[0]))
