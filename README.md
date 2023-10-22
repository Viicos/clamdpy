# clamdpy

A Python wrapper around `clamd`, the [ClamAV](https://www.clamav.net/) daemon.

This is a maintained and updated fork of https://github.com/graingert/python-clamd/, credit goes to the original developer(s).

[![Python versions](https://img.shields.io/pypi/pyversions/clamdpy.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/clamdpy.svg)](https://pypi.org/project/clamdpy/)
[![Code style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Installation

Using `pip`:

```sh
pip install clamdpy
```

## Usage

```python
from io import BytesIO

from clamdpy import ClamdNetworkSocket

clamd = ClamdNetworkSocket(
    host="127.0.0.1",
    port=3310,
    timeout=15,
)

clamd.ping()
#> 'PONG'

clamd.version()
#> VersionInfo(version='ClamAV 0.103.9', signature=27065, signature_date=datetime(2023, 10, 18, 9, 49, 14))

# Raw response can be fetched as well:
clamd.version(raw=True)
#> 'ClamAV 0.103.9/27065/Wed Oct 18 09:49:14 2023'

clamd.instream(BytesIO(b"data"))
#> ScanResult(path='stream', reason=None, status='OK')
```

Most of the [clamd commands](https://github.com/Cisco-Talos/clamav/blob/main/docs/man/clamd.8.in) are implemented (a couple ones are missing and should be implemented sooner or later).

It is possible to use [UNIX sockets](https://docs.python.org/3/library/socket.html#socket.AF_UNIX) as well:

```python
from clamdpy import ClamdUnixSocket

clamd = ClamdUnixSocket(path="/var/run/clamav/clamd.ctl")
```

### Line delimitations

By default, `\n` will be used to terminate lines. Clamd also supports `NULL` characters:

```python
from clamdpy import ClamdNetworkSocket

clamd = ClamdNetworkSocket(line_terminator="z")
```

> [!WARNING]\
> Support for the `NULL` character isn't tested and may not work as it doesn't play well with Python. Use with caution.
