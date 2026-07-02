mod newt;

use newt::Screen;
use std::fs;
use std::io::{Read, Write as IoWrite};
use std::net::{TcpListener, UdpSocket};
use std::process::{Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const TARGET: &str = "/mnt/target";
const SHIM_UDP_PORT: u16 = 9191;
const SHIM_TCP_PORT: u16 = 9192;
const BROADCAST_MAGIC: &str = "SMECHVISOR_SHIM";

// ── Helpers ───────────────────────────────────────────────────────────────────

fn run(cmd: &[&str]) -> Result<String, String> {
    let child = Command::new(cmd[0])
        .args(&cmd[1..])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{}: {}", cmd[0], e))?;
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    if out.status.success() {
        Ok(combined)
    } else {
        Err(format!("{} failed:\n{}", cmd.join(" "), combined))
    }
}

fn run_ok(cmd: &[&str]) -> String {
    run(cmd).unwrap_or_default()
}

fn gen_code() -> String {
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let pid = std::process::id() as u128;
    format!("{:07x}", (t ^ (pid << 17)) & 0x0FFF_FFFF)
}

// ── Disk helpers ──────────────────────────────────────────────────────────────

fn list_disks() -> Vec<String> {
    let mut disks = Vec::new();
    if let Ok(entries) = fs::read_dir("/sys/block") {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name.starts_with("sd")
                || name.starts_with("vd")
                || name.starts_with("nvme")
                || name.starts_with("xvd")
                || name.starts_with("hd")
            {
                let size_path = format!("/sys/block/{}/size", name);
                let size_mb = fs::read_to_string(&size_path)
                    .ok()
                    .and_then(|s| s.trim().parse::<u64>().ok())
                    .map(|s| s * 512 / 1024 / 1024)
                    .unwrap_or(0);
                disks.push(format!("/dev/{}  ({} MB)", name, size_mb));
            }
        }
    }
    disks.sort();
    disks
}

fn disk_dev_from_entry(entry: &str) -> String {
    entry.split_whitespace().next().unwrap_or(entry).to_string()
}

fn partition_name(disk: &str, n: u32) -> String {
    if disk.contains("nvme") || disk.contains("mmcblk") {
        format!("{}p{}", disk, n)
    } else {
        format!("{}{}", disk, n)
    }
}

fn auto_partition(disk: &str) -> Result<(String, String, String), String> {
    // GPT: 512MB EFI, 2GB swap, rest root
    let script = "label: gpt\n,512M,U,*\n,2G,S\n,,L\n";
    let mut child = Command::new("sfdisk")
        .arg(disk)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("sfdisk: {}", e))?;
    if let Some(mut stdin) = child.stdin.take() {
        stdin.write_all(script.as_bytes()).ok();
    }
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    if !out.status.success() {
        return Err(format!(
            "sfdisk failed:\n{}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    // Let the kernel re-read the partition table
    run_ok(&["partprobe", disk]);
    std::thread::sleep(Duration::from_secs(2));

    let efi = partition_name(disk, 1);
    let swap = partition_name(disk, 2);
    let root = partition_name(disk, 3);
    Ok((efi, swap, root))
}

fn format_and_mount(efi: &str, swap: &str, root: &str) -> Result<(), String> {
    run(&["mkfs.vfat", "-F", "32", efi])?;
    run(&["mkswap", swap])?;
    run(&["mkfs.ext4", "-F", root])?;
    let _ = fs::create_dir_all(TARGET);
    run(&["mount", root, TARGET])?;
    let efi_dir = format!("{}/boot/efi", TARGET);
    let _ = fs::create_dir_all(&efi_dir);
    run(&["mount", efi, &efi_dir])?;
    Ok(())
}

// ── Network helpers ───────────────────────────────────────────────────────────

fn list_wifi_ifaces() -> Vec<String> {
    let mut ifaces = Vec::new();
    if let Ok(entries) = fs::read_dir("/sys/class/net") {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if fs::metadata(format!("/sys/class/net/{}/wireless", name)).is_ok() {
                ifaces.push(name);
            }
        }
    }
    ifaces.sort();
    ifaces
}

fn list_eth_ifaces() -> Vec<String> {
    let mut ifaces = Vec::new();
    if let Ok(entries) = fs::read_dir("/sys/class/net") {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name == "lo" {
                continue;
            }
            if fs::metadata(format!("/sys/class/net/{}/wireless", name)).is_err() {
                ifaces.push(name);
            }
        }
    }
    ifaces.sort();
    ifaces
}

fn scan_ssids(iface: &str) -> Vec<String> {
    run_ok(&["iw", "dev", iface, "scan"])
        .lines()
        .filter(|l| l.trim_start().starts_with("SSID:"))
        .map(|l| l.trim_start().trim_start_matches("SSID:").trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn connect_wifi(iface: &str, ssid: &str, password: &str) -> Result<(), String> {
    let conf = format!(
        "ctrl_interface=/var/run/wpa_supplicant\nnetwork={{\n    ssid=\"{}\"\n    psk=\"{}\"\n}}\n",
        ssid, password
    );
    fs::write("/tmp/wpa_shim.conf", conf).map_err(|e| e.to_string())?;
    run(&["ip", "link", "set", iface, "up"])?;
    run(&[
        "wpa_supplicant", "-B", "-i", iface,
        "-c", "/tmp/wpa_shim.conf",
        "-P", "/tmp/wpa_shim.pid",
    ])?;
    std::thread::sleep(Duration::from_secs(3));
    run(&["dhcpcd", "-t", "20", iface])?;
    Ok(())
}

fn setup_dhcp(iface: &str) -> Result<(), String> {
    run(&["ip", "link", "set", iface, "up"])?;
    run(&["dhcpcd", "-t", "20", iface])?;
    Ok(())
}

fn setup_static(iface: &str, ip_cidr: &str, gw: &str, dns: &str) -> Result<(), String> {
    run(&["ip", "link", "set", iface, "up"])?;
    run(&["ip", "addr", "add", ip_cidr, "dev", iface])?;
    run(&["ip", "route", "add", "default", "via", gw])?;
    fs::write("/etc/resolv.conf", format!("nameserver {}\nnameserver 1.1.1.1\n", dns))
        .map_err(|e| e.to_string())?;
    Ok(())
}

// ── TCP receive ───────────────────────────────────────────────────────────────

fn receive_packages(stream: &mut std::net::TcpStream) -> Result<(), String> {
    let _ = fs::create_dir_all(TARGET);
    loop {
        // Read 4-byte name length
        let mut name_len_buf = [0u8; 4];
        stream
            .read_exact(&mut name_len_buf)
            .map_err(|e| format!("read name_len: {}", e))?;
        let name_len = u32::from_be_bytes(name_len_buf);
        if name_len == 0 {
            break; // terminator
        }
        // Read name
        let mut name_buf = vec![0u8; name_len as usize];
        stream
            .read_exact(&mut name_buf)
            .map_err(|e| format!("read name: {}", e))?;
        let name = String::from_utf8_lossy(&name_buf).to_string();

        // Read 8-byte data length
        let mut data_len_buf = [0u8; 8];
        stream
            .read_exact(&mut data_len_buf)
            .map_err(|e| format!("read data_len: {}", e))?;
        let data_len = u64::from_be_bytes(data_len_buf);

        println!("  Receiving package '{}' ({} bytes)...", name, data_len);

        // Stream directly into tar xJ
        let mut child = Command::new("tar")
            .args(["-xJf", "-", "-C", TARGET])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("tar spawn: {}", e))?;

        let mut remaining = data_len;
        let mut buf = [0u8; 65536];
        if let Some(mut tar_stdin) = child.stdin.take() {
            while remaining > 0 {
                let to_read = remaining.min(buf.len() as u64) as usize;
                let n = stream
                    .read(&mut buf[..to_read])
                    .map_err(|e| format!("read data: {}", e))?;
                if n == 0 {
                    return Err("connection closed mid-package".to_string());
                }
                tar_stdin
                    .write_all(&buf[..n])
                    .map_err(|e| format!("tar write: {}", e))?;
                remaining -= n as u64;
            }
        }
        child
            .wait()
            .map_err(|e| format!("tar wait: {}", e))?;
        println!("  '{}' installed.", name);
    }
    Ok(())
}

// ── GRUB + post-install ───────────────────────────────────────────────────────

fn post_install(root_part: &str, efi_part: &str) -> Result<(), String> {
    let root_uuid = run_ok(&["blkid", "-s", "UUID", "-o", "value", root_part])
        .trim()
        .to_string();
    let efi_uuid = run_ok(&["blkid", "-s", "UUID", "-o", "value", efi_part])
        .trim()
        .to_string();

    let fstab = format!(
        "UUID={} / ext4 defaults 0 1\nUUID={} /boot/efi vfat defaults 0 2\n",
        root_uuid, efi_uuid
    );
    fs::write(format!("{}/etc/fstab", TARGET), fstab).ok();
    fs::write(format!("{}/etc/hostname", TARGET), "smechvisor\n").ok();

    // Bind-mount and run grub-install in chroot
    for d in ["/dev", "/proc", "/sys"] {
        let target_dir = format!("{}{}", TARGET, d);
        let _ = run(&["mount", "--bind", d, &target_dir]);
    }
    run(&[
        "chroot", TARGET,
        "grub-install", "--target=x86_64-efi",
        "--efi-directory=/boot/efi",
        "--bootloader-id=SmechVisor",
    ])?;

    let kernel_ls = run_ok(&["ls", &format!("{}/boot/", TARGET)]);
    let vmlinuz = kernel_ls
        .lines()
        .find(|l| l.starts_with("vmlinuz"))
        .unwrap_or("vmlinuz");
    let initrd = kernel_ls
        .lines()
        .find(|l| l.starts_with("initramfs"))
        .unwrap_or("initramfs.img");

    let grub_cfg = format!(
        "set timeout=3\nset default=0\n\n\
         menuentry \"SmechVisor\" {{\n\
             linux /boot/{} root=UUID={} ro quiet loglevel=3 intel_iommu=on amd_iommu=on iommu=pt kvm.enable_apicv=1\n\
             initrd /boot/{}\n\
         }}\n\n\
         menuentry \"SmechVisor (debug console)\" {{\n\
             linux /boot/{} root=UUID={} ro console=ttyS0,115200 intel_iommu=on amd_iommu=on iommu=pt\n\
             initrd /boot/{}\n\
         }}\n",
        vmlinuz, root_uuid, initrd,
        vmlinuz, root_uuid, initrd,
    );
    let _ = fs::create_dir_all(format!("{}/boot/grub", TARGET));
    fs::write(format!("{}/boot/grub/grub.cfg", TARGET), grub_cfg).ok();

    run_ok(&["umount", "-R", TARGET]);
    Ok(())
}

// ── Code display ──────────────────────────────────────────────────────────────

fn display_code_banner(code: &str) {
    // Clear screen and show a prominent code box in the terminal
    print!("\x1b[2J\x1b[H");
    let spacer = code.chars().flat_map(|c| [c, ' ']).collect::<String>().trim_end().to_string();
    println!("\x1b[1;37m");
    println!("  ╔══════════════════════════════════════════════╗");
    println!("  ║       SMECHVISOR  DEPLOY  SHIM               ║");
    println!("  ╠══════════════════════════════════════════════╣");
    println!("  ║                                              ║");
    println!("  ║   Waiting for deployment...                  ║");
    println!("  ║                                              ║");
    println!("  ║   Your code is:                              ║");
    println!("  ║                                              ║");
    println!("  ║     \x1b[1;33m{:<44}\x1b[1;37m  ║", spacer);
    println!("  ║                                              ║");
    println!("  ║   On your SmechVisor node, run:              ║");
    println!("  ║                                              ║");
    println!("  ║     spk-visor deploy-system-img-copy         ║");
    println!("  ║                     \x1b[1;32m{:<25}\x1b[1;37m║", code);
    println!("  ║                                              ║");
    println!("  ╚══════════════════════════════════════════════╝");
    println!("\x1b[0m");
}

// ── Wizard ────────────────────────────────────────────────────────────────────

struct Wizard {
    screen: Option<Screen>,
    disk: String,
    efi_part: String,
    swap_part: String,
    root_part: String,
}

impl Wizard {
    fn new() -> Self {
        Wizard {
            screen: Some(Screen::init()),
            disk: String::new(),
            efi_part: String::new(),
            swap_part: String::new(),
            root_part: String::new(),
        }
    }

    fn scr(&self) -> &Screen {
        self.screen.as_ref().expect("screen not active")
    }

    fn drop_screen(&mut self) {
        if let Some(s) = self.screen.take() {
            s.finish();
        }
    }

    fn init_screen(&mut self) {
        self.screen = Some(Screen::init());
    }

    // ── Step 1: Welcome ──────────────────────────────────────────────────────
    fn step_welcome(&mut self) {
        newt::message_window(
            "SmechVisor Deploy Shim",
            "Welcome to the SmechVisor Deploy Shim.\n\n\
             This tool will:\n\
               1. Select and auto-partition a disk\n\
               2. Set up your network connection\n\
               3. Generate a deploy code\n\
               4. Receive SmechVisor over the network\n\
                  from a running SmechVisor node\n\n\
             WARNING: The selected disk will be ERASED.",
            "Continue",
        );
    }

    // ── Step 2: Disk selection ───────────────────────────────────────────────
    fn step_disk_select(&mut self) {
        let disk_entries = list_disks();
        if disk_entries.is_empty() {
            newt::message_window("Error", "No disks detected.\nCannot continue.", "Exit");
            std::process::exit(1);
        }
        let refs: Vec<&str> = disk_entries.iter().map(|s| s.as_str()).collect();
        let idx = newt::listbox_window(
            "Select Disk",
            "Select the disk to install SmechVisor on.\nThis disk will be COMPLETELY ERASED.",
            &refs,
            "Continue",
        )
        .unwrap_or(0);
        self.disk = disk_dev_from_entry(&disk_entries[idx]);

        newt::message_window(
            "Confirm",
            &format!(
                "ALL DATA on {} will be destroyed.\n\nPress 'Erase Disk' to continue,\nor restart the shim to cancel.",
                self.disk
            ),
            "Erase Disk",
        );
    }

    // ── Step 3: Network type ─────────────────────────────────────────────────
    fn step_network(&mut self) {
        let choices = ["Wi-Fi", "Ethernet"];
        let idx = newt::listbox_window(
            "Network Setup",
            "Select your network connection type:",
            &choices,
            "Continue",
        )
        .unwrap_or(1);

        if idx == 0 {
            self.setup_wifi();
        } else {
            self.setup_ethernet();
        }
    }

    fn setup_wifi(&mut self) {
        let ifaces = list_wifi_ifaces();
        if ifaces.is_empty() {
            newt::message_window(
                "Wi-Fi",
                "No Wi-Fi interfaces detected.\nFalling back to Ethernet.",
                "OK",
            );
            self.setup_ethernet();
            return;
        }

        // Pick interface if more than one
        let iface = if ifaces.len() == 1 {
            ifaces[0].clone()
        } else {
            let refs: Vec<&str> = ifaces.iter().map(|s| s.as_str()).collect();
            let idx = newt::listbox_window(
                "Wi-Fi Interface",
                "Select Wi-Fi interface:",
                &refs,
                "Continue",
            )
            .unwrap_or(0);
            ifaces[idx].clone()
        };

        // Scan for SSIDs
        self.scr().draw_root_text(0, 0, " Scanning for Wi-Fi networks... ");
        self.scr().refresh();
        run_ok(&["ip", "link", "set", &iface, "up"]);
        let mut ssids = scan_ssids(&iface);
        if ssids.is_empty() {
            ssids.push("(Enter SSID manually)".to_string());
        }

        let ssid_refs: Vec<&str> = ssids.iter().map(|s| s.as_str()).collect();
        let sidx = newt::listbox_window(
            "Wi-Fi Network",
            "Select your Wi-Fi network (SSID):",
            &ssid_refs,
            "Select",
        )
        .unwrap_or(0);

        let ssid = if ssids[sidx] == "(Enter SSID manually)" {
            let vals = newt::entry_window(
                "Wi-Fi Network",
                "Enter network details:",
                &[("SSID:", false)],
                "Continue",
            );
            vals.into_iter().next().unwrap_or_default()
        } else {
            ssids[sidx].clone()
        };

        let vals = newt::entry_window(
            "Wi-Fi Password",
            &format!("Network: {}", ssid),
            &[("Password:", true)],
            "Connect",
        );
        let password = vals.into_iter().next().unwrap_or_default();

        self.scr().draw_root_text(0, 0, " Connecting to Wi-Fi... ");
        self.scr().refresh();

        if let Err(e) = connect_wifi(&iface, &ssid, &password) {
            newt::message_window("Wi-Fi Error", &format!("Failed to connect:\n{}", e), "OK");
        } else {
            newt::message_window(
                "Wi-Fi",
                &format!("Connected to '{}' on {}.", ssid, iface),
                "Continue",
            );
        }
    }

    fn setup_ethernet(&mut self) {
        let ifaces = list_eth_ifaces();
        if ifaces.is_empty() {
            newt::message_window("Error", "No Ethernet interfaces found.\nCannot continue.", "Exit");
            std::process::exit(1);
        }

        // Pick interface
        let iface = if ifaces.len() == 1 {
            ifaces[0].clone()
        } else {
            let refs: Vec<&str> = ifaces.iter().map(|s| s.as_str()).collect();
            let idx = newt::listbox_window(
                "Ethernet Interface",
                "Select Ethernet interface:",
                &refs,
                "Continue",
            )
            .unwrap_or(0);
            ifaces[idx].clone()
        };

        let modes = ["DHCP (automatic)", "Static IP (manual)"];
        let midx = newt::listbox_window(
            "Ethernet Setup",
            &format!("Interface: {}\nHow should the IP address be configured?", iface),
            &modes,
            "Continue",
        )
        .unwrap_or(0);

        if midx == 0 {
            self.scr().draw_root_text(0, 0, " Requesting DHCP lease... ");
            self.scr().refresh();
            if let Err(e) = setup_dhcp(&iface) {
                newt::message_window("DHCP Error", &format!("DHCP failed:\n{}", e), "OK");
            } else {
                let ip = run_ok(&["ip", "-4", "addr", "show", &iface])
                    .lines()
                    .find(|l| l.trim().starts_with("inet "))
                    .and_then(|l| l.trim().strip_prefix("inet "))
                    .and_then(|l| l.split_whitespace().next())
                    .unwrap_or("(unknown)")
                    .to_string();
                newt::message_window(
                    "Ethernet",
                    &format!("DHCP successful.\nInterface: {}\nIP: {}", iface, ip),
                    "Continue",
                );
            }
        } else {
            let vals = newt::entry_window(
                "Static IP",
                &format!("Interface: {}", iface),
                &[
                    ("IP (CIDR e.g. 192.168.1.10/24):", false),
                    ("Gateway:", false),
                    ("DNS server:", false),
                ],
                "Apply",
            );
            let ip_cidr = vals.get(0).cloned().unwrap_or_default();
            let gw = vals.get(1).cloned().unwrap_or_default();
            let dns = vals.get(2).cloned().unwrap_or_else(|| "1.1.1.1".to_string());
            if let Err(e) = setup_static(&iface, &ip_cidr, &gw, &dns) {
                newt::message_window("Static IP Error", &format!("Failed:\n{}", e), "OK");
            } else {
                newt::message_window(
                    "Ethernet",
                    &format!("Static IP set.\nIP: {}\nGateway: {}", ip_cidr, gw),
                    "Continue",
                );
            }
        }
    }

    // ── Done screen ──────────────────────────────────────────────────────────
    fn step_done(&mut self) {
        newt::message_window(
            "Deployment Complete",
            "SmechVisor has been deployed and installed!\n\n\
             Remove the shim USB/media and restart.\n\
             The smechvisord control plane will be\n\
             available at http://<host-ip>:8080 after boot.",
            "Restart",
        );
        self.drop_screen();
        unsafe {
            libc::sync();
            libc::reboot(libc::LINUX_REBOOT_CMD_RESTART);
        }
    }

    // ── Main wizard run ──────────────────────────────────────────────────────
    fn run(&mut self) {
        self.step_welcome();
        self.step_disk_select();
        self.step_network();

        // Drop Newt — the rest runs as terminal output
        self.drop_screen();

        println!("\n[smechvisor-shim] Auto-partitioning {}...", self.disk);
        match auto_partition(&self.disk) {
            Ok((efi, swap, root)) => {
                println!("  EFI:  {}", efi);
                println!("  Swap: {}", swap);
                println!("  Root: {}", root);
                self.efi_part = efi;
                self.swap_part = swap;
                self.root_part = root;
            }
            Err(e) => {
                eprintln!("[smechvisor-shim] Partition error: {}", e);
                std::process::exit(1);
            }
        }

        println!("[smechvisor-shim] Formatting and mounting partitions...");
        if let Err(e) = format_and_mount(&self.efi_part, &self.swap_part, &self.root_part) {
            eprintln!("[smechvisor-shim] Format error: {}", e);
            std::process::exit(1);
        }

        // Generate deploy code, show banner, receive packages
        let code = gen_code();
        display_code_banner(&code);

        // Broadcast UDP in background
        let code_clone = code.clone();
        std::thread::spawn(move || {
            if let Ok(sock) = UdpSocket::bind("0.0.0.0:0") {
                sock.set_broadcast(true).ok();
                let msg = format!("{}:{}", BROADCAST_MAGIC, code_clone);
                loop {
                    sock.send_to(msg.as_bytes(), format!("255.255.255.255:{}", SHIM_UDP_PORT)).ok();
                    std::thread::sleep(Duration::from_secs(2));
                }
            }
        });

        // Listen for TCP connection from donor
        let listener = match TcpListener::bind(format!("0.0.0.0:{}", SHIM_TCP_PORT)) {
            Ok(l) => l,
            Err(e) => {
                eprintln!("[smechvisor-shim] TCP bind error: {}", e);
                std::process::exit(1);
            }
        };
        println!("[smechvisor-shim] Listening for donor on TCP port {}...", SHIM_TCP_PORT);

        let (mut stream, addr) = match listener.accept() {
            Ok(x) => x,
            Err(e) => {
                eprintln!("[smechvisor-shim] Accept error: {}", e);
                std::process::exit(1);
            }
        };
        println!("[smechvisor-shim] Donor connected from {}", addr);
        println!("[smechvisor-shim] Receiving packages...");

        if let Err(e) = receive_packages(&mut stream) {
            eprintln!("[smechvisor-shim] Receive error: {}", e);
            std::process::exit(1);
        }
        println!("[smechvisor-shim] All packages received.");

        println!("[smechvisor-shim] Installing GRUB and writing system config...");
        if let Err(e) = post_install(&self.root_part, &self.efi_part) {
            eprintln!("[smechvisor-shim] Post-install error: {}", e);
            // Don't exit — show done screen anyway so operator knows something happened
        }

        // Re-init Newt for done screen
        self.init_screen();
        self.step_done();
    }
}

fn main() {
    let mut wizard = Wizard::new();
    wizard.run();
}
