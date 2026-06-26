mod newt;

use std::fs;
use std::io::Read;
use std::process::Command;

use newt::Screen;

const TARGET: &str = "/mnt/target";
// Packages are served from a GitHub Release rather than GerritHub's REST
// file-content API -- that API works for small files but silently
// truncates large binaries (confirmed: base-system.tar.xz fetched
// incomplete through it). GitHub Releases serves raw files directly with
// no such limit. See Smech-Labs/spk's README for the full story.
const RELEASE_BASE_URL: &str = "https://github.com/Smech-Labs/SmechDeploy/releases/download/v1.0.0-packages";

const BASE_PACKAGES: &[&str] = &["base-system", "kernel-modules", "firmware", "bootloader-grub"];
const KDE_PACKAGES: &[&str] = &["kde-frameworks", "plasma", "qt6", "mesa-graphics"];

const LANGUAGES: &[&str] = &["English (US)"];
const COUNTRIES: &[&str] = &["United States", "Romania", "United Kingdom", "Germany", "France"];
const TIMEZONES: &[&str] = &[
    "UTC",
    "Europe/Bucharest",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles",
];

fn run(cmd: &[&str]) -> Result<String, String> {
    run_input(cmd, None)
}

fn run_input(cmd: &[&str], input: Option<&str>) -> Result<String, String> {
    use std::io::Write;
    use std::process::Stdio;
    let mut child = Command::new(cmd[0])
        .args(&cmd[1..])
        .stdin(if input.is_some() { Stdio::piped() } else { Stdio::null() })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{}: spawn failed: {}", cmd[0], e))?;
    if let Some(data) = input {
        if let Some(stdin) = child.stdin.as_mut() {
            let _ = stdin.write_all(data.as_bytes());
        }
    }
    let out = child.wait_with_output().map_err(|e| e.to_string())?;
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    if !out.status.success() {
        return Err(format!("{} failed:\n{}", cmd.join(" "), combined));
    }
    Ok(combined)
}

fn run_ok(cmd: &[&str]) -> String {
    run(cmd).unwrap_or_default()
}

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
                disks.push(format!("/dev/{}", name));
            }
        }
    }
    disks.sort();
    disks
}

fn list_partitions(disk: &str) -> Vec<String> {
    let base = disk.trim_start_matches("/dev/");
    let mut parts = Vec::new();
    let sysdir = format!("/sys/block/{}", base);
    if let Ok(entries) = fs::read_dir(&sysdir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name.starts_with(base) && name != base {
                parts.push(format!("/dev/{}", name));
            }
        }
    }
    parts.sort();
    parts
}

fn list_net_ifaces() -> Vec<String> {
    let mut ifaces = Vec::new();
    if let Ok(entries) = fs::read_dir("/sys/class/net") {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name != "lo" {
                ifaces.push(name);
            }
        }
    }
    ifaces.sort();
    ifaces
}

fn detect_cpu_vendor() -> String {
    if let Ok(data) = fs::read_to_string("/proc/cpuinfo") {
        if data.contains("GenuineIntel") {
            return "intel".to_string();
        }
        if data.contains("AuthenticAMD") {
            return "amd".to_string();
        }
    }
    "unknown".to_string()
}

fn ensure_network(timeout: u32) {
    for iface in list_net_ifaces() {
        let t = timeout.to_string();
        let _ = run(&["dhcpcd", "-t", &t, &iface]);
    }
}

fn fetch_package(name: &str) -> Result<Vec<u8>, String> {
    let url = format!("{}/{}.tar.xz", RELEASE_BASE_URL, name);
    let mut resp = ureq::get(&url).call().map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    resp.body_mut()
        .as_reader()
        .read_to_end(&mut buf)
        .map_err(|e| e.to_string())?;
    Ok(buf)
}

fn fetch_and_extract(name: &str, target: &str) -> Result<(), String> {
    let data = fetch_package(name)?;
    let tarpath = format!("/tmp/{}.tar.xz", name);
    fs::write(&tarpath, &data).map_err(|e| e.to_string())?;
    run(&["tar", "-xJf", &tarpath, "-C", target])?;
    let _ = fs::remove_file(&tarpath);
    Ok(())
}

fn create_user(target: &str, username: &str, password: &str) {
    let uid = 1000;
    let hash = pwhash::sha512_crypt::hash(password).unwrap_or_else(|_| password.to_string());
    let hash = hash.trim();

    let _ = append_file(
        &format!("{}/etc/passwd", target),
        &format!("{}:x:{}:{}:{}:/home/{}:/bin/bash\n", username, uid, uid, username, username),
    );
    let _ = append_file(
        &format!("{}/etc/shadow", target),
        &format!("{}:{}:19000:0:99999:7:::\n", username, hash),
    );
    let _ = append_file(
        &format!("{}/etc/group", target),
        &format!("{}:x:{}:\n", username, uid),
    );
    let home = format!("{}/home/{}", target, username);
    let _ = fs::create_dir_all(&home);
    let _ = run(&["chown", &format!("{}:{}", uid, uid), &home]);
}

fn append_file(path: &str, data: &str) -> std::io::Result<()> {
    use std::io::Write;
    let mut f = std::fs::OpenOptions::new().append(true).create(true).open(path)?;
    f.write_all(data.as_bytes())
}

fn do_reboot() {
    unsafe {
        libc::sync();
        libc::reboot(libc::LINUX_REBOOT_CMD_RESTART);
    }
}

struct Wizard {
    screen: Screen,
    disk: String,
    boot_part: String,
    swap_part: String,
    root_part: String,
    profile: String,
    cpu_vendor: String,
}

impl Wizard {
    fn new() -> Self {
        Wizard {
            screen: Screen::init(),
            disk: String::new(),
            boot_part: String::new(),
            swap_part: String::new(),
            root_part: String::new(),
            profile: "desktop".to_string(),
            cpu_vendor: String::new(),
        }
    }

    fn step_welcome(&mut self) {
        newt::message_window(
            "SmechOS Install Wizard",
            "Welcome to SmechOS Install Wizard",
            "Continue",
        );
    }

    fn step_language(&mut self) {
        newt::listbox_window("Language Selection", "Select your language:", LANGUAGES, "Continue");
    }

    fn step_country(&mut self) {
        newt::listbox_window("Country Selection", "Select your country:", COUNTRIES, "Continue");
    }

    fn step_timezone(&mut self) {
        newt::listbox_window("Time Zone", "Select your time zone:", TIMEZONES, "Continue");
    }

    fn step_hardware_detect(&mut self) {
        let disks = list_disks();
        let ifaces = list_net_ifaces();
        self.cpu_vendor = detect_cpu_vendor();
        let summary = format!(
            "Disks found: {}\nNetwork interfaces: {}\nCPU vendor: {}",
            if disks.is_empty() { "none".into() } else { disks.join(", ") },
            if ifaces.is_empty() { "none".into() } else { ifaces.join(", ") },
            self.cpu_vendor
        );
        newt::message_window("Hardware Detection", &summary, "Continue");
    }

    fn step_partition(&mut self) {
        let disks = list_disks();
        if disks.is_empty() {
            newt::message_window("Error", "No disks detected. Cannot continue.", "Exit");
            std::process::exit(1);
        }
        let disk_refs: Vec<&str> = disks.iter().map(|s| s.as_str()).collect();
        let idx = newt::listbox_window("Partitioning", "Select the disk to partition:", &disk_refs, "Continue")
            .unwrap_or(0);
        self.disk = disks[idx].clone();

        self.screen.suspend();
        let _ = Command::new("cfdisk").arg(&self.disk).status();
        self.screen.resume();

        std::thread::sleep(std::time::Duration::from_secs(1));
        let parts = list_partitions(&self.disk);
        if parts.is_empty() {
            newt::message_window("Error", &format!("No partitions found on {}.", self.disk), "Exit");
            std::process::exit(1);
        }
        let part_refs: Vec<&str> = parts.iter().map(|s| s.as_str()).collect();

        let bi = newt::listbox_window("Boot Partition", "Select the BOOT (EFI) partition:", &part_refs, "Continue").unwrap_or(0);
        self.boot_part = parts[bi].clone();

        let mut swap_items = vec!["None"];
        swap_items.extend(part_refs.iter());
        let si = newt::listbox_window("Swap Partition (optional)", "Select a SWAP partition, or skip:", &swap_items, "Continue").unwrap_or(0);
        self.swap_part = if si == 0 { String::new() } else { parts[si - 1].clone() };

        let ri = newt::listbox_window("Root Partition", "Select the ROOT partition:", &part_refs, "Continue").unwrap_or(0);
        self.root_part = parts[ri].clone();
    }

    fn step_base_install(&mut self) {
        self.screen.draw_root_text(0, 0, " Installing base system... ");
        self.screen.refresh();

        let _ = run(&["mkfs.vfat", "-F", "32", &self.boot_part]);
        let _ = run(&["mkfs.ext4", "-F", &self.root_part]);
        if !self.swap_part.is_empty() {
            let _ = run(&["mkswap", &self.swap_part]);
        }

        let _ = fs::create_dir_all(TARGET);
        let _ = run(&["mount", &self.root_part, TARGET]);
        let efi_dir = format!("{}/boot/efi", TARGET);
        let _ = fs::create_dir_all(&efi_dir);
        let _ = run(&["mount", &self.boot_part, &efi_dir]);

        ensure_network(15);

        for name in BASE_PACKAGES {
            if let Err(e) = fetch_and_extract(name, TARGET) {
                newt::message_window("Fetch Error", &format!("Failed to fetch {}: {}", name, e), "Continue");
            }
        }

        let root_uuid = run_ok(&["blkid", "-s", "UUID", "-o", "value", &self.root_part]).trim().to_string();
        let boot_uuid = run_ok(&["blkid", "-s", "UUID", "-o", "value", &self.boot_part]).trim().to_string();
        let mut fstab = format!(
            "UUID={} / ext4 defaults 0 1\nUUID={} /boot/efi vfat defaults 0 2\n",
            root_uuid, boot_uuid
        );
        if !self.swap_part.is_empty() {
            let swap_uuid = run_ok(&["blkid", "-s", "UUID", "-o", "value", &self.swap_part]).trim().to_string();
            if !swap_uuid.is_empty() {
                fstab.push_str(&format!("UUID={} swap swap defaults 0 0\n", swap_uuid));
            }
        }
        let _ = fs::write(format!("{}/etc/fstab", TARGET), fstab);
        let _ = fs::write(format!("{}/etc/hostname", TARGET), "smechos\n");

        create_user(TARGET, "smech", "smechos");
    }

    fn step_network(&mut self) {
        let ifaces = list_net_ifaces();
        if ifaces.is_empty() {
            newt::message_window("Network", "No network interfaces detected. Skipping.", "Continue");
            return;
        }
        let eth: Vec<&String> = ifaces.iter().filter(|i| !i.starts_with("wl")).collect();
        let wifi: Vec<&String> = ifaces.iter().filter(|i| i.starts_with("wl")).collect();

        let mut items: Vec<String> = Vec::new();
        for i in &eth {
            items.push(format!("{} (Ethernet, DHCP)", i));
        }
        for i in &eth {
            items.push(format!("{} (Ethernet, Static IP)", i));
        }
        for i in &wifi {
            items.push(format!("{} (Wi-Fi - requires wpa_supplicant, not yet bundled)", i));
        }
        let item_refs: Vec<&str> = items.iter().map(|s| s.as_str()).collect();
        let idx = match newt::listbox_window("Network Provisioning", "Configure networking:", &item_refs, "Continue") {
            Some(i) => i,
            None => return,
        };

        let n_eth = eth.len();
        if idx < n_eth {
            let iface = eth[idx];
            let _ = run(&["dhcpcd", "-t", "15", iface]);
            // This minimal environment has no dhcpcd-hooks (no
            // /usr/lib/dhcpcd/dhcpcd-hooks/01-resolv.conf), so dhcpcd
            // obtains a lease/IP but never actually writes /etc/resolv.conf
            // itself -- confirmed by testing in QEMU: DHCP succeeds but
            // every subsequent package fetch fails with "Temporary failure
            // in name resolution". Write a working resolver directly.
            let _ = fs::write("/etc/resolv.conf", "nameserver 8.8.8.8\nnameserver 1.1.1.1\n");
        } else if idx < n_eth * 2 {
            let iface = eth[idx - n_eth];
            let values = newt::entry_window(
                "Static IP Configuration",
                &format!("Configure {}:", iface),
                &[("IP address (e.g. 192.168.1.50/24)", false), ("Gateway", false), ("DNS server", false)],
                "Continue",
            );
            let (ip_cidr, gateway, dns) = (&values[0], &values[1], &values[2]);
            let _ = run(&["ip", "addr", "add", ip_cidr, "dev", iface]);
            let _ = run(&["ip", "link", "set", iface, "up"]);
            let _ = run(&["ip", "route", "add", "default", "via", gateway]);
            let conf = format!(
                "\ninterface {}\nstatic ip_address={}\nstatic routers={}\nstatic domain_name_servers={}\n",
                iface, ip_cidr, gateway, dns
            );
            let _ = append_file(&format!("{}/etc/dhcpcd.conf", TARGET), &conf);
            // Same as the DHCP branch: the installer's own environment
            // needs working DNS right now, immediately, to fetch packages
            // -- not just the persisted config for the installed system's
            // future boots.
            let _ = fs::write("/etc/resolv.conf", format!("nameserver {}\n", dns));
        } else {
            newt::message_window(
                "Wi-Fi Not Yet Supported",
                "Wi-Fi connection requires wpa_supplicant, which isn't bundled in this installer yet.\nUse Ethernet for this install.",
                "Continue",
            );
        }
    }

    fn step_profile(&mut self) {
        let idx = newt::listbox_window(
            "Profile Selection",
            "Select install profile:",
            &["KDE Plasma Desktop", "Server (no desktop)", "(more coming soon)"],
            "Continue",
        )
        .unwrap_or(0);
        self.profile = match idx {
            0 => "desktop".to_string(),
            1 => "server".to_string(),
            _ => "none".to_string(),
        };
    }

    fn step_userland(&mut self) {
        newt::message_window(
            "Additional Userland Applications",
            "No additional userland applications are available yet.\nMore coming soon.",
            "Continue",
        );
    }

    fn step_install_profile_packages(&mut self) {
        if self.profile == "desktop" {
            self.screen.draw_root_text(0, 0, " Installing KDE Plasma Desktop... ");
            self.screen.refresh();
            for name in KDE_PACKAGES {
                if let Err(e) = fetch_and_extract(name, TARGET) {
                    newt::message_window("Fetch Error", &format!("Failed to fetch {}: {}", name, e), "Continue");
                }
            }
        }
    }

    fn step_microcode(&mut self) {
        let ucode_dir = match self.cpu_vendor.as_str() {
            "intel" => Some("intel-ucode"),
            "amd" => Some("amd-ucode"),
            _ => None,
        };
        let mut msg = format!("Detected CPU vendor: {}\n", self.cpu_vendor);
        if let Some(dir) = ucode_dir {
            let path = format!("{}/usr/lib/firmware/{}", TARGET, dir);
            if std::path::Path::new(&path).is_dir() {
                msg.push_str(&format!("Microcode for {} is present in /usr/lib/firmware/{}.", self.cpu_vendor.to_uppercase(), dir));
            } else {
                msg.push_str("Microcode data not found (firmware package may not have included it).");
            }
        } else {
            msg.push_str("Unknown CPU vendor; skipping microcode check.");
        }
        newt::message_window("CPU Microcode", &msg, "Continue");
    }

    fn step_grub_install(&mut self) {
        self.screen.draw_root_text(0, 0, " Installing bootloader... ");
        self.screen.refresh();
        for d in ["/dev", "/proc", "/sys"] {
            let target_dir = format!("{}{}", TARGET, d);
            let _ = run(&["mount", "--bind", d, &target_dir]);
        }
        if let Err(e) = run(&[
            "chroot", TARGET, "grub-install", "--target=x86_64-efi",
            "--efi-directory=/boot/efi", "--bootloader-id=SmechOS",
        ]) {
            newt::message_window("GRUB Error", &e, "Continue");
        }
        let _ = run(&["chroot", TARGET, "grub-mkconfig", "-o", "/boot/grub/grub.cfg"]);
        let _ = run(&["umount", "-R", TARGET]);
    }

    fn step_done(&mut self) {
        newt::message_window(
            "Installation Complete",
            "SmechOS has installed successfully!\n\nTo boot SmechOS, remove the installation media and restart the computer.",
            "Restart",
        );
        self.screen.finish();
        do_reboot();
    }

    fn run(&mut self) {
        self.step_welcome();
        self.step_language();
        self.step_country();
        self.step_timezone();
        self.step_hardware_detect();
        self.step_network();
        self.step_partition();
        self.step_base_install();
        self.step_profile();
        self.step_install_profile_packages();
        self.step_userland();
        self.step_microcode();
        self.step_grub_install();
        self.step_done();
    }
}

fn main() {
    let mut wizard = Wizard::new();
    wizard.run();
}
