//! Two-way local IPC using a fixed-slot SPSC shared-memory mapping.
//!
//! IMPORTANT: Exactly one process uses Side::A and one uses Side::B.
//! This is a protocol requirement; the OS does not enforce ownership here.
//! Do not use across machines or different CPU architectures.
mod memory;
mod ringbuffer;

use anyhow::{Result, bail};
use memory::SharedMemory;
use ringbuffer::PushError;
use serde::{Serialize, de::DeserializeOwned};
use std::path::Path;
use std::time::Duration;

pub const MAX_MESSAGE_BYTES: usize = ringbuffer::MAX_MESSAGE;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    A,
    B,
}

pub struct Endpoint {
    memory: SharedMemory,
    side: Side,
}

#[derive(Debug, PartialEq, Eq)]
pub enum SendStatus {
    Sent,
    Full,
}

impl Endpoint {
    /// Create a NEW queue file. Fails if the file already exists.
    pub fn create(path: impl AsRef<Path>) -> Result<Self> {
        Ok(Self {
            memory: SharedMemory::create(path.as_ref())?,
            side: Side::A,
        })
    }

    /// Attach as side B to an existing queue file.
    pub fn connect(path: impl AsRef<Path>, timeout: Duration) -> Result<Self> {
        Ok(Self {
            memory: SharedMemory::open(path.as_ref(), timeout)?,
            side: Side::B,
        })
    }

    pub fn side(&self) -> Side {
        self.side
    }

    /// Nonblocking send. Full queues do not overwrite unread messages.
    pub fn try_send<T: Serialize>(&mut self, message: &T) -> Result<SendStatus> {
        let bytes = rmp_serde::to_vec_named(message)?;
        let region = self.memory.region();
        let tx = match self.side {
            Side::A => &region.a_to_b,
            Side::B => &region.b_to_a,
        };
        // SAFETY: API and deployment contract grant one producer per direction.
        match unsafe { tx.push(&bytes) } {
            Ok(()) => Ok(SendStatus::Sent),
            Err(PushError::Full) => Ok(SendStatus::Full),
            Err(PushError::TooLarge) => bail!("message exceeds {MAX_MESSAGE_BYTES} bytes"),
        }
    }

    /// Nonblocking receive; None means no message currently available.
    pub fn try_recv<T: DeserializeOwned>(&mut self) -> Result<Option<T>> {
        let region = self.memory.region();
        let rx = match self.side {
            Side::A => &region.b_to_a,
            Side::B => &region.a_to_b,
        };
        // SAFETY: API and deployment contract grant one consumer per direction.
        let Some(bytes) = (unsafe { rx.pop() }) else {
            return Ok(None);
        };
        Ok(Some(rmp_serde::from_slice(&bytes)?))
    }

    /// Send raw bytes without serialization.
    pub fn try_send_bytes(&mut self, bytes: &[u8]) -> Result<SendStatus> {
        let region = self.memory.region();

        let tx = match self.side {
            Side::A => &region.a_to_b,
            Side::B => &region.b_to_a,
        };

        match unsafe { tx.push(bytes) } {
            Ok(()) => Ok(SendStatus::Sent),
            Err(PushError::Full) => Ok(SendStatus::Full),
            Err(PushError::TooLarge) => {
                bail!("message exceeds {MAX_MESSAGE_BYTES} bytes")
            }
        }
    }

    /// Receive raw bytes without deserialization.
    pub fn try_recv_bytes(&mut self) -> Option<Vec<u8>> {
        let region = self.memory.region();

        let rx = match self.side {
            Side::A => &region.b_to_a,
            Side::B => &region.a_to_b,
        };

        unsafe { rx.pop() }
    }
}
