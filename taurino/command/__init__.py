"""Taurino command system public API."""

from __future__ import annotations

from taurino.command.compiler import CommandCompiler, CompiledCommand
from taurino.command.dependencies import DependencyContainer, Depends
from taurino.command.dispatcher import CommandDispatcher
from taurino.command.models import (
    CommandEnvelope,
    InvokeRequest,
    InvokeResponse,
    UInt32,
)
from taurino.command.registry import CommandRegistry
from taurino.errors import CommandErrorCode, CommandException
from taurino.hooks import CommandHooks
from taurino.types import (
    AfterHook,
    BeforeHook,
    CommandFn,
    Provider,
)

__all__ = [
    # Public registry
    "CommandRegistry",
    # Request and response models
    "InvokeRequest",
    "InvokeResponse",
    "CommandEnvelope",
    "UInt32",
    # Errors
    "CommandErrorCode",
    "CommandException",
    # Dependency injection
    "Depends",
    "DependencyContainer",
    # Command compilation
    "CommandCompiler",
    "CompiledCommand",
    # Execution
    "CommandDispatcher",
    # Hooks
    "CommandHooks",
    # Types
    "CommandFn",
    "Provider",
    "BeforeHook",
    "AfterHook",
]
