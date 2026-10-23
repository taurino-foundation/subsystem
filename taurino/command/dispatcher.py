"""Asynchronous command dispatcher for Taurino."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from pydantic_core import to_jsonable_python

from taurino.command.models import InvokeRequest, InvokeResponse
from taurino.errors import CommandErrorCode, CommandException
from taurino.hooks import CommandHooks

if TYPE_CHECKING:
    from taurino.app.handle import AppHandle
    from taurino.command.compiler import CompiledCommand
    from taurino.command.dependencies import DependencyContainer


log = logging.getLogger(__name__)


class CommandDispatcher:
    """Execute registered commands independently of IPC transport."""

    def __init__(
        self,
        *,
        handlers: dict[str, CompiledCommand],
        container: DependencyContainer,
        hooks: CommandHooks,
        debug: bool = False,
        enable_tracing: bool = True,
    ) -> None:
        self._handlers = handlers
        self._container = container
        self._hooks = hooks
        self._app_handle: AppHandle | None = None
        self._debug = debug
        self._enable_tracing = enable_tracing

    def bind(self, app_handle: AppHandle) -> None:
        if self._app_handle is not None:
            raise RuntimeError("CommandRegistry already bound")

        self._app_handle = app_handle

    async def dispatch(
        self,
        request: InvokeRequest | Mapping[str, Any],
    ) -> InvokeResponse:
        """
        Execute a command and return a transport-neutral response.

        Malformed request envelopes must be handled by the transport.
        Valid requests always produce a response.
        """

        if not isinstance(request, InvokeRequest):
            request = InvokeRequest.model_validate(request)

        started = time.perf_counter()

        payload: dict[str, Any] = {}
        response: InvokeResponse

        try:
            if request.payload is None:
                payload = {}

            elif isinstance(request.payload, dict):
                payload = request.payload

            else:
                raise CommandException(
                    CommandErrorCode.INVALID_PARAMS,
                    "Invoke payload must be a JSON object or null",
                )

            command = self._handlers.get(request.cmd)

            if command is None:
                raise CommandException(
                    CommandErrorCode.NO_HANDLER,
                    f"No command registered as '{request.cmd}'",
                )

            await self._hooks.run_before(
                request.cmd,
                payload,
            )

            if command.validator is None:
                if payload:
                    raise CommandException(
                        CommandErrorCode.INVALID_PARAMS,
                        "This command accepts no payload parameters",
                    )

                bound: dict[str, Any] = {}

            else:
                try:
                    validated = command.validator.model_validate(payload)

                except ValidationError as exc:
                    raise CommandException(
                        CommandErrorCode.VALIDATION_ERROR,
                        "Command payload validation failed",
                        exc.errors(
                            include_input=False,
                            include_url=False,
                        ),
                    ) from exc

                bound = {name: getattr(validated, name) for name in command.validator.model_fields}

            for name, dep_type in command.injections.items():
                if dep_type is None:
                    if self._app_handle is None:
                        raise CommandException(
                            CommandErrorCode.INTERNAL_ERROR,
                            "AppHandle is not bound",
                        )

                    bound[name] = self._app_handle

                else:
                    bound[name] = await self._container.resolve(dep_type)

            if inspect.iscoroutinefunction(command.func):
                value = await command.func(**bound)

            else:
                # Run synchronous handlers outside the IPC event loop.
                value = await asyncio.to_thread(
                    command.func,
                    **bound,
                )

                if inspect.isawaitable(value):
                    value = await value

            response = InvokeResponse(
                ok=True,
                data=to_jsonable_python(value),
            )

        except CommandException as exc:
            response = self._error_response(
                exc.code,
                exc.message,
                exc.details,
            )

        except Exception as exc:
            log.exception(
                "Command '%s' failed",
                request.cmd,
            )

            response = self._error_response(
                CommandErrorCode.EXECUTION_ERROR,
                "Command execution failed",
                str(exc) if self._debug else None,
            )

        if self._enable_tracing:
            log.debug(
                "Command '%s' completed (ok=%s, elapsed_ms=%.3f)",
                request.cmd,
                response.ok,
                (time.perf_counter() - started) * 1000,
            )

        await self._hooks.run_after(
            request.cmd,
            payload,
            response.model_dump(mode="json"),
        )

        return response

    @staticmethod
    def _error_response(
        code: CommandErrorCode,
        message: str,
        details: Any = None,
    ) -> InvokeResponse:
        return InvokeResponse(
            ok=False,
            data={
                "code": code.value,
                "message": message,
                "details": to_jsonable_python(details),
            },
        )

    def close(self) -> None:
        self._app_handle = None
