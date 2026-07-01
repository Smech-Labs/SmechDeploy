use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, UdpSocket};
use std::path::Path;
use std::process::{Command, exit};
use std::time::{Duration, Instant};

// Color codes
const RESET: &str = "\x1b[0m";
const BOLD: &str = "\x1b[1m";
const GREEN: &str = "\x1b[32m";
const CYAN: &str = "\x1b[36m";
const YELLOW: &str = "\x1b[33m";
const RED: &str = "\x1b[31m";
const MAGENTA: &str = "\x1b[35m";

const DOCS_URL: &str = "https://visor.smech.xyz/docs/spk-visor";
const RELEASE_BASE_URL: &str =
    "https://github.com/Smech-Labs/smechvisord/releases/download/v0.1.0-alpha-install-iso";

// Packages that OTA upgrade touches. Kernel updates are flagged as needing reboot.
const OTA_PACKAGES: &[(&str, bool)] = &[
    ("smechvisor-daemon", false), // smechvisord + cloud-hypervisor -- live-swappable
    ("smechvisor-base", true),    // kernel, musl base -- requires reboot
];

// UDP port used for shim discovery broadcasts and package receive
const SHIM_PORT: u16 = 9191;
// TCP port the shim listens on for incoming package streams
const SHIM_RECV_PORT: u16 = 9192;
const BROADCAST_MAGIC: &str = "SMECHVISOR_SHIM";

fn banner() {
    println!(
        "{}{}========================================================================{}",
        BOLD, MAGENTA, RESET
    );
    println!(
        "{}{}   SPK-VISOR -- SmechVisor Sovereign Package & Deploy Manager{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}   SmechVisor is install-only. This is NOT standard SPK.{}",
        BOLD, YELLOW, RESET
    );
    println!(
        "{}{}========================================================================{}",
        BOLD, MAGENTA, RESET
    );
}

fn print_help() {
    banner();
    println!("{}USAGE:{}", BOLD, RESET);
    println!("    spk-visor <COMMAND> [args]");
    println!();
    println!("{}COMMANDS:{}", BOLD, RESET);
    println!(
        "    {}entire-system-upgrade{}              Live OTA update -- no reboot required for daemon",
        GREEN, RESET
    );
    println!(
        "    {}deploy-system-img-copy <code>{}     Deploy this SmechVisor image to a shim target",
        GREEN, RESET
    );
    println!(
        "    {}receive-deploy{}                    Start shim receive mode (used by the shim ISO)",
        GREEN, RESET
    );
    println!("    {}version{}                           Show spk-visor version", GREEN, RESET);
    println!("    {}about{}                             Show SmechVisor info and credits", GREEN, RESET);
    println!("    {}help{}                              Show this help", GREEN, RESET);
    println!();
    println!("{}BLOCKED COMMANDS:{}", BOLD, RESET);
    println!(
        "    {}system-install{} / {}userland-install{}   Not supported on SmechVisor",
        RED, RESET, RED, RESET
    );
    println!();
    println!("{}DOCS:{}  {}", BOLD, RESET, DOCS_URL);
    println!();
}

fn print_about() {
    banner();
    println!("{}spk-visor v0.1.0{}", BOLD, RESET);
    println!("  SmechVisor-specific package and deploy manager.");
    println!("  Unlike standard SPK, spk-visor does not install arbitrary packages.");
    println!("  It manages live OTA updates and network-based system deployment.");
    println!();
    println!("{}OTA UPDATE:{}", BOLD, RESET);
    println!("  Downloads smechvisor-daemon from GitHub Releases, swaps the");
    println!("  smechvisord binary and web assets live via OpenRC, and restarts");
    println!("  the daemon -- no reboot, no VM downtime for daemon updates.");
    println!("  Kernel updates are downloaded but flagged as requiring a reboot.");
    println!();
    println!("{}NETWORK DEPLOY:{}", BOLD, RESET);
    println!("  Boot the SmechVisor Deploy Shim ISO on a target machine.");
    println!("  The shim displays a short code (e.g. e13gts2).");
    println!("  Run: spk-visor deploy-system-img-copy e13gts2");
    println!("  This machine discovers the target via UDP broadcast, then");
    println!("  streams all SmechVisor packages to the shim over TCP.");
    println!("  The shim installs and reboots into SmechVisor automatically.");
    println!();
    println!("{}DOCS:{}  {}", BOLD, RESET, DOCS_URL);
    println!();
}

fn blocked_command(cmd: &str) {
    println!(
        "{}{}[!] spk-visor does NOT support '{}' -- this is NOT standard SPK.{}",
        BOLD, RED, cmd, RESET
    );
    println!(
        "{}    SmechVisor is a sealed hypervisor OS. Package installation is not{}",
        RED, RESET
    );
    println!(
        "{}    available. Please refer to the documentation:{}",
        RED, RESET
    );
    println!("{}    {}{}", CYAN, DOCS_URL, RESET);
    exit(1);
}

fn run(cmd: &[&str]) -> Result<String, String> {
    let out = Command::new(cmd[0])
        .args(&cmd[1..])
        .output()
        .map_err(|e| format!("{}: {}", cmd[0], e))?;
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    if out.status.success() {
        Ok(combined)
    } else {
        Err(format!("{} failed: {}", cmd.join(" "), combined))
    }
}

fn run_ok(cmd: &[&str]) -> String {
    run(cmd).unwrap_or_default()
}

// ── Live OTA update ───────────────────────────────────────────────────────────

fn ota_upgrade() {
    banner();
    println!("{}[spk-visor] Starting live OTA upgrade...{}", CYAN, RESET);
    println!("  Source: {}", RELEASE_BASE_URL);
    println!();

    let mut needs_reboot = false;

    for (pkg, requires_reboot) in OTA_PACKAGES {
        println!("{}[+] Fetching {}...{}", CYAN, pkg, RESET);

        let tmp = format!("/tmp/spk-visor-{}.tar.xz", pkg);
        let url = format!("{}/{}.tar.xz", RELEASE_BASE_URL, pkg);

        let dl = run(&["curl", "-sfL", "-o", &tmp, &url]);
        if dl.is_err() {
            println!("{}[-] Failed to download {} -- skipping.{}", RED, pkg, RESET);
            continue;
        }

        if *requires_reboot {
            println!(
                "{}[!] {} requires a reboot to take effect. Extracting to / now...{}",
                YELLOW, pkg, RESET
            );
            let _ = run(&["tar", "-xf", &tmp, "-C", "/"]);
            let _ = fs::remove_file(&tmp);
            needs_reboot = true;
            continue;
        }

        // Live-swap smechvisord without rebooting:
        // 1. Extract to staging area
        // 2. Stop smechvisord
        // 3. Move new files into place
        // 4. Restart smechvisord
        println!("{}[+] Live-swapping {}...{}", CYAN, pkg, RESET);

        let stage = format!("/tmp/spk-visor-stage-{}", pkg);
        let _ = fs::create_dir_all(&stage);
        if let Err(e) = run(&["tar", "-xf", &tmp, "-C", &stage]) {
            println!("{}[-] Extract failed: {}{}", RED, e, RESET);
            let _ = fs::remove_file(&tmp);
            continue;
        }
        let _ = fs::remove_file(&tmp);

        println!("{}[+] Stopping smechvisord...{}", CYAN, RESET);
        let _ = run_ok(&["rc-service", "smechvisord", "stop"]);

        // Rsync staged files into system (fall back to cp -a if rsync absent)
        let sync_ok = if Path::new("/usr/bin/rsync").exists() || Path::new("/bin/rsync").exists() {
            run(&["rsync", "-a", &format!("{}/", stage), "/"]).is_ok()
        } else {
            run(&["cp", "-a", &format!("{}/.", stage), "/"]).is_ok()
        };

        let _ = fs::remove_dir_all(&stage);

        println!("{}[+] Starting smechvisord...{}", CYAN, RESET);
        let _ = run_ok(&["rc-service", "smechvisord", "start"]);

        if sync_ok {
            println!("{}[+] {} updated live -- smechvisord restarted.{}", GREEN, pkg, RESET);
        } else {
            println!("{}[-] File sync failed for {}.{}", RED, pkg, RESET);
        }
    }

    println!();
    if needs_reboot {
        println!(
            "{}{}[!] Kernel or base packages were updated. Reboot when ready to apply them.{}",
            BOLD, YELLOW, RESET
        );
        println!(
            "{}    Daemon updates are already live -- VMs are unaffected until reboot.{}",
            YELLOW, RESET
        );
    } else {
        println!(
            "{}{}[+] OTA upgrade complete. No reboot required.{}",
            BOLD, GREEN, RESET
        );
    }
}

// ── Network deploy (sender side) ─────────────────────────────────────────────

fn deploy_to(code: &str) {
    banner();
    println!(
        "{}[spk-visor] Searching for shim with code {}{}{}...{}",
        CYAN, BOLD, code, RESET, RESET
    );

    let socket = UdpSocket::bind("0.0.0.0:0").expect("Failed to bind UDP socket");
    socket.set_broadcast(true).expect("Failed to enable broadcast");
    socket
        .set_read_timeout(Some(Duration::from_secs(10)))
        .unwrap();

    // Listen for shim broadcast: "SMECHVISOR_SHIM:{code}"
    let mut buf = [0u8; 256];
    let target_ip;
    let deadline = Instant::now() + Duration::from_secs(60);

    loop {
        if Instant::now() > deadline {
            println!(
                "{}[-] Timed out waiting for shim '{}'. Make sure the shim ISO is booted\n    and connected to the same network.{}",
                RED, code, RESET
            );
            exit(1);
        }
        match socket.recv_from(&mut buf) {
            Ok((len, src)) => {
                let msg = String::from_utf8_lossy(&buf[..len]);
                // Expected: "SMECHVISOR_SHIM:{code}"
                let expected = format!("{}:{}", BROADCAST_MAGIC, code);
                if msg.trim() == expected {
                    target_ip = src.ip().to_string();
                    println!("{}[+] Found shim '{}' at {}{}",GREEN, code, target_ip, RESET);
                    break;
                }
            }
            Err(_) => continue,
        }
    }

    // Collect package tarballs to send
    let packages = [
        "/tmp/smechos_build/smechvisor_install_iso/packages/smechvisor-base.tar.xz",
        "/tmp/smechos_build/smechvisor_install_iso/packages/smechvisor-daemon.tar.xz",
    ];

    let addr = format!("{}:{}", target_ip, SHIM_RECV_PORT);
    println!("{}[+] Connecting to shim at {}...{}", CYAN, addr, RESET);

    let mut stream = TcpStream::connect(&addr).unwrap_or_else(|e| {
        println!("{}[-] Could not connect to shim: {}{}", RED, e, RESET);
        exit(1);
    });

    for pkg_path in &packages {
        if !Path::new(pkg_path).exists() {
            println!("{}[-] Package not found locally: {} -- skipping.{}", YELLOW, pkg_path, RESET);
            continue;
        }

        let data = fs::read(pkg_path).unwrap_or_else(|e| {
            println!("{}[-] Could not read {}: {}{}", RED, pkg_path, e, RESET);
            exit(1);
        });

        let filename = Path::new(pkg_path)
            .file_name()
            .unwrap()
            .to_string_lossy();

        println!("{}[+] Sending {} ({} MB)...{}", CYAN, filename, data.len() / 1_048_576, RESET);

        // Wire protocol: 4-byte filename length, filename, 8-byte data length, data
        let name_bytes = filename.as_bytes();
        let _ = stream.write_all(&(name_bytes.len() as u32).to_be_bytes());
        let _ = stream.write_all(name_bytes);
        let _ = stream.write_all(&(data.len() as u64).to_be_bytes());
        let _ = stream.write_all(&data);

        println!("{}[+] {} sent.{}", GREEN, filename, RESET);
    }

    // Send terminator: filename length = 0
    let _ = stream.write_all(&0u32.to_be_bytes());

    println!();
    println!(
        "{}{}[+] Deploy complete. The shim is installing SmechVisor.{}",
        BOLD, GREEN, RESET
    );
    println!(
        "{}    The target machine will reboot into SmechVisor when done.{}",
        GREEN, RESET
    );
}

// ── Shim receive mode (runs on the shim ISO) ─────────────────────────────────

fn receive_deploy() {
    // Generate a random 7-char code from the system clock + PID
    let seed = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos()
        ^ (std::process::id() << 16);
    let code: String = format!("{:07x}", seed & 0x0fffffff)[..7].to_string();

    println!();
    println!(
        "{}{}╔══════════════════════════════════════════╗{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║   SmechVisor Deploy Shim -- Ready        ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║                                          ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║   Deploy code:  {}{}{:>7}{}{}{}               ║{}",
        BOLD, CYAN, RESET, BOLD, code, RESET, BOLD, CYAN, RESET
    );
    println!(
        "{}{}║                                          ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║   On source:                             ║{}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}║   spk-visor deploy-system-img-copy {}{}   ║{}",
        BOLD, CYAN, code, RESET, RESET
    );
    println!(
        "{}{}╚══════════════════════════════════════════╝{}",
        BOLD, CYAN, RESET
    );
    println!();

    // Broadcast code via UDP every 2s in background
    let code_clone = code.clone();
    std::thread::spawn(move || {
        let sock = UdpSocket::bind("0.0.0.0:0").expect("UDP bind failed");
        sock.set_broadcast(true).unwrap();
        let msg = format!("{}:{}", BROADCAST_MAGIC, code_clone);
        loop {
            let _ = sock.send_to(msg.as_bytes(), format!("255.255.255.255:{}", SHIM_PORT));
            std::thread::sleep(Duration::from_secs(2));
        }
    });

    // Listen for incoming package stream
    let listener = TcpListener::bind(format!("0.0.0.0:{}", SHIM_RECV_PORT))
        .expect("Failed to bind TCP receiver");
    println!("{}[shim] Waiting for deploy connection on port {}...{}", CYAN, SHIM_RECV_PORT, RESET);

    let (mut stream, peer) = listener.accept().expect("Accept failed");
    println!("{}[shim] Connected from {}. Receiving packages...{}", GREEN, peer, RESET);

    let extract_root = "/mnt/target";
    let _ = fs::create_dir_all(extract_root);

    loop {
        // Read filename length
        let mut len_buf = [0u8; 4];
        if stream.read_exact(&mut len_buf).is_err() { break; }
        let name_len = u32::from_be_bytes(len_buf) as usize;
        if name_len == 0 { break; } // terminator

        // Read filename
        let mut name_buf = vec![0u8; name_len];
        if stream.read_exact(&mut name_buf).is_err() { break; }
        let filename = String::from_utf8_lossy(&name_buf).into_owned();

        // Read data length
        let mut dlen_buf = [0u8; 8];
        if stream.read_exact(&mut dlen_buf).is_err() { break; }
        let data_len = u64::from_be_bytes(dlen_buf) as usize;

        println!("{}[shim] Receiving {} ({} MB)...{}", CYAN, filename, data_len / 1_048_576, RESET);

        // Stream directly to a temp file to avoid loading into RAM
        let tmp_path = format!("/tmp/{}", filename);
        let mut f = fs::File::create(&tmp_path).expect("Cannot create tmp file");
        let mut remaining = data_len;
        let mut chunk = vec![0u8; 65536];
        while remaining > 0 {
            let to_read = remaining.min(chunk.len());
            let n = stream.read(&mut chunk[..to_read]).unwrap_or(0);
            if n == 0 { break; }
            f.write_all(&chunk[..n]).expect("Write failed");
            remaining -= n;
        }
        drop(f);

        println!("{}[shim] Extracting {} into {}...{}", CYAN, filename, extract_root, RESET);
        let _ = run(&["tar", "--ignore-failed-read", "-xJf", &tmp_path, "-C", extract_root]);
        let _ = fs::remove_file(&tmp_path);
        println!("{}[shim] {} installed.{}", GREEN, filename, RESET);
    }

    println!();
    println!("{}{}[shim] All packages received. Rebooting into SmechVisor...{}", BOLD, GREEN, RESET);

    // Brief pause so the user can read the screen
    std::thread::sleep(Duration::from_secs(3));
    libc_reboot();
}

#[cfg(target_os = "linux")]
fn libc_reboot() {
    unsafe extern "C" {
        fn sync();
        fn reboot(cmd: i32) -> i32;
    }
    unsafe {
        sync();
        reboot(0x01234567u32 as i32);
    }
}

#[cfg(not(target_os = "linux"))]
fn libc_reboot() {
    let _ = run(&["reboot"]);
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        print_help();
        exit(0);
    }

    match args[1].as_str() {
        "help" | "--help" | "-h" => print_help(),
        "about" | "--about" => print_about(),
        "version" | "--version" => {
            println!("spk-visor 0.1.0");
        }

        // Blocked commands -- SmechVisor does not support package install
        "system-install" => blocked_command("system-install"),
        "userland-install" => blocked_command("userland-install"),
        "entire-system-upgrade" => {
            // Also block if somehow called from a non-SmechVisor context
            if !Path::new("/usr/sbin/smechvisord").exists()
                && !Path::new("/usr/bin/smechvisord").exists()
            {
                println!(
                    "{}[!] smechvisord not found. Are you running on SmechVisor?{}",
                    RED, RESET
                );
                exit(1);
            }
            ota_upgrade();
        }

        "deploy-system-img-copy" => {
            if args.len() < 3 {
                println!("{}[-] Usage: spk-visor deploy-system-img-copy <code>{}", RED, RESET);
                println!("    Boot the SmechVisor Deploy Shim ISO on the target machine");
                println!("    and enter the code it displays.");
                exit(1);
            }
            let code = args[2].to_lowercase();
            deploy_to(&code);
        }

        "receive-deploy" => {
            receive_deploy();
        }

        cmd => {
            println!("{}[-] Unknown command: '{}'{}", RED, cmd, RESET);
            println!("    Run 'spk-visor help' to see available commands.");
            exit(1);
        }
    }
}
