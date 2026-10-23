"""Lifecycle hooks for Taurino commands."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from .types import AfterHook, BeforeHook

log = logging.getLogger(__name__)


async def invoke_hook(
    func: Callable[..., Any],
    *args: Any,
) -> None:
    """Execute synchronous or asynchronous hooks."""

    if inspect.iscoroutinefunction(func):
        await func(*args)

    else:
        value = await asyncio.to_thread(
            func,
            *args,
        )

        if inspect.isawaitable(value):
            await value


class CommandHooks:
    """Manage command lifecycle hooks."""

    def __init__(self) -> None:
        self._before: list[BeforeHook] = []
        self._after: list[AfterHook] = []

    @property
    def before_hooks(self) -> list[BeforeHook]:
        return self._before

    @property
    def after_hooks(self) -> list[AfterHook]:
        return self._after

    def before(
        self,
        hook: BeforeHook,
    ) -> BeforeHook:
        self._before.append(hook)
        return hook

    def after(
        self,
        hook: AfterHook,
    ) -> AfterHook:
        self._after.append(hook)
        return hook

    async def run_before(
        self,
        command: str,
        payload: dict[str, Any],
    ) -> None:
        for hook in self._before:
            await invoke_hook(
                hook,
                command,
                payload,
            )

    async def run_after(
        self,
        command: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        for hook in self._after:
            try:
                await invoke_hook(
                    hook,
                    command,
                    payload,
                    response,
                )

            except Exception:
                log.exception("Command after-hook failed")

    def clear(self) -> None:
        self._before.clear()
        self._after.clear()
