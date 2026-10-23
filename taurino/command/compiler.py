"""Command signature compilation and validation."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    create_model,
)

from ..types import CommandFn, InjectionMap
from .dependencies import Depends


@dataclass(frozen=True, slots=True)
class CompiledCommand:
    """Compiled command metadata.

    Attributes:
        func:
            Original Python command handler.

        validator:
            Pydantic model used for argument validation.
            None when the command has no user-provided arguments.

        injections:
            Dependency injection mapping.
            A value of None represents AppHandle.
    """

    func: CommandFn
    validator: type[BaseModel] | None
    injections: InjectionMap


class CommandCompiler:
    """Compile Python command functions into validated handlers."""

    @staticmethod
    def compile(
        func: CommandFn,
        *,
        localns: Mapping[str, Any] | None = None,
    ) -> CompiledCommand:
        """Compile a command handler.

        Args:
            func:
                Python function to compile.

            localns:
                Optional namespace used to resolve annotations
                referring to locally defined classes.

        Returns:
            Compiled command metadata.

        Raises:
            TypeError:
                If the command signature or an injection
                declaration is invalid.

            NameError:
                If a forward-referenced annotation cannot
                be resolved.
        """
        from taurino.app.handle import AppHandle

        if not callable(func):
            raise TypeError("Command handler must be callable")

        signature = inspect.signature(func)

        # Resolve postponed annotations and preserve Annotated metadata.
        # Local classes require an explicitly supplied namespace.
        hints = get_type_hints(
            func,
            globalns=func.__globals__,
            localns=dict(localns) if localns is not None else None,
            include_extras=True,
        )

        fields: dict[str, Any] = {}
        injections: InjectionMap = {}

        for name, parameter in signature.parameters.items():
            if parameter.kind not in (
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                raise TypeError("Commands only accept named arguments, not positional-only, *args or **kwargs")

            hinted = hints.get(name, Any)
            dependency = False

            # Resolve Annotated[T, Depends()] injection metadata.
            if get_origin(hinted) is Annotated:
                base, *annotations = get_args(hinted)

                dependency = any(isinstance(metadata, Depends) for metadata in annotations)

                hinted = base

            # Handle injected parameters.
            if hinted is AppHandle or dependency:
                if parameter.default is not inspect.Parameter.empty:
                    raise TypeError(f"Injected parameter '{name}' cannot have a default")

                if hinted is AppHandle:
                    injections[name] = None

                elif isinstance(hinted, type):
                    injections[name] = hinted

                else:
                    raise TypeError(f"Depends requires a concrete class for '{name}'")

                continue

            # Accept both Python snake_case and JavaScript camelCase.
            parts = name.split("_")

            camel_name = parts[0] + "".join(part.capitalize() for part in parts[1:])

            default = ... if parameter.default is inspect.Parameter.empty else parameter.default

            if camel_name != name:
                fields[name] = (
                    hinted,
                    Field(
                        default=default,
                        validation_alias=AliasChoices(
                            name,
                            camel_name,
                        ),
                    ),
                )

            else:
                fields[name] = (
                    hinted,
                    default,
                )

        # Build a Pydantic validator only when user arguments exist.
        validator = (
            create_model(
                f"Command_{func.__name__}_Params",
                __config__=ConfigDict(
                    extra="forbid",
                ),
                **fields,
            )
            if fields
            else None
        )

        return CompiledCommand(
            func=func,
            validator=validator,
            injections=injections,
        )
