"""Shared type definitions for the Taurino command system."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

CommandFn = Callable[..., Any]

Provider = Callable[[], Any | Awaitable[Any]]

BeforeHook = Callable[
    [str, dict[str, Any]],
    Any,
]

AfterHook = Callable[
    [str, dict[str, Any], dict[str, Any]],
    Any,
]

CommandValidator = type[BaseModel]

InjectionMap = dict[str, type[Any] | None]
