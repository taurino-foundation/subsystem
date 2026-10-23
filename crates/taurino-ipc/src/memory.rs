//! A file-backed mapping is used as portable local shared memory.
//! Both processes must run on the same machine and use compatible architecture/ABI.
use crate::ringbuffer::RingBuffer;
use anyhow::{Context, Result, bail};
use memmap2::{MmapMut, MmapOptions};
use std::fs::{File, OpenOptions};
use std::path::Path;
use std::sync::atomic::{AtomicU32, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const MAGIC: u32 = 0x5449_5043; // TIPC
const VERSION: u32 = 1;

#[repr(C, align(64))]
pub(crate) struct Region {
    magic: u32,
    version: u32,
    ready: AtomicU32,
    pub(crate) a_to_b: RingBuffer,
    pub(crate) b_to_a: RingBuffer,
}

// Region contains only integer fields, atomics, and byte buffers. Zero is a
// valid initial representation for every field. Create it directly in the
// mapped pages: constructing Region::new() by value may overflow a Windows
// thread stack because the two ring buffers are very large.

pub(crate) struct SharedMemory {
    // Keeps mapping alive and its memory at a stable address.
    map: MmapMut,
}

impl SharedMemory {
    pub(crate) fn create(path: &Path) -> Result<Self> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(path)
            .with_context(|| format!("create mapping file {}", path.display()))?;
        file.set_len(std::mem::size_of::<Region>() as u64)?;
        let mut map = unsafe {
            MmapOptions::new()
                .len(std::mem::size_of::<Region>())
                .map_mut(&file)?
        };
        check_alignment(map.as_ptr())?;
        // SAFETY: This mapping has exclusive ownership during creation and
        // every field of Region is valid when all its bytes are zero (including
        // AtomicU32/U64 and UnsafeCell<u8/u32>). Do not add fields with a
        // non-zero validity requirement without changing this initializer.
        // In particular, no large Region temporary is allocated on the stack.
        map.fill(0);
        let region_ptr = map.as_mut_ptr().cast::<Region>();
        unsafe {
            std::ptr::addr_of_mut!((*region_ptr).magic).write(MAGIC);
            std::ptr::addr_of_mut!((*region_ptr).version).write(VERSION);
        }
        // Publish initialization only after the complete region is written.
        unsafe { &*region_ptr }.ready.store(1, Ordering::Release);
        Ok(Self { map })
    }

    pub(crate) fn open(path: &Path, timeout: Duration) -> Result<Self> {
        let deadline = Instant::now() + timeout;
        let file: File = loop {
            match OpenOptions::new().read(true).write(true).open(path) {
                Ok(f) => break f,
                Err(e) if e.kind() == std::io::ErrorKind::NotFound && Instant::now() < deadline => {
                    thread::sleep(Duration::from_millis(10));
                }
                Err(e) => return Err(e).with_context(|| format!("open {}", path.display())),
            }
        };
        // Creator sets file size before marking ready. Wait until file is fully sized.
        while file.metadata()?.len() < std::mem::size_of::<Region>() as u64 {
            if Instant::now() >= deadline {
                bail!("mapping not sized before timeout")
            }
            thread::sleep(Duration::from_millis(10));
        }
        let map = unsafe {
            MmapOptions::new()
                .len(std::mem::size_of::<Region>())
                .map_mut(&file)?
        };
        check_alignment(map.as_ptr())?;
        loop {
            let region = unsafe { &*map.as_ptr().cast::<Region>() };
            if region.ready.load(Ordering::Acquire) == 1 {
                if region.magic != MAGIC || region.version != VERSION {
                    bail!("incompatible shared-memory layout")
                }
                return Ok(Self { map });
            }
            if Instant::now() >= deadline {
                bail!("initialization timeout")
            }
            thread::sleep(Duration::from_millis(10));
        }
    }

    pub(crate) fn region(&self) -> &Region {
        // SAFETY: mapping remains alive, layout was initialized/validated and is aligned.
        unsafe { &*self.map.as_ptr().cast::<Region>() }
    }
}

fn check_alignment(ptr: *const u8) -> Result<()> {
    if !(ptr as usize).is_multiple_of(std::mem::align_of::<Region>()) {
        bail!("shared region is not aligned");
    }

    Ok(())
}
