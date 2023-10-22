from os import PathLike
from typing import Protocol, TypeVar, Union

_T_co = TypeVar("_T_co", covariant=True)


# Taken from _typeshed/__init__.pyi
class SupportsRead(Protocol[_T_co]):
    def read(self, __length: int = ...) -> _T_co:
        ...


# Taken from _typeshed/__init__.pyi
StrPath = Union[str, "PathLike[str]"]
