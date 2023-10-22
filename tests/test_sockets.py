from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from clamdpy import ClamdNetworkSocket, ClamdUnixSocket
from clamdpy.exceptions import BufferTooLongError, CommandReadTimedOut, ResponseError, UnknownCommand
from clamdpy.models import ScanResult, VersionInfo

# TODO implement tests for this
line_terminator_param = pytest.mark.parametrize(
    "line_terminator",
    ["n", "z"],
)

clamd_class_param = pytest.mark.parametrize(
    "clamd_class",
    [ClamdUnixSocket, ClamdUnixSocket],
)


# Mock classes sourced from the test stdlib:
class MockFile:
    """Mock file object returned by MockSocket.makefile()."""

    def __init__(self, lines):
        self.lines = lines

    def readline(self, limit=-1):
        result = self.lines.pop(0) + b"\r\n"
        if limit >= 0:
            # Re-insert the line, removing the \r\n we added.
            self.lines.insert(0, result[limit:-2])
            result = result[:limit]
        return result

    def read(self, size=None):
        rv = b"\r\n".join(self.lines)
        self.lines = []
        return rv

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()


class MockSocket:
    """Mock socket object used by the smtplib tests."""

    def __init__(self, family=None):
        self.family = family
        self.output = []
        self.lines = []
        self.conn = None
        self.timeout = None

    def queue_recv(self, line):
        self.lines.append(line)

    def recv(self, bufsize, flags=None):
        data = self.lines.pop(0) + b"\r\n"
        return data

    def fileno(self):
        return 0

    def settimeout(self, timeout):
        if timeout is None:
            self.timeout = None
        else:
            self.timeout = timeout

    def gettimeout(self):
        return self.timeout

    def setsockopt(self, level, optname, value):
        pass

    def getsockopt(self, level, optname, buflen=None):
        return 0

    def bind(self, address):
        pass

    def accept(self):
        self.conn = MockSocket()
        return self.conn, "c"

    def getsockname(self):
        return ("0.0.0.0", 0)

    def setblocking(self, flag):
        pass

    def listen(self, backlog):
        pass

    def makefile(self, mode="r", bufsize=-1):
        handle = MockFile(self.lines)
        return handle

    def sendall(self, data, flags=None):
        self.last = data
        self.output.append(data)
        return len(data)

    def send(self, data, flags=None):
        self.last = data
        self.output.append(data)
        return len(data)

    def getpeername(self):
        return ("peer-address", "peer-port")

    def close(self):
        pass

    def connect(self, host):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()


@clamd_class_param
def test_unknown_command(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"UNKNOWN COMMAND"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        with pytest.raises(UnknownCommand) as excinfo:
            clamd._command("UNKNOWN")

        assert excinfo.value.args == ("UNKNOWN",)


@clamd_class_param
def test_command_read_timed_out(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"COMMAND READ TIMED OUT"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        with pytest.raises(CommandReadTimedOut) as excinfo:
            clamd._command("DUMMY")

        assert excinfo.value.args == ("DUMMY",)


@clamd_class_param
def test_response_error(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"Reason ERROR"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        with pytest.raises(ResponseError) as excinfo:
            clamd._command("DUMMY")

        assert excinfo.value.args == ("DUMMY", "Reason")


@clamd_class_param
def test_response_error_no_exc(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"Reason ERROR"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd._command("DUMMY", raise_on_error=False) == "Reason ERROR"


@clamd_class_param
def test_pong(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"PONG"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.ping() == "PONG"


@clamd_class_param
def test_reload(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"RELOADING"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.reload() == "RELOADING"


@clamd_class_param
def test_shutdown(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.shutdown() is None


@clamd_class_param
def test_version(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"ClamAV 0.103.9/27065/Wed Oct 18 09:49:14 2023"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.version(raw=True) == "ClamAV 0.103.9/27065/Wed Oct 18 09:49:14 2023"
        assert clamd.version() == VersionInfo(
            version="ClamAV 0.103.9", signature=27065, signature_date=datetime(2023, 10, 18, 9, 49, 14)
        )


@clamd_class_param
def test_stats(clamd_class: type[ClamdNetworkSocket]):
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"POOLS: 1\n\nSTATE: VALID PRIMARY\nTHREADS: live 1  idle 0 max 12 idle-timeout 30"]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.stats() == "POOLS: 1\n\nSTATE: VALID PRIMARY\nTHREADS: live 1  idle 0 max 12 idle-timeout 30"


@pytest.mark.parametrize(
    "method",
    ["scan", "contscan", "multiscan"],
)
@clamd_class_param
def test_scan(method: str, clamd_class: type[ClamdNetworkSocket]):
    rv = "/path/to/file: OK\n/path/to/file2: Virus desc FOUND\n/path/to/file3: File path check failure: No such file or directory. ERROR"
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [rv.encode("utf-8")]
        mock_socket.return_value = ms

        clamd = clamd_class()
        # We just test response parsing here, no matter the path used:
        meth = getattr(clamd, method)
        assert meth("dummy", raw=True) == rv
        assert meth("dummy") == [
            ScanResult(path=Path("/path/to/file"), reason=None, status="OK"),
            ScanResult(path=Path("/path/to/file2"), reason="Virus desc", status="FOUND"),
            ScanResult(
                path=Path("/path/to/file3"),
                reason="File path check failure: No such file or directory.",
                status="ERROR",
            ),
        ]


@pytest.mark.xfail(reason="Parsing fails when `:` in path")
@pytest.mark.parametrize(
    "method",
    ["scan", "contscan", "multiscan"],
)
@clamd_class_param
def test_scan_colon_in_path(method: str, clamd_class: type[ClamdNetworkSocket]):
    rv = "/path/to/file_with:/path: File path check failure: No such file or directory. ERROR"
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [rv.encode("utf-8")]
        mock_socket.return_value = ms

        clamd = clamd_class()
        # We just test response parsing here, no matter the path used:
        meth = getattr(clamd, method)
        assert meth("dummy", raw=True) == rv
        assert meth("dummy") == [
            ScanResult(
                path=Path("/path/to/file_with:/path"),
                reason="File path check failure: No such file or directory.",
                status="ERROR",
            ),
        ]


@clamd_class_param
def test_instream(clamd_class: type[ClamdNetworkSocket]):
    rv = "stream: OK"
    buffer = BytesIO(b"")
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [rv.encode("utf-8")]
        mock_socket.return_value = ms

        clamd = clamd_class()
        assert clamd.instream(buffer, raw=True) == rv
        assert clamd.instream(buffer) == ScanResult(path="stream", reason=None, status="OK")


@clamd_class_param
def test_instream_size_limit(clamd_class: type[ClamdNetworkSocket]):
    buffer = BytesIO(b"")
    with patch("socket.socket") as mock_socket:
        ms = MockSocket()
        ms.lines = [b"INSTREAM size limit exceeded ERROR"]
        mock_socket.return_value = ms

        clamd = clamd_class()

        with pytest.raises(BufferTooLongError) as excinfo:
            clamd.instream(buffer)

        assert excinfo.value.args == ("INSTREAM size limit exceeded",)
