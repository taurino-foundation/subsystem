//! Fixed-slot SPSC FIFO designed for a shared memory mapping.
//! One producer and one consumer PER direction; never use for MPMC.

use std::cell::UnsafeCell;
use std::sync::atomic::{AtomicU64, Ordering};

pub const SLOT_COUNT: usize = 64;
pub const MAX_MESSAGE: usize = 2048;

#[repr(C)]
struct Slot {
    len: UnsafeCell<u32>,
    bytes: UnsafeCell<[u8; MAX_MESSAGE]>,
}

#[repr(C, align(64))]
pub(crate) struct RingBuffer {
    head: AtomicU64,
    tail: AtomicU64,
    slots: [Slot; SLOT_COUNT],
}

impl RingBuffer {
    /// SAFETY: Exactly one producer must write to this ring.
    pub(crate) unsafe fn push(&self, payload: &[u8]) -> Result<(), PushError> {
        if payload.len() > MAX_MESSAGE {
            return Err(PushError::TooLarge);
        }

        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire);

        if head.wrapping_sub(tail) >= SLOT_COUNT as u64 {
            return Err(PushError::Full);
        }

        let slot = &self.slots[(head as usize) % SLOT_COUNT];

        // SAFETY: The producer exclusively owns this slot until head is published.
        unsafe {
            (&mut (*slot.bytes.get()))[..payload.len()].copy_from_slice(payload);
            slot.len.get().write(payload.len() as u32);
        }

        self.head.store(head.wrapping_add(1), Ordering::Release);

        Ok(())
    }

    /// SAFETY: Exactly one consumer must read from this ring.
    pub(crate) unsafe fn pop(&self) -> Option<Vec<u8>> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire);

        if tail == head {
            return None;
        }

        let slot = &self.slots[(tail as usize) % SLOT_COUNT];

        // SAFETY: Acquire of head makes producer writes visible.
        let len = unsafe { slot.len.get().read() as usize };

        assert!(len <= MAX_MESSAGE, "corrupted ring buffer length");

        let mut result = vec![0u8; len];

        // SAFETY: Consumer owns this published slot until tail is released.
        unsafe {
            result.copy_from_slice(&(&(*slot.bytes.get()))[..len]);
        }

        self.tail.store(tail.wrapping_add(1), Ordering::Release);

        Some(result)
    }
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum PushError {
    Full,
    TooLarge,
}
