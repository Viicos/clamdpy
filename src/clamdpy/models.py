from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from .exceptions import ResponseError

# TODO Be able to match `:` in path names
RESULT_REGEX = re.compile(r"^(?P<path>[^:]*): ((?P<reason>.+) )?(?P<status>(FOUND|OK|ERROR))$")


class VersionInfo(NamedTuple):
    """A tuple containing info about the current ClamAV version."""

    version: str
    signature: int
    signature_date: datetime

    @classmethod
    def _from_str(cls, string: str) -> VersionInfo:
        splitted = string.split("/")
        return cls(
            version=splitted[0],
            signature=int(splitted[1]),
            # TODO parsing currently depends on the current locale
            signature_date=datetime.strptime(splitted[2], "%a %b %d %H:%M:%S %Y"),
        )


class ScanResult(NamedTuple):
    """A tuple containing info about the result of a scan."""

    path: Path | Literal["stream"]
    """The path of the file/directory scanned. If a stream was used instead,
    it will take the value of the literal `stream`.
    """

    reason: str | None
    """Depending on the status:
    - `FOUND`: reason will be the description of the virus.
    - `OK`: reason will always be `None`.
    - `ERROR`: reason will describe the encountered error.
    """
    status: Literal["FOUND", "OK", "ERROR"]
    """The status of the scan."""

    @classmethod
    def _from_str(cls, string: str, command: str, stream: bool = False) -> ScanResult:
        match = RESULT_REGEX.match(string)
        if match is None:
            raise ResponseError(command, f"Unable to match string: {string}")
        groups: tuple[str, str | None, Literal["FOUND", "OK", "ERROR"]] = match.group(  # type: ignore[assignment]
            "path", "reason", "status"
        )
        return cls(
            path="stream" if stream else Path(groups[0]),
            reason=groups[1],
            status=groups[2],
        )
