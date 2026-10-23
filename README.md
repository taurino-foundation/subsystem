<div align="center">
  <a href="https://github.com/taurino-foundation/taurino">
    <img
      src="https://raw.githubusercontent.com/taurino-foundation/taurino/main/docs/images/logo.png"
      alt="Taurino Logo"
      width="320"
    />
  </a>

# Meet Taurino

### A Modern, Rust-Powered Desktop Framework for Python

**Python Simplicity. Rust Performance. Native Desktop Experiences.**

</div>

---

Taurino is a modern, cross-platform desktop application framework that brings together **Python's flexibility**, **Rust's performance**, and **web technologies** in a unified development environment.

Powered by **Tao and Wry**, Taurino provides a native, event-driven runtime designed for asynchronous execution, inter-process communication (IPC), and integration between Python, Rust, and JavaScript.

Built for developers who value **performance, reliability, and flexibility**, Taurino aims to make native desktop development productive without requiring application developers to write Rust.

> **Project status:** Taurino is under active development. Public APIs, examples, packaging, and platform support may change. Check the [releases](https://github.com/taurino-foundation/taurino/releases) and [PyPI project](https://pypi.org/project/taurino/) for available versions before installing.

## Why Taurino?

- **Python-first development:** Keep application logic in Python and use native functionality through its Rust-based extension.
- **Native desktop windows:** Tao handles cross-platform windowing and event-loop integration.
- **Web-powered interfaces:** Wry provides access to the operating system's webview technology.
- **Process separation:** A GUI child process can be managed by the Python runtime.
- **Prebuilt wheels:** When a compatible wheel is available, Rust, Cargo, Maturin, and a C/C++ compiler are **not required** to install Taurino.

## Supported platforms

Taurino's CI builds Python extension wheels for the following targets. **A successful build and import test does not by itself certify the GUI runtime on every operating-system version.**

| Platform | Architectures | Native webview | Notes |
| --- | --- | --- | --- |
| Windows | x64, ARM64 | Microsoft Edge WebView2 | WebView2 Runtime must be installed. |
| macOS | Intel, Apple Silicon | WKWebView | Uses the system-provided WebKit implementation. |
| Linux (glibc) | x64, ARM64 | WebKitGTK | System runtime libraries are required; native Linux wheels are not guaranteed to work across distributions. |
| Linux (musl / Alpine) | x64, ARM64 | WebKitGTK | musllinux wheels are built, but full runtime portability still requires testing. |

### Python compatibility

The native PyO3 extension is built using **`abi3-py39`**, enabling a single wheel per platform to target standard CPython **3.9 and newer** at the extension ABI level. The actual supported Python range also depends on Taurino's published package metadata, Python dependencies, and testing. Verify the requirements for the release you install.

## 1. Install Python

Install a supported version of **CPython**. Use an isolated virtual environment for each application.

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv python install 3.13
uv init my-taurino-app
cd my-taurino-app
uv python pin 3.13
```

Or create a conventional virtual environment:

```bash
python -m venv .venv
```

Activate it before using `pip`:

- **Windows PowerShell:** `.venv\Scripts\Activate.ps1`
- **Linux / macOS:** `source .venv/bin/activate`

## 2. Check operating-system prerequisites

### Windows

**For installing a compatible prebuilt wheel:** You do **not** need to install Rust, Cargo, Maturin, Visual Studio, or Microsoft C++ Build Tools.

Taurino uses **Microsoft Edge WebView2** to display web content. WebView2 is typically already present on modern Windows installations. If it is missing, install the [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).

You only need Rust and the C++ build toolchain if you intend to **build Taurino from source** or develop its Rust internals.

### macOS

**For installing a compatible prebuilt wheel:** Xcode and Rust are **not required**.

Taurino uses **WKWebView**, which is provided by macOS. Install a supported macOS version and an appropriate Python interpreter. Apple Silicon and Intel require wheels matching their respective architectures.

Xcode Command Line Tools and Rust are only relevant if you are compiling Taurino yourself.

### Linux

Linux is different: **a Python wheel does not automatically install operating-system webview packages**. Taurino's Linux GUI backend uses GTK and **WebKitGTK 4.1**. You may need to install their runtime libraries through your distribution's package manager even when the Python wheel installed successfully.

The commands below are **examples for runtime use**, not complete lists for every distribution, release, or feature. Package names may differ. Install your distribution's WebKitGTK 4.1 and GTK 3 runtime packages as appropriate.

**Ubuntu / Debian (where these package names are available):**

```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-0 libgtk-3-0
```

**Fedora (example):**

```bash
sudo dnf install webkit2gtk4.1 gtk3
```

**Arch Linux (example):**

```bash
sudo pacman -S --needed webkit2gtk-4.1 gtk3
```

**Alpine Linux (example):**

```bash
sudo apk add webkit2gtk-4.1 gtk+3.0 font-dejavu
```

> **Important:** Some Linux platforms may need additional libraries or desktop services, such as X11/Wayland components or an application indicator implementation. In particular, bundled musllinux dependencies do not guarantee that a complete WebKitGTK desktop environment is present. NixOS and other nonstandard environments may require distribution-specific configuration.

#### Building Taurino from source on Linux

The commands above are for **users of prebuilt wheels**. If you modify or compile Taurino itself, install the **development** packages too (such as `libwebkit2gtk-4.1-dev` on Debian/Ubuntu or `webkit2gtk-4.1-dev` on Alpine), along with a Rust toolchain, compiler, and build tools. See the [Tauri Linux prerequisites](https://v2.tauri.app/start/prerequisites/) as a useful reference for the same underlying WebKitGTK stack; Taurino is a separate project and may have additional requirements.

## 3. Install Taurino

Once a suitable version has been published to PyPI, install it with **uv**:

```bash
uv add taurino
```

Or use **pip** in your activated virtual environment:

```bash
python -m pip install taurino
```

To install a particular released version:

```bash
python -m pip install "taurino==<version>"
```

Replace `<version>` with a version shown on the [Taurino PyPI page](https://pypi.org/project/taurino/).

> If the package or a compatible wheel is not published yet, these commands will not install a release from this repository. Follow the [releases](https://github.com/taurino-foundation/taurino/releases) for availability. **Prebuilt wheels are distributed as CI artifacts during development; a successful CI run is not a PyPI release.**

## 4. Verify your installation

Run a basic import check:

```bash
python -c "from taurino import Runtime; import taurino.runtime.core; print('Taurino native module imported successfully')"
```

This verifies that Python can import Taurino and its native module. **It does not verify that a window or WebView can be created on your machine.**

If the import fails, check that you installed a wheel compatible with your Python version, CPU architecture, and operating system, and that the required native runtime libraries are present.

## 5. Build your first desktop application

Taurino's public application builder API is still evolving. Until stable, documented `App` and `Window` APIs are released, use the version-matched examples in the repository:

- [Examples](https://github.com/taurino-foundation/taurino/tree/main/examples)
- [Source and documentation](https://github.com/taurino-foundation/taurino)

The currently implemented low-level `Runtime` controller runs the native event loop in a **separate child process**. Its configuration is an internal binary format and should not be guessed or replaced with arbitrary bytes. For a runnable GUI example, use the configuration and sample provided by the corresponding Taurino release.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No matching distribution found for taurino` | Is the release published, and is there a compatible wheel for your Python version and platform? |
| `ImportError`, `DLL load failed`, or missing `.so` | Check native system dependencies and that the Python and wheel architectures match. |
| WebView2 unavailable on Windows | Install or repair the Microsoft Edge WebView2 Runtime. |
| WebKitGTK missing on Linux | Install your distribution's WebKitGTK **4.1 runtime**, not only Python packages. |
| Wheel installs but the GUI does not start | Check the graphics/display session, system WebView runtime, application logs, and the corresponding release's known issues. |
| Source build requests Rust or a compiler | Prefer a supported published wheel unless you specifically intend to compile Taurino. |

When reporting a problem, include the Taurino version, Python version, operating system, CPU architecture, installation command, and full error message.

## For contributors

If you want to build or contribute to the Rust/PyO3 extension rather than install a prebuilt wheel, see the [repository](https://github.com/taurino-foundation/taurino). Taurino uses `uv` for Python workflows and `maturin` with PyO3 for native extension builds.

## Resources

- [Source code](https://github.com/taurino-foundation/taurino)
- [Releases](https://github.com/taurino-foundation/taurino/releases)
- [Issue tracker](https://github.com/taurino-foundation/taurino/issues)
- [PyPI](https://pypi.org/project/taurino/)
- [uv documentation](https://docs.astral.sh/uv/)

---

<div align="center">

**Taurino — Python Simplicity. Rust Performance. Native Desktop Experiences.**

</div>
