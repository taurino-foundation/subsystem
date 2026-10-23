
"""Basic example for the Taurino desktop runtime.

Run:
    uv run python examples/basic.py

The GUI runs in a separate child process.
"""

from __future__ import annotations

import multiprocessing as mp
import time

from taurino.error import RuntimeStartError, RuntimeStateError
from taurino.runtime import Runtime


def main() -> None:
    """Start and manage the Taurino GUI runtime."""

    # Native runtime configuration.
    # Replace this with the MessagePack configuration expected by Rust.
    config = b""

    gui = Runtime(
        config=config,
        name="taurino-basic",
        start_timeout=15.0,
        stop_timeout=5.0,
        method="spawn",
    )

    try:
        print("[Taurino] Starting GUI runtime...")

        gui.start()

        print("[Taurino] GUI runtime started.")
        print(f"[Taurino] Process ID: {gui.pid}")

        while gui.is_running:
            time.sleep(0.1)

        print(f"[Taurino] GUI exited with code: {gui.exitcode}")

    except KeyboardInterrupt:
        print("\n[Taurino] Keyboard interrupt received.")

    except (RuntimeStartError, RuntimeStateError) as exc:
        print(f"[Taurino] Runtime error: {exc}")
        raise

    finally:
        print("[Taurino] Stopping GUI runtime...")
        gui.close()
        print("[Taurino] GUI runtime closed.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
