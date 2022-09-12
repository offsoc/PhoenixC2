"""Options for creating listeners and stagers"""
# Inspired by https://github.com/BC-SECURITY/Empire
import socket
import requests
import importlib
from dataclasses import dataclass, field
from abc import abstractmethod
from .misc import get_network_interfaces
from Creator.available import AVAILABLE_LISTENERS


@dataclass
class OptionType():
    """The base option-type"""
    data_type = any

    def validate(name: str, data: any) -> bool:
        return True


@dataclass
class StringType(OptionType):
    """The option-type of string"""
    data_type = str

    def __str__() -> str:
        return "String"


@dataclass
class IntegerType(OptionType):
    """The option-type of integer"""
    data_type = int

    def __str__() -> str:
        return "Integer"


@dataclass
class BooleanType(OptionType):
    """The option-type of boolean"""
    data_type = bool

    def __str__() -> str:
        return "Boolean"


@dataclass
class UrlType(StringType):
    """The option-type of url"""

    @staticmethod
    def validate(name: str, url: str) -> bool:
        try:
            requests.get(url)
        except requests.ConnectionError as e:
            raise requests.ConnectionError(
                f"Couldn't connect to the url for the option '{name}'.") from e
        except requests.exceptions.MissingSchema as e:
            raise requests.exceptions.MissingSchema(
                f"The url for the option '{name}' is invalid.") from e
        except requests.exceptions.InvalidURL as e:
            raise requests.exceptions.MissingSchema(
                f"The url for the option '{name}' is invalid.") from e
        else:
            return True

    def __str__() -> str:
        return "Url"


@dataclass
class AddressType(StringType):
    """The option-type of address"""

    @staticmethod
    def interface_to_address(interface: str) -> str:
        address = get_network_interfaces().get(interface)

        if address is None:
            raise ValueError(f"The interface '{interface}' doesn't exist.")
        return address

    @staticmethod
    def validate(name: str, address: str) -> bool:
        try:
            socket.gethostbyname(address)
        except socket.gaierror as e:
            raise socket.gaierror(
                f"{address} for the option '{name}' is invalid.") from e
        else:
            return True

    def __str__() -> str:
        return "Address"


@dataclass
class ChoiceType(OptionType):
    choices: field(default_factory=list)
    data_type: any

    def validate(self, name: str, choice: str) -> bool:
        if choice not in self.choices:
            raise ValueError(
                f"{choice} isn't in the available choices {self.choices} for '{name}'.)")

    def __str__(self) -> str:
        return "Choice"


@dataclass
class Option():
    """"""
    name: str
    type: OptionType
    _real_name: str = None
    description: str = ""
    required: bool = False
    default: any = None

    @property
    def real_name(self) -> str:
        if self._real_name is None:
            return self.name.lower()
        return self._real_name

    def validate_data(self, data: any) -> OptionType.data_type:
        """Raises an exception if data isn't fitting to the requirements"""
        if not data:
            if self.required and self.default is None:
                raise ValueError(f"{self.name} is required.")
            return self.default

        if type(data) != self.type.data_type:
            try:
                data = self.type.data_type(data)
            except ValueError:
                raise TypeError(
                    f"{self.name} has to be a type of '{self.type.data_type.__name__}'.")

        try:
            self.type.validate(self.name, data)
        except AttributeError:
            pass
        return data

    def to_json(self) -> dict:
        data = {
            "name": self.name,
            "real-name": self.real_name,
            "type": self.type.__str__().lower(),
            "required": self.required,
            "description": self.description,
            "default": self.default
        }
        if type(self.type) == ChoiceType:
            data["choices"] = self.type.choices
        return data


@dataclass
class OptionPool():
    """Contains all options"""
    options: list[Option] = field(default_factory=list)

    def register_option(self, option: Option):
        """Register a new option"""
        self.options.append(option)

    def validate_data(self, data: dict) -> bool:
        """Validate the data"""
        cleaned_data = {}
        for option in self.options:
            value = data.get(option.real_name, "")
            cleaned_data[option.real_name] = option.validate_data(value)
        return cleaned_data

    def to_json(self) -> list:
        return [option.to_json() for option in self.options]


def get_options(listener_type: str) -> OptionPool:
    """Get the options based on the listener type."""
    
    if listener_type not in AVAILABLE_LISTENERS:
        raise ValueError(f"'{listener_type}' isn't available.")

    try:
        open("Listeners/" + listener_type + ".py", "r").close()
    except:
        raise Exception(f"Listener {listener_type} does not exist") from None
    
    listener = importlib.import_module(
        "Listeners." + listener_type.replace("/", ".")).Listener
    return listener.option_pool