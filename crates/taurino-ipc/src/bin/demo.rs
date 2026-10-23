use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use std::{
    env,
    path::PathBuf,
    thread,
    time::{Duration, Instant},
};
use taurino_ipc::{Endpoint, SendStatus};

#[derive(Debug, Serialize, Deserialize)]
struct Message {
    id: u64,
    text: String,
}

fn send_wait(ep: &mut Endpoint, msg: &Message) -> Result<()> {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        match ep.try_send(msg)? {
            SendStatus::Sent => return Ok(()),
            SendStatus::Full if Instant::now() < deadline => {
                thread::sleep(Duration::from_millis(1))
            }
            SendStatus::Full => bail!("send timed out: ring buffer full"),
        }
    }
}

fn recv_wait(ep: &mut Endpoint) -> Result<Message> {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Some(msg) = ep.try_recv::<Message>()? {
            return Ok(msg);
        }
        if Instant::now() >= deadline {
            bail!("receive timeout")
        }
        thread::sleep(Duration::from_millis(1));
    }
}

fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 || !["a", "b"].contains(&args[1].as_str()) {
        bail!("usage: cargo run --bin demo -- <a|b> <mapping-file-path>")
    }
    let file = PathBuf::from(&args[2]);
    if args[1] == "a" {
        let mut ep = Endpoint::create(&file)?;
        println!("side A created {}", file.display());
        send_wait(
            &mut ep,
            &Message {
                id: 1,
                text: "Hallo von A".into(),
            },
        )?;
        println!("A received: {:?}", recv_wait(&mut ep)?);
    } else {
        let mut ep = Endpoint::connect(&file, Duration::from_secs(10))?;
        let received = recv_wait(&mut ep)?;
        println!("B received: {received:?}");
        send_wait(
            &mut ep,
            &Message {
                id: received.id + 1,
                text: "Hallo von B".into(),
            },
        )?;
    }
    Ok(())
}
