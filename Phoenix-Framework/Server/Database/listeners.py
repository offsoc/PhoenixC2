"""The Listeners Model"""
import importlib
import json
from typing import TYPE_CHECKING

from Creator.available import AVAILABLE_LISTENERS
from sqlalchemy import JSON, Boolean, Column, Integer, String
from sqlalchemy.orm import Session, relationship

from .base import Base

if TYPE_CHECKING:
    from Commander import Commander
    from Listeners.base import BaseListener
    from Utils.options import OptionPool

    from .devices import DeviceModel
    from .stagers import StagerModel


class ListenerModel(Base):
    """The Listeners Model"""
    __tablename__ = "Listeners"
    id: int = Column(
        Integer, primary_key=True, nullable=False)
    name: str = Column(String(100))
    type: str = Column(String(100))
    address: str = Column(String(15))
    port: int = Column(Integer)
    ssl: bool = Column(Boolean)
    enabled: bool = Column(Boolean, default=True)
    limit = Column(Integer, name="limit")
    options: dict = Column(JSON, default=[])
    stagers: list["StagerModel"] = relationship(
        "StagerModel",
        back_populates="listener")
    devices: list["DeviceModel"] = relationship(
        "DeviceModel",
        back_populates="listener"
    )

    def is_active(self, commander: "Commander" = None) -> bool|str:
        """Returns True if listeners is active, else False"""
        try:
            if commander is None:
                return "Unknown"
            commander.get_active_listener(self.id)
        except KeyError:
            return False
        else:
            return True

    def to_dict(self, commander: "Commander", show_stagers: bool = True, show_devices: bool = True) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "address": self.address,
            "port": self.port,
            "ssl": self.ssl,
            "enabled": self.enabled,
            "limit": self.limit,
            "active": self.is_active(commander),
            "options": self.options,
            "stagers": [stager.to_dict(commander, show_listener=False)
                        for stager in self.stagers] if show_stagers
            else [stager.id for stager in self.stagers],
            "devices": [device.to_dict(commander, show_listener=False)
                        for device in self.devices] if show_devices
            else [device.id for device in self.devices]
        }

    def to_json(self, commander: "Commander", show_stagers: bool = True, show_devices: bool = True) -> str:
        """Return a JSON string"""
        return json.dumps(self.to_dict(commander, show_stagers, show_devices))

    def delete_stagers(self, session: Session):
        """Delete all stagers"""
        for stager in self.stagers:
            session.delete(stager)

    def create_listener_object(self, commander: "Commander") -> "BaseListener":
        """Create the Listener Object"""
        return importlib.import_module("Listeners." + self.type.replace("/", ".")).Listener(
            commander, self)

    @staticmethod
    def get_all_options(commander: "Commander") -> dict:
        """Get all options for all listener types"""
        options: dict = {}
        for listener in AVAILABLE_LISTENERS:
            options[listener] = ListenerModel.get_options_from_type(
                listener).to_dict(commander)
        return options

    def get_options(self) -> "OptionPool":
        """Get the options using the type the current object."""

        if self.type not in AVAILABLE_LISTENERS:
            raise ValueError(f"'{self.type}' isn't available.")

        try:
            open("Listeners/" + self.type + ".py", "r").close()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Listener {self.type} does not exist") from e
        listener: "BaseListener" = importlib.import_module(
            "Listeners." + self.type.replace("/", ".")).Listener
        return listener.listener_pool

    @staticmethod
    def get_options_from_type(type: str) -> "OptionPool":
        """Get the options based on the listener type."""

        if type not in AVAILABLE_LISTENERS:
            raise ValueError(f"'{type}' isn't available.")

        try:
            open("Listeners/" + type + ".py", "r").close()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Listener {type} does not exist") from e

        listener: "BaseListener" = importlib.import_module(
            "Listeners." + type.replace("/", ".")).Listener
        return listener.listener_pool

    def edit(self, data: dict):
        """Edit the listener"""
        for key, value in data.items():
            if hasattr(self, key):
                if value == str(getattr(self, key)):
                    continue
                value = self.get_options().get_option(key).validate_data(value)
                setattr(self, key, value)
            else:
                if key in self.options:
                    if value == self.options[key]:
                        continue
                    value = self.get_options().get_option(key).validate_data(value)
                    self.options[key] = value
                else:
                    raise KeyError(f"{key} is not a valid key")

    @staticmethod
    def create_listener_from_data(data: dict):
        """Create the stager using listener validated data"""
        standard = []
        # gets standard values present in every listener and remove them to only leave options
        for st_value in ["name", "type", "address", "port", "ssl", "limit", "enabled"]:
            standard.append(data.pop(st_value))
        return ListenerModel(
            name=standard[0],
            type=standard[1],
            address=standard[2],
            port=standard[3],
            ssl=standard[4],
            limit=standard[5],
            enabled=standard[6],
            options=data
        )
