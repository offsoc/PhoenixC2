from phoenix_framework.server.database import DeviceModel
from phoenix_framework.server.utils.options import OptionPool
from abc import ABC, abstractmethod

"""The base module class"""


class BaseModule(ABC):
    """This is the Base Class for all Modules."""

    name: str = "BaseModule"
    description: str = "This is the Base Class for all Modules."
    author: str = "Screamz2k"
    language: str = "python"
    os: list[str] = ["linux", "windows", "osx"]
    options = OptionPool()
    stagers: list[str] = []
    admin: bool = False
    # execution types:
    # - code - execute the code directly
    # - shellcode - execute the code as shellcode
    # - file - execute the code as an external file
    execution_type: str = "code"

    @classmethod
    @abstractmethod
    def code(cls, device: DeviceModel) -> str | bytes:
        """The code to be executed"""
        pass

    @classmethod
    def to_dict(cls) -> dict:
        return {
            "name": cls.name,
            "description": cls.description,
            "author": cls.author,
            "language": cls.language,
            "os": cls.os,
            "options": cls.options.to_dict(),
            "stagers": cls.stagers,
            "admin": cls.admin,
            "execution_type": cls.execution_type,
        }

    @classmethod
    @abstractmethod
    def finish(cls, data: str | bytes):
        """This function is called when the module is finished"""
        pass