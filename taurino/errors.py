"""Public errors and protocol exceptions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class TaurinoError(Exception):
    """Base error for this package."""


class StateAlreadyExistsError(TaurinoError):
    pass


class StateNotFoundError(TaurinoError):
    pass


class ProtocolError(TaurinoError):
    pass


class MultiplexerClosedError(TaurinoError):
    pass


class RequestIdsExhausted(TaurinoError):
    pass


class RuntimeStartError(TaurinoError):
    pass


class RuntimeStateError(TaurinoError):
    pass


class AppLifecycleError(TaurinoError):
    pass


class CommandErrorCode(StrEnum):
    NO_HANDLER = "NO_HANDLER"
    INVALID_PARAMS = "INVALID_PARAMS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CommandException(TaurinoError):
    """Exception raised during command processing."""

    def __init__(
        self,
        code: CommandErrorCode,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.message = message
        self.details = details
