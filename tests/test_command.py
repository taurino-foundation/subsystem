from __future__ import annotations

from typing import Annotated

import msgpack
import pytest

from taurino.command import (
    CommandErrorCode,
    CommandRegistry,
    DependencyContainer,
    Depends,
    InvokeRequest,
)


class Service:
    def get_value(self) -> str:
        return "Dependency OK"


def make_request(
    cmd: str,
    payload: object = None,
) -> InvokeRequest:
    return InvokeRequest(
        cmd=cmd,
        callback=1,
        error=2,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_async_command():
    registry = CommandRegistry()

    @registry.command()
    async def greet(name: str) -> str:
        return f"Hello, {name}!"

    response = await registry.dispatch(make_request("greet", {"name": "Taurino"}))

    assert response.ok is True
    assert response.data == "Hello, Taurino!"

    registry.close()


@pytest.mark.asyncio
async def test_sync_command():
    registry = CommandRegistry()

    @registry.command()
    def add(a: int, b: int) -> int:
        return a + b

    response = await registry.dispatch(make_request("add", {"a": 10, "b": 20}))

    assert response.ok is True
    assert response.data == 30

    registry.close()


@pytest.mark.asyncio
async def test_command_not_found():
    registry = CommandRegistry()

    response = await registry.dispatch(make_request("unknown"))

    assert response.ok is False
    assert response.data["code"] == CommandErrorCode.NO_HANDLER

    registry.close()


@pytest.mark.asyncio
async def test_validation_error():
    registry = CommandRegistry()

    @registry.command()
    def multiply(a: int, b: int) -> int:
        return a * b

    response = await registry.dispatch(
        make_request(
            "multiply",
            {"a": "invalid", "b": 5},
        )
    )

    assert response.ok is False
    assert response.data["code"] == CommandErrorCode.VALIDATION_ERROR

    registry.close()


@pytest.mark.asyncio
async def test_camel_case_arguments():
    registry = CommandRegistry()

    @registry.command()
    def get_user(user_name: str) -> str:
        return user_name

    response = await registry.dispatch(
        make_request(
            "get_user",
            {"userName": "Taurino"},
        )
    )

    assert response.ok is True
    assert response.data == "Taurino"

    registry.close()


@pytest.mark.asyncio
async def test_dependency_injection():

    container = DependencyContainer()
    container.register_singleton(Service, Service())

    registry = CommandRegistry(container=container)

    @registry.command()
    def get_service(
        service: Annotated[Service, Depends()],
    ) -> str:
        return service.get_value()

    response = await registry.dispatch(make_request("get_service"))

    assert response.ok is True
    assert response.data == "Dependency OK"

    registry.close()


@pytest.mark.asyncio
async def test_hooks():
    registry = CommandRegistry()
    events = []

    @registry.before
    async def before(cmd, payload):
        events.append("before")

    @registry.after
    async def after(cmd, payload, response):
        events.append("after")

    @registry.command()
    async def execute():
        events.append("execute")
        return True

    response = await registry.dispatch(make_request("execute"))

    assert response.ok is True
    assert events == ["before", "execute", "after"]

    registry.close()


@pytest.mark.asyncio
async def test_messagepack_serialization():
    registry = CommandRegistry()

    @registry.command()
    async def get_data():
        return {"name": "Taurino", "version": 1}

    response = await registry.dispatch(make_request("get_data"))

    packed = response.to_bytes()
    unpacked = msgpack.unpackb(packed, raw=False)

    assert isinstance(packed, bytes)
    assert unpacked["ok"] is True
    assert unpacked["data"]["name"] == "Taurino"

    registry.close()


@pytest.mark.asyncio
async def test_duplicate_command():
    registry = CommandRegistry()

    @registry.command("test")
    def first():
        return 1

    with pytest.raises(ValueError):
        registry.register("test", lambda: 2)

    registry.close()


@pytest.mark.asyncio
async def test_close():
    registry = CommandRegistry()

    @registry.command()
    def ping():
        return "pong"

    assert registry.is_registered("ping")

    registry.close()

    assert registry.list_commands() == []
