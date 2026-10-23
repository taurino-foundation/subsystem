"""Tests for the Taurino GUI process lifecycle.

Test the real Runtime controller without launching a native GUI window.

Run:
    uv run pytest tests/test_runtime.py -v
"""

from __future__ import annotations

import importlib
import multiprocessing as mp
from unittest.mock import MagicMock

import pytest

from taurino.errors import RuntimeStartError, RuntimeStateError
from taurino.runtime import Runtime

# Import the actual module containing Runtime and _gui_process_entry.
runtime_module = importlib.import_module(Runtime.__module__)


@pytest.fixture
def controller():
    """Create a Runtime instance and ensure resource cleanup."""
    instance = Runtime(
        config=b"test-config",
        name="taurino-test",
        start_timeout=1.0,
        stop_timeout=0.1,
        method="spawn",
    )

    yield instance

    instance.close()


@pytest.fixture
def mock_process():
    """Simulate a multiprocessing child process."""
    process = MagicMock()
    process.pid = 12345
    process.exitcode = None
    process.is_alive.return_value = True
    return process


@pytest.fixture
def mock_connection():
    """Simulate the parent side of the status pipe."""
    connection = MagicMock()
    connection.poll.return_value = True
    connection.recv.return_value = ("ready", None)
    return connection


class TestInitialization:
    def test_valid_configuration(self, controller):
        assert controller._config == b"test-config"
        assert controller._name == "taurino-test"
        assert controller._start_timeout == 1.0
        assert controller._stop_timeout == 0.1

    def test_spawn_context(self, controller):
        assert controller._context.get_start_method() == "spawn"

    def test_invalid_config(self):
        with pytest.raises(TypeError):
            Runtime(config="not-bytes")

    @pytest.mark.parametrize("timeout", [0, -1, -10])
    def test_invalid_start_timeout(self, timeout):
        with pytest.raises(ValueError):
            Runtime(b"config", start_timeout=timeout)

    @pytest.mark.parametrize("timeout", [-1, -10])
    def test_invalid_stop_timeout(self, timeout):
        with pytest.raises(ValueError):
            Runtime(b"config", stop_timeout=timeout)

    def test_initial_state(self, controller):
        assert controller.pid is None
        assert controller.exitcode is None
        assert controller.is_running is False
        assert controller.is_stopping is False


class TestProperties:
    def test_pid(self, controller, mock_process):
        controller._process = mock_process
        assert controller.pid == 12345

    def test_exitcode(self, controller, mock_process):
        mock_process.exitcode = 0
        controller._process = mock_process

        assert controller.exitcode == 0

    def test_is_running(self, controller, mock_process):
        controller._process = mock_process
        assert controller.is_running is True

        mock_process.is_alive.return_value = False
        assert controller.is_running is False

    def test_is_stopping(self, controller, mock_process):
        controller._process = mock_process

        assert controller.is_stopping is False

        controller._shutdown_event.set()
        assert controller.is_stopping is True


class TestStart:
    def test_start_success(self, controller, monkeypatch):
        """Check process creation, readiness and pipe ownership."""
        process = MagicMock()
        process.is_alive.return_value = True

        parent = MagicMock()
        parent.poll.return_value = True
        parent.recv.return_value = ("ready", None)

        child = MagicMock()

        context = MagicMock()
        context.Event.side_effect = lambda: mp.get_context("spawn").Event()
        context.Pipe.return_value = (parent, child)
        context.Process.return_value = process

        monkeypatch.setattr(controller, "_context", context)

        controller.start()

        context.Process.assert_called_once()
        process.start.assert_called_once()
        child.close.assert_called_once()

        kwargs = context.Process.call_args.kwargs

        assert kwargs["target"] is runtime_module._gui_process_entry
        assert kwargs["name"] == "taurino-test"
        assert kwargs["daemon"] is False
        assert kwargs["args"][0] == b"test-config"

        assert controller._process is process
        assert controller._status_connection is parent

    def test_double_start(self, controller, mock_process):
        controller._process = mock_process

        with pytest.raises(RuntimeStateError, match="already running"):
            controller.start()

    def test_process_factory_failure(self, controller, monkeypatch):
        parent = MagicMock()
        child = MagicMock()

        context = MagicMock()
        context.Pipe.return_value = (parent, child)
        context.Process.side_effect = RuntimeError("Cannot create process")

        monkeypatch.setattr(controller, "_context", context)

        with pytest.raises(RuntimeError, match="Cannot create process"):
            controller.start()

        parent.close.assert_called_once()
        child.close.assert_called_once()

    def test_process_start_failure(self, controller, monkeypatch):
        process = MagicMock()
        process.start.side_effect = OSError("Spawn failed")
        process.is_alive.return_value = False

        parent = MagicMock()
        child = MagicMock()

        context = MagicMock()
        context.Event.side_effect = lambda: mp.get_context("spawn").Event()
        context.Pipe.return_value = (parent, child)
        context.Process.return_value = process

        monkeypatch.setattr(controller, "_context", context)

        with pytest.raises(OSError, match="Spawn failed"):
            controller.start()

        child.close.assert_called_once()
        parent.close.assert_called_once()
        process.close.assert_called_once()


class TestReadiness:
    def test_ready_success(self, controller, mock_process, mock_connection):
        controller._process = mock_process
        controller._status_connection = mock_connection

        controller._wait_until_ready()

        mock_connection.recv.assert_called_once()

    def test_missing_connection(self, controller):
        with pytest.raises(RuntimeStateError, match="status pipe"):
            controller._wait_until_ready()

    def test_startup_timeout(self, controller, mock_process):
        controller._process = mock_process
        controller._start_timeout = 0.02

        connection = MagicMock()
        connection.poll.return_value = False

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="timed out"):
            controller._wait_until_ready()

    def test_native_error(self, controller, mock_process):
        controller._process = mock_process

        connection = MagicMock()
        connection.poll.return_value = True
        connection.recv.return_value = (
            "error",
            "Rust GUI initialization failed",
        )

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="Rust GUI initialization failed"):
            controller._wait_until_ready()

    def test_unknown_status(self, controller, mock_process):
        controller._process = mock_process

        connection = MagicMock()
        connection.poll.return_value = True
        connection.recv.return_value = ("invalid", None)

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="Unknown GUI status"):
            controller._wait_until_ready()

    def test_pipe_disconnected(self, controller, mock_process):
        controller._process = mock_process

        connection = MagicMock()
        connection.poll.return_value = True
        connection.recv.side_effect = EOFError()

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="disconnected"):
            controller._wait_until_ready()

    def test_child_exits_before_ready(self, controller, mock_process):
        mock_process.is_alive.return_value = False
        mock_process.exitcode = 1

        controller._process = mock_process

        connection = MagicMock()
        connection.poll.return_value = False

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="exited with code 1"):
            controller._wait_until_ready()

    def test_child_exits_after_ready_message(self, controller, mock_process):
        mock_process.is_alive.return_value = False
        controller._process = mock_process

        connection = MagicMock()
        connection.poll.return_value = True
        connection.recv.return_value = ("ready", None)

        controller._status_connection = connection

        with pytest.raises(RuntimeStartError, match="exited during startup"):
            controller._wait_until_ready()


class TestStop:
    def test_stop_without_process(self, controller):
        controller.stop()
        assert controller.is_running is False

    def test_request_stop(self, controller, mock_process):
        controller._process = mock_process

        controller.request_stop()

        assert controller._shutdown_event.is_set()
        assert controller.is_stopping is True

    def test_graceful_shutdown(self, controller):
        process = MagicMock()
        process.is_alive.return_value = True

        def join(timeout=None):
            process.is_alive.return_value = False

        process.join.side_effect = join
        controller._process = process

        controller.stop(timeout=0.1)

        assert controller._shutdown_event.is_set()
        process.join.assert_called_once_with(0.1)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

        # Avoid leaving the mocked process running during fixture cleanup.
        assert controller.is_running is False

    def test_terminate_fallback(self, controller):
        process = MagicMock()
        process.is_alive.return_value = True

        def terminate():
            process.is_alive.return_value = False

        process.terminate.side_effect = terminate
        controller._process = process

        controller.stop(timeout=0)

        assert controller._shutdown_event.is_set()
        process.join.assert_any_call(0)
        process.terminate.assert_called_once()
        process.kill.assert_not_called()

        assert controller.is_running is False

    def test_kill_fallback(self, controller):
        process = MagicMock()
        process.is_alive.return_value = True

        def kill():
            process.is_alive.return_value = False

        process.kill.side_effect = kill
        controller._process = process

        controller.stop(timeout=0)

        assert controller._shutdown_event.is_set()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()

        assert controller.is_running is False

    def test_negative_timeout(self, controller):
        with pytest.raises(ValueError):
            controller.stop(timeout=-1)

    def test_repeated_stop(self, controller):
        controller.stop()
        controller.stop()

        assert controller.is_running is False


class TestJoin:
    def test_join_without_process(self, controller):
        assert controller.join() is None

    def test_join_with_process(self, controller):
        process = MagicMock()
        process.is_alive.return_value = False
        process.exitcode = 0

        controller._process = process

        result = controller.join(timeout=0.5)

        process.join.assert_called_once_with(0.5)
        assert result == 0


class TestClose:
    def test_release_resources(self, controller):
        process = MagicMock()
        process.is_alive.return_value = False

        connection = MagicMock()

        controller._process = process
        controller._status_connection = connection

        controller.close()

        connection.close.assert_called_once()
        process.close.assert_called_once()

        assert controller._process is None
        assert controller._status_connection is None
        assert controller.pid is None

    def test_multiple_close(self, controller):
        controller.close()
        controller.close()

        assert controller._process is None


class TestChildEntry:
    def test_ready_notification_and_shutdown(self, monkeypatch):
        """Execute the real child entry point with a mocked native binding."""
        connection = MagicMock()
        shutdown_event = MagicMock()

        def fake_runtime(config, event, notify_ready):
            assert config == b"test-config"
            assert event is shutdown_event

            notify_ready()
            notify_ready()

        monkeypatch.setattr(runtime_module, "runtime", fake_runtime)

        runtime_module._gui_process_entry(
            b"test-config",
            shutdown_event,
            connection,
        )

        connection.send.assert_called_once_with(("ready", None))
        connection.close.assert_called_once()

    def test_native_exception(self, monkeypatch):
        connection = MagicMock()
        shutdown_event = MagicMock()

        def fake_runtime(config, event, notify_ready):
            raise RuntimeError("Native GUI failed")

        monkeypatch.setattr(runtime_module, "runtime", fake_runtime)

        with pytest.raises(RuntimeError, match="Native GUI failed"):
            runtime_module._gui_process_entry(
                b"test-config",
                shutdown_event,
                connection,
            )

        sent_status, sent_message = connection.send.call_args.args[0]

        assert sent_status == "error"
        assert "Native GUI failed" in sent_message

        connection.close.assert_called_once()

    def test_keyboard_interrupt(self, monkeypatch):
        connection = MagicMock()
        shutdown_event = MagicMock()

        def fake_runtime(config, event, notify_ready):
            raise KeyboardInterrupt()

        monkeypatch.setattr(runtime_module, "runtime", fake_runtime)

        runtime_module._gui_process_entry(
            b"test-config",
            shutdown_event,
            connection,
        )

        shutdown_event.set.assert_called_once()
        connection.close.assert_called_once()
