mod newt;

use std::fs;
use std::process::Command;

use newt::Screen;

const TARGET: &str = "/mnt/target";
const ISO_MOUNT: &str = "/mnt/iso";
// Volume label burned into the install ISO by 15_build_smechvisor_install_iso.sh
const ISO_LABEL: &str = "SMECHVISOR_INST";
const PKGS_DIR: &str = "/mnt/iso/packages";

const VISOR_PACKAGES: &[&str] = &["smechvisor-base", "smechvisor-daemon"];

const TIMEZONES: &[&str] = &[
    "UTC",
    "Europe/Bucharest",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles",
];

fn run(cmd: &[&str]) -> Result<String, String> {
    use std::io::Write;
    use std::process::Stdio;
    let mut child = Command::new(cmd[0])
        .args(&cmd[1..])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{}: spawn failed: {}", cmd[0], e))?;
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

// Find the block device carrying ISO_LABEL and mount it at ISO_MOUNT.
// Tries optical drives first, then all block devices via blkid.
fn find_and_mount_iso() -> Result<(), String> {
    let _ = fs::create_dir_all(ISO_MOUNT);

    // Try common optical/USB block devices
    let candidates: Vec<String> = {
        let mut v = Vec::new();
        if let Ok(entries) = fs::read_dir("/sys/block") {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().into_owned();
                if name.starts_with("sr") || name.starts_with("sd") || name.starts_with("vd") {
                    v.push(format!("/dev/{}", name));
                }
            }
        }
        v.sort();
        v
    };

    for dev in &candidates {
        let label = run_ok(&["blkid", "-s", "LABEL", "-o", "value", dev]);
        if label.trim() == ISO_LABEL {
            return run(&["mount", "-o", "ro", dev, ISO_MOUNT]).map(|_| ());
        }
    }

    Err(format!(
        "Could not find a device with label {}.\nMake sure the install media is attached.",
        ISO_LABEL
    ))
}

fn local_extract(name: &str, target: &str) -> Result<(), String> {
    let tarpath = format!("{}/{}.tar.xz", PKGS_DIR, name);
    if !std::path::Path::new(&tarpath).exists() {
        return Err(format!("Package not found on ISO: {}", tarpath));
    }
    run(&["tar", "-xJf", &tarpath, "-C", target]).map(|_| ())
}

fn create_user(target: &str, username: &str, password: &str) {
    let uid = 1000;
    let hash = pwhash::sha512_crypt::hash(password).unwrap_or_else(|_| password.to_string());
    let hash = hash.trim();

    let _ = append_file(
        &format!("{}/etc/passwd", target),
        &format!("{}:x:{}:{}:{}:/home/{}:/bin/sh\n", username, uid, uid, username, username),
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
            cpu_vendor: String::new(),
        }
    }

    fn step_welcome(&mut self) {
        newt::message_window(
            "SmechVisor Install Wizard",
            "Welcome to the SmechVisor installer.\n\nThis wizard will install SmechVisor -- a sovereign\nbare-metal hypervisor OS -- onto your disk.\n\nAll packages are installed from the local ISO.\nNo internet connection is required.",
            "Continue",
        );
    }

    fn step_timezone(&mut self) {
        newt::listbox_window("Time Zone", "Select your time zone:", TIMEZONES, "Continue");
    }

    fn step_hardware_detect(&mut self) {
        let disks = list_disks();
        self.cpu_vendor = detect_cpu_vendor();
        let summary = format!(
            "Disks found: {}\nCPU vendor: {}",
            if disks.is_empty() { "none".into() } else { disks.join(", ") },
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
        let idx = newt::listbox_window(
            "Partitioning",
            "Select the disk to install SmechVisor on:",
            &disk_refs,
            "Continue",
        )
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

        let bi = newt::listbox_window(
            "Boot Partition",
            "Select the BOOT (EFI) partition:",
            &part_refs,
            "Continue",
        )
        .unwrap_or(0);
        self.boot_part = parts[bi].clone();

        let mut swap_items = vec!["None"];
        swap_items.extend(part_refs.iter().copied());
        let si = newt::listbox_window(
            "Swap Partition (optional)",
            "Select a SWAP partition, or skip:",
            &swap_items,
            "Continue",
        )
        .unwrap_or(0);
        self.swap_part = if si == 0 { String::new() } else { parts[si - 1].clone() };

        let ri = newt::listbox_window(
            "Root Partition",
            "Select the ROOT partition:",
            &part_refs,
            "Continue",
        )
        .unwrap_or(0);
        self.root_part = parts[ri].clone();
    }

    fn step_mount_iso(&mut self) {
        self.screen.draw_root_text(0, 0, " Mounting install media... ");
        self.screen.refresh();
        if let Err(e) = find_and_mount_iso() {
            newt::message_window("Install Media Error", &e, "Exit");
            std::process::exit(1);
        }
    }

    fn step_install(&mut self) {
        self.screen.draw_root_text(0, 0, " Installing SmechVisor... ");
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

        for name in VISOR_PACKAGES {
            self.screen.draw_root_text(0, 0, &format!(" Installing {}... ", name));
            self.screen.refresh();
            if let Err(e) = local_extract(name, TARGET) {
                newt::message_window("Install Error", &format!("Failed to install {}: {}", name, e), "Continue");
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
        let _ = fs::write(format!("{}/etc/hostname", TARGET), "smechvisor\n");

        create_user(TARGET, "smech", "smechos");
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
                msg.push_str(&format!(
                    "Microcode for {} is present in /usr/lib/firmware/{}.",
                    self.cpu_vendor.to_uppercase(),
                    dir
                ));
            } else {
                msg.push_str("Microcode data not found in smechvisor-base package.");
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
            "--efi-directory=/boot/efi", "--bootloader-id=SmechVisor",
        ]) {
            newt::message_window("GRUB Error", &e, "Continue");
        }
        // Write a fixed GRUB config that boots SmechVisor with IOMMU enabled
        let grub_cfg = format!(
            "{}/boot/grub/grub.cfg",
            TARGET
        );
        let kernel = run_ok(&["ls", &format!("{}/boot/", TARGET)]);
        let vmlinuz = kernel
            .lines()
            .find(|l| l.starts_with("vmlinuz"))
            .unwrap_or("vmlinuz");
        let initrd = kernel
            .lines()
            .find(|l| l.starts_with("initramfs"))
            .unwrap_or("initramfs.img");
        let cfg = format!(
            "set timeout=3\nset default=0\n\nmenuentry \"SmechVisor\" {{\n    linux /boot/{} root=UUID={} ro quiet loglevel=3 intel_iommu=on amd_iommu=on iommu=pt kvm.enable_apicv=1\n    initrd /boot/{}\n}}\n\nmenuentry \"SmechVisor (debug console)\" {{\n    linux /boot/{} root=UUID={} ro console=ttyS0,115200 intel_iommu=on amd_iommu=on iommu=pt\n    initrd /boot/{}\n}}\n",
            vmlinuz,
            run_ok(&["blkid", "-s", "UUID", "-o", "value", &self.root_part]).trim(),
            initrd,
            vmlinuz,
            run_ok(&["blkid", "-s", "UUID", "-o", "value", &self.root_part]).trim(),
            initrd,
        );
        let _ = fs::write(&grub_cfg, cfg);
        let _ = run(&["umount", "-R", TARGET]);
    }

    fn step_done(&mut self) {
        newt::message_window(
            "Installation Complete",
            "SmechVisor has been installed successfully!\n\nRemove the install media and restart.\nThe smechvisord control plane will be\navailable at http://<host-ip>:8080 after boot.",
            "Restart",
        );
        self.screen.finish();
        do_reboot();
    }

    fn run(&mut self) {
        self.step_welcome();
        self.step_timezone();
        self.step_hardware_detect();
        self.step_partition();
        self.step_mount_iso();
        self.step_install();
        self.step_microcode();
        self.step_grub_install();
        self.step_done();
    }
}

fn main() {
    let mut wizard = Wizard::new();
    wizard.run();
}
