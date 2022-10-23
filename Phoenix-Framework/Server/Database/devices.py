"""The Devices Model"""
import json
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid1

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from .base import Base

if TYPE_CHECKING:
    from Commander import Commander

    from Server.Kits.base_listener import BaseListener

    from .listeners import ListenerModel
    from .tasks import TaskModel


class DeviceModel(Base):
    """The Devices Model"""
    __tablename__ = "Devices"
    id: int = Column(Integer, primary_key=True, nullable=False)
    name: str = Column(String, unique=True, nullable=False)
    hostname: str = Column(String(100))
    address: str = Column(String(100), nullable=False)
    os: str = Column(String(10))
    user: str = Column(String(100))
    infos: dict = Column(MutableDict.as_mutable(JSON), default={})
    connection_date: datetime = Column(DateTime)
    last_online: datetime = Column(DateTime)
    listener_id: int = Column(Integer, ForeignKey("Listeners.id"))
    listener: "ListenerModel" = relationship(
        "ListenerModel", back_populates="devices")
    tasks: list["TaskModel"] = relationship(
        "TaskModel",
        back_populates="device")
    

    @property
    def connected(self):
        return (datetime.now() - self.last_online).seconds < 10

    def to_dict(self, commander: "Commander", show_listener: bool = True, show_tasks: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "hostname": self.hostname,
            "address": self.address,
            "os": self.os,
            "user": self.user,
            "infos": self.infos,
            "connection_date": self.connection_date,
            "last_online": self.last_online,
            "listener": self.listener.to_dict(commander, show_devices=False) if show_listener else self.listener_id,
            "tasks": [task.to_dict(commander, show_device=False)
                      for task in self.tasks] if show_tasks
            else [task.id for task in self.tasks]
        }
        try:
            if commander is None:
                data["connected"] = "Unknown"
            else:
                commander.get_active_handler(self.id)
        except KeyError:
            data["connected"] = False
        else:
            data["connected"] = True
        return data

    def to_json(self, commander: "Commander", show_listener: bool = True, show_tasks: bool = True) -> str:
        """Return a JSON string"""
        return json.dumps(self.to_dict(commander, show_listener, show_tasks))

    @classmethod
    def generate_device(cls, listener: "BaseListener", hostname: str, address: str, os: str, user: str) -> "ListenerModel":
        return cls(
            name=str(uuid1()).split("-")[0],
            hostname=hostname,
            address=address,
            os=os,
            user=user,
            connection_date=datetime.now(),
            last_online=datetime.now(),
            listener=listener.db_entry
        )
