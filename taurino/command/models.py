"""Request, response, and envelope models for Taurino commands."""

from __future__ import annotations

from typing import Annotated, Any, Self

import msgpack
from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import JsonValue

UInt32 = Annotated[
    int,
    Field(
        strict=True,
        ge=0,
        le=0xFFFF_FFFF,
    ),
]


class InvokeRequest(BaseModel):
    """
    JavaScript -> Rust -> Python.

    Field names match the Rust InvokeRequest.
    """

    model_config = ConfigDict(
        extra="ignore",
        strict=True,
    )

    cmd: str
    callback: UInt32
    error: UInt32
    payload: JsonValue = None
    options: JsonValue | None = None

    @classmethod
    def from_any(cls, data: Any) -> Self:
        return cls.model_validate(data)


class InvokeResponse(BaseModel):
    """
    Python -> Rust.

    Rust uses the callback/error IDs from the original request.

    The data field is passed directly to the JavaScript
    callback without requiring another RPC envelope.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    ok: bool
    data: JsonValue

    def to_bytes(self) -> bytes:
        packed = msgpack.packb(
            self.model_dump(mode="json"),
            use_bin_type=True,
        )

        if not isinstance(packed, bytes):
            raise TypeError("MessagePack serialization must return bytes")

        return packed


class CommandEnvelope(BaseModel):
    """
    Transport envelope containing the invocation context.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    cmd: str
    window_label: str = Field(min_length=1)
    webview_label: str = Field(min_length=1)
    request: InvokeRequest
