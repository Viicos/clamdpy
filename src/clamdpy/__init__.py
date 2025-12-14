from importlib.metadata import version

from .sockets import ClamdNetworkSocket, ClamdUnixSocket

__version__ = version("clamdpy")

__all__ = ("ClamdNetworkSocket", "ClamdUnixSocket")
