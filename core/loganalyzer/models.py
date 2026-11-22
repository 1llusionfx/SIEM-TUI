from typing import Literal

from pydantic import BaseModel, IPvAnyAddress


class Event(BaseModel):
    ts: int
    source: Literal["auth"]
    ip: IPvAnyAddress
    user: str | None
    event_type: Literal["ssh_failed", "ssh_accepted", "ssh_invalid_user"]
    raw: str
