use std::{ops::Deref, pin::Pin};

use tao::event_loop::{
    ControlFlow, EventLoop as TaoLoop, EventLoopBuilder as TaoLoopBuilder,
    EventLoopProxy as TaoLoopProxy, EventLoopWindowTarget as TaoLoopWindowTarget,
};

pub type TargetCallback =
    Pin<Box<dyn Fn(&EventWindowTarget, &mut ControlFlow) -> anyhow::Result<()> + Send>>;
pub struct EventWithTarget(TargetCallback);

impl std::fmt::Debug for EventWithTarget {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("EventWithTarget").finish()
    }
}

impl EventWithTarget {
    pub fn new<
        F: Fn(&EventWindowTarget, &mut ControlFlow) -> anyhow::Result<()> + Send + 'static,
    >(
        f: F,
    ) -> Self {
        Self(Box::pin(f))
    }
}

impl Deref for EventWithTarget {
    type Target =
        Pin<Box<dyn Fn(&EventWindowTarget, &mut ControlFlow) -> anyhow::Result<()> + Send>>;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub enum EventLoopMessage {
    Task(Box<dyn FnOnce() + Send>),
    TargetTask(EventWithTarget),
    Shutdown,
}

pub type EventLoop = TaoLoop<EventLoopMessage>;
pub type EventLoopBuilder = TaoLoopBuilder<EventLoopMessage>;
pub type EventLoopProxy = TaoLoopProxy<EventLoopMessage>;
pub type EventWindowTarget = TaoLoopWindowTarget<EventLoopMessage>;

#[macro_export]
macro_rules! unsafe_impl_sync_send {
    ($type:ty) => {
        unsafe impl Send for $type {}
        unsafe impl Sync for $type {}
    };
}
