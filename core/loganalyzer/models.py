from typing import Literal

from pydantic import BaseModel, IPvAnyAddress


class Event(BaseModel):
    ts: int
    source: Literal["auth", "nginx"]
    ip: IPvAnyAddress
    user: str | None
    event_type: Literal[
        "ssh_failed", "ssh_accepted", "ssh_invalid_user", "http_request"
    ]
    raw: str
    path: str | None = None
    status: int | None = None
