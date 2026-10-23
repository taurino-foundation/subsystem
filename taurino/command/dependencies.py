"""Dependency injection container for Taurino commands."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from taurino.errors import CommandErrorCode, CommandException
from taurino.types import Provider, T


@dataclass(frozen=True, slots=True)
class Depends:
    """
    Explicit dependency injection marker.

    Example:
        Annotated[MyService, Depends()]
    """


class DependencyContainer:
    """Container for singleton instances and dependency providers."""

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._providers: dict[type[Any], Provider] = {}
        self._locks: dict[type[Any], asyncio.Lock] = {}

    def register_singleton(
        self,
        dep_type: type[T],
        instance: T,
    ) -> None:
        if not isinstance(instance, dep_type):
            raise TypeError(f"Expected instance of {dep_type.__name__}")

        self._singletons[dep_type] = instance

    def register_factory(
        self,
        dep_type: type[T],
        provider: Callable[[], T | Awaitable[T]],
    ) -> None:
        self._providers[dep_type] = provider
        self._singletons.pop(dep_type, None)

    async def resolve(self, dep_type: type[T]) -> T:
        existing = self._singletons.get(dep_type)

        if existing is not None:
            return cast(T, existing)

        if dep_type not in self._providers:
            raise CommandException(
                CommandErrorCode.DEPENDENCY_ERROR,
                f"No provider for {dep_type.__name__}",
            )

        lock = self._locks.setdefault(
            dep_type,
            asyncio.Lock(),
        )

        async with lock:
            if dep_type not in self._singletons:
                provided = self._providers[dep_type]()

                if inspect.isawaitable(provided):
                    provided = await provided

                if not isinstance(provided, dep_type):
                    raise CommandException(
                        CommandErrorCode.DEPENDENCY_ERROR,
                        (f"Provider returned the wrong type for {dep_type.__name__}"),
                    )

                self._singletons[dep_type] = provided

            return cast(
                T,
                self._singletons[dep_type],
            )

    def clear(self) -> None:
        self._singletons.clear()
        self._providers.clear()
        self._locks.clear()
