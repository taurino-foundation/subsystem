use std::{
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    thread,
};

use crate::utis::{EventLoop, EventLoopBuilder, EventLoopMessage, EventLoopProxy};

use {
    pyo3::{exceptions::PyRuntimeError, prelude::*},
    std::sync::OnceLock,
};

use tao::dpi;
use {
    anyhow::{Context, Result},
    tao::{
        event::{Event, WindowEvent},
        event_loop::ControlFlow,
        window::WindowBuilder,
    },
    wry::WebViewBuilder,
};

pub mod json_rpc;
mod utis;

pub struct Manager {}
impl Manager {
    pub fn new() -> Result<Arc<Self>> {
        Ok(Arc::new(Self {}))
    }
}

pub struct Taurino {
    runner: EventLoop,
    manager: Arc<Manager>,
    proxy: EventLoopProxy,
}

impl Taurino {
    pub fn new(config: Vec<u8>) -> Result<Self> {
        let _ = config;

        // Create the native event loop.
        let mut builder = EventLoopBuilder::with_user_event();

        let runner = builder.build();
        let proxy = runner.create_proxy();

        let manager = Manager::new()?;

        Ok(Self {
            runner,
            manager,
            proxy,
        })
    }

    pub fn run(self, shutdown_event: Py<PyAny>, notify_ready: Py<PyAny>) -> Result<()> {
        let Self {
            runner,
            manager,
            proxy,
        } = self;

        // Create the initial native window.
        let window = WindowBuilder::new()
            .with_title("Taurino")
            .with_inner_size(dpi::LogicalSize::new(1000.0, 700.0))
            .build(&runner)?;
        let _webview = WebViewBuilder::new()
            .with_url("https://www.y-sic.com")
            .build(&window)?;
        let window_id = window.id();
        let watcher_running = Arc::new(AtomicBool::new(true));
        let watcher =
            spawn_shutdown_watcher(shutdown_event, proxy.clone(), Arc::clone(&watcher_running));

        // Notify Python only once the IPC client, window, and WebView exist.
        // This does NOT mean JavaScript has installed all application listeners.
        if let Err(error) = Python::attach(|py| notify_ready.call0(py).map(|_| ())) {
            watcher_running.store(false, Ordering::Release);
            let _ = watcher.join();
            return Err(error.into());
        }
        // Start the native application event loop.
        runner.run(move |event, _, control_flow| {
            *control_flow = ControlFlow::Wait;

            match event {
                Event::WindowEvent {
                    window_id: id,
                    event: WindowEvent::CloseRequested,
                    ..
                } if id == window_id => {
                    *control_flow = ControlFlow::Exit;
                }

                _ => {}
            }

            // Keep application resources alive for the lifetime
            // of the native event loop.
            let _ = (&window, &manager, &proxy);
        })
    }

    pub fn manager(&self) -> &Arc<Manager> {
        &self.manager
    }

    pub fn proxy(&self) -> &EventLoopProxy {
        &self.proxy
    }
}

pub fn get_taurino_version() -> &'static str {
    static VERSION: OnceLock<String> = OnceLock::new();

    VERSION.get_or_init(|| {
        let version = env!("CARGO_PKG_VERSION");
        version.replace("-alpha", "a").replace("-beta", "b")
    })
}

fn run_runtime(config: Vec<u8>, shutdown_event: Py<PyAny>, notify_ready: Py<PyAny>) -> Result<()> {
    let app = Taurino::new(config).context("Failed to initialize Taurino Runtime")?;

    app.run(shutdown_event, notify_ready)
        .context("Taurino runtime failed")
}
#[pyfunction]
fn runtime(
    py: Python<'_>,
    config: Vec<u8>,
    shutdown_event: Py<PyAny>,
    notify_ready: Py<PyAny>,
) -> PyResult<()> {
    py.detach(move || {
        run_runtime(config, shutdown_event, notify_ready)
            .map_err(|error| PyRuntimeError::new_err(format!("{error:#}")))
    })
}

#[pymodule]
fn core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__version__", get_taurino_version())?;
    module.add_function(wrap_pyfunction!(runtime, module)?)?;
    Ok(())
}

fn spawn_shutdown_watcher(
    shutdown_event: Py<PyAny>,
    proxy: EventLoopProxy,
    running: Arc<AtomicBool>,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        while running.load(Ordering::Acquire) {
            // multiprocessing.Event.wait(timeout), in Python's spawned child.
            let wait_result = Python::attach(|py| {
                shutdown_event
                    .call_method1(py, "wait", (0.1_f64,))
                    .and_then(|result| result.extract::<bool>(py))
            });

            match wait_result {
                Ok(true) => {
                    let _ = proxy.send_event(EventLoopMessage::Shutdown);
                    break;
                }
                Ok(false) => {}
                Err(error) => {
                    eprintln!("Shutdown watcher failed: {error}");
                    let _ = proxy.send_event(EventLoopMessage::Shutdown);
                    break;
                }
            }
        }
    })
}
