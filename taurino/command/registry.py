"""Central command registry for Taurino."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from taurino.command.models import InvokeRequest, InvokeResponse
from taurino.errors import CommandErrorCode
from taurino.hooks import CommandHooks, invoke_hook
from taurino.types import AfterHook, BeforeHook, CommandFn

from .compiler import CommandCompiler, CompiledCommand
from .dependencies import DependencyContainer
from .dispatcher import CommandDispatcher

if TYPE_CHECKING:
    from taurino.app.handle import AppHandle


class CommandRegistry:
    """
    Internal command registry.

    Manages registration and delegates compilation,
    validation, dependency resolution and execution
    to dedicated components.

    Does not depend on IPC or the Multiplexer.
    """

    def __init__(
        self,
        *,
        container: DependencyContainer | None = None,
        debug: bool = False,
        enable_tracing: bool = True,
    ) -> None:
        self._app_handle: AppHandle | None = None

        self._handlers: dict[str, CompiledCommand] = {}
        self._registered_keys: set[str] = set()

        self.container = container if container is not None else DependencyContainer()

        self._hooks = CommandHooks()

        # Retain the original internal hook lists.
        self._before = self._hooks.before_hooks
        self._after = self._hooks.after_hooks

        self._debug = debug
        self._enable_tracing = enable_tracing

        self._dispatcher = CommandDispatcher(
            handlers=self._handlers,
            container=self.container,
            hooks=self._hooks,
            debug=debug,
            enable_tracing=enable_tracing,
        )

    def bind(self, app_handle: AppHandle) -> None:
        """Bind the application handle once."""

        if self._app_handle is not None:
            raise RuntimeError("CommandRegistry already bound")

        self._dispatcher.bind(app_handle)
        self._app_handle = app_handle

    def before(
        self,
        hook: BeforeHook,
    ) -> BeforeHook:
        """Register a before-execution hook."""

        return self._hooks.before(hook)

    def after(
        self,
        hook: AfterHook,
    ) -> AfterHook:
        """Register an after-execution hook."""

        return self._hooks.after(hook)

    def command(
        self,
        name: str | None = None,
    ) -> Callable[[CommandFn], CommandFn]:
        """Decorator for registering a command."""

        def decorator(func: CommandFn) -> CommandFn:
            self.register(
                name if name is not None else func.__name__,
                func,
            )

            return func

        return decorator

    def register(
        self,
        name: str,
        func: CommandFn,
    ) -> None:
        """Compile and register a command handler."""

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Command name must be a non-empty string")

        if name.startswith("taurino."):
            raise ValueError("The 'taurino.' namespace is reserved")

        if name in self._registered_keys:
            raise ValueError(f"Duplicate command: {name}")

        # Compile before modifying registry state.
        compiled = self._compile(func)

        self._handlers[name] = compiled
        self._registered_keys.add(name)

    def registered_keys(self) -> set[str]:
        """Return a copy of all registered command names."""

        return self._registered_keys.copy()

    def is_registered(self, name: str) -> bool:
        """Check whether a command exists."""

        return name in self._registered_keys

    def list_commands(self) -> list[str]:
        """Return sorted registered command names."""

        return sorted(self._registered_keys)

    def describe(self) -> dict[str, Any]:
        """Describe registered command metadata."""

        return {
            name: {
                "handler": (f"{compiled.func.__module__}.{compiled.func.__qualname__}"),
                "async": inspect.iscoroutinefunction(compiled.func),
                "params": (list(compiled.validator.model_fields) if compiled.validator is not None else []),
                "injected": list(compiled.injections),
            }
            for name, compiled in self._handlers.items()
        }

    @staticmethod
    def _compile(func: CommandFn) -> CompiledCommand:
        """Compile a command using CommandCompiler."""

        return CommandCompiler.compile(func)

    async def dispatch(
        self,
        request: InvokeRequest | Mapping[str, Any],
    ) -> InvokeResponse:
        """Execute a registered command."""

        return await self._dispatcher.dispatch(request)

    @staticmethod
    async def _invoke_hook(
        func: Callable[..., Any],
        *args: Any,
    ) -> None:
        """Backward-compatible internal hook executor."""

        await invoke_hook(func, *args)

    @staticmethod
    def _error_response(
        code: CommandErrorCode,
        message: str,
        details: Any = None,
    ) -> InvokeResponse:
        """Create a standardized command error response."""

        return CommandDispatcher._error_response(
            code,
            message,
            details,
        )

    def close(self) -> None:
        """Clear registry state and release references."""

        self.container.clear()

        self._handlers.clear()
        self._registered_keys.clear()

        self._hooks.clear()
        self._dispatcher.close()

        self._app_handle = None
