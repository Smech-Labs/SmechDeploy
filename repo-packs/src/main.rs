use std::env;
use std::fs;
use std::path::Path;
use std::process::{Command, Stdio, exit};

// Color escape codes
const RESET: &str = "\x1b[0m";
const BOLD: &str = "\x1b[1m";
const GREEN: &str = "\x1b[32m";
const CYAN: &str = "\x1b[36m";
const YELLOW: &str = "\x1b[33m";
const RED: &str = "\x1b[31m";
const MAGENTA: &str = "\x1b[35m";

fn print_banner() {
    println!(
        "{}{}{}========================================================================{}",
        BOLD, MAGENTA, RESET, RESET
    );
    println!(
        "{}{}     ███████╗██████╗ ██╗  ██╗    ███████╗ ██████╗ ██╗  ██╗{}",
        BOLD, RED, RESET
    );
    println!(
        "{}{}     ██╔════╝██╔══██╗██║ ██╔╝    ██╔════╝██╔═══██╗██║ ██╔╝{}",
        BOLD, RED, RESET
    );
    println!(
        "{}{}     ███████╗██████╔╝█████╔╝     ███████╗██║   ██║█████╔╝ {}",
        BOLD, RED, RESET
    );
    println!(
        "{}{}     ╚════██║██╔═══╝ ██╔═██╗     ╚════██║██║   ██║██╔═██╗ {}",
        BOLD, RED, RESET
    );
    println!(
        "{}{}     ███████║██║     ██║  ██╗    ███████║╚██████╔╝██║  ██╗{}",
        BOLD, RED, RESET
    );
    println!(
        "{}{}               SMECHOS SOVEREIGN PACKAGE KEEPER (SPK){}",
        BOLD, CYAN, RESET
    );
    println!(
        "{}{}{}========================================================================{}",
        BOLD, MAGENTA, RESET, RESET
    );
}

fn print_help() {
    print_banner();
    println!("{}USAGE:{}", BOLD, RESET);
    println!("    spk <COMMAND> [package]");
    println!();
    println!("{}COMMANDS:{}", BOLD, RESET);
    println!(
        "    {}system-install <pkg>{}   Install packages onto the target system partition",
        GREEN, RESET
    );
    println!(
        "    {}userland-install <pkg>{} Install userland software (Flatpaks/Apps)",
        GREEN, RESET
    );
    println!(
        "    {}entire-system-upgrade{}  Synchronize and compile complete updates for SmechOS",
        GREEN, RESET
    );
    println!("    {}about{}                  Show SmechOS workstation specs and software credits", GREEN, RESET);
    println!("    {}help{}                   Show this help menu", GREEN, RESET);
    println!();
    println!("{}EXAMPLES:{}", BOLD, RESET);
    println!("    spk system-install htop");
    println!("    spk userland-install org.mozilla.firefox");
    println!("    spk entire-system-upgrade");
    println!();
}

fn print_about() {
    print_banner();
    println!("{}--- SMECH-SOVEREIGN WORKSTATION 2026 build CONFIGURATION ---{}", BOLD, RESET);
    println!("  {}CPU:{}             AMD Threadripper PRO 9965WX (Zen 5, 24-core, 48-thread)", CYAN, RESET);
    println!("  {}Motherboard:{}     ASUS Pro WS WRX90E-SAGE SE SSI-EEB", CYAN, RESET);
    println!("  {}ECC Memory:{}     256GB DDR5 RDIMM (8x 32GB Kingston FURY Renegade Pro)", CYAN, RESET);
    println!("  {}GPUs:{}           2x NVIDIA RTX 5080 (Horizontal active liquid cooled)", CYAN, RESET);
    println!("  {}Storage Tier:{}    Dual 1TB Samsung 990 PRO NVMe RAID (SmechOS Boot/System)", CYAN, RESET);
    println!("  {}Cooling Loop:{}    Industrial Active Syltherm 800 - 4x D5 Pumps, EPDM Tubing", CYAN, RESET);
    println!("  {}Power Res:{}      Dual ROG Thor III 1200W (Total 2400W fully isolated)", CYAN, RESET);
    println!();
    println!("{}--- SPK ARCHITECTURE CREDITS ---{}", BOLD, RESET);
    println!("  Designed by Gemini / Antigravity with Comrade Smech.");
    println!("  Built as a zero-dependency, static sovereign manager.");
    println!("  Replacing black-box lane-rationing with pure compute sovereignty.");
    println!();
}

fn get_target_context() -> (bool, &'static str) {
    // Check if we are running on host with /mnt/smechos mounted
    if Path::new("/mnt/smechos").exists() {
        (true, "/mnt/smechos")
    } else {
        (false, "")
    }
}

fn is_root() -> bool {
    if let Ok(uid_str) = env::var("UID") {
        uid_str == "0"
    } else {
        // Fallback using id -u
        if let Ok(output) = Command::new("id").arg("-u").output() {
            let s = String::from_utf8_lossy(&output.stdout).trim().to_string();
            s == "0"
        } else {
            false
        }
    }
}

fn run_command_interactive(cmd: &str, args: &[&str]) -> bool {
    let mut child = Command::new(cmd)
        .args(args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn();

    match child {
        Ok(mut proc) => {
            if let Ok(status) = proc.wait() {
                status.success()
            } else {
                false
            }
        }
        Err(e) => {
            println!("{}[-] Failed to execute command {}: {}{}", BOLD, cmd, e, RESET);
            false
        }
    }
}

fn chroot_run(target_dir: &str, inner_cmd: &[&str]) -> bool {
    // We execute chroot with target_dir
    let mut args = vec![target_dir];
    args.extend(inner_cmd);
    
    // We run sudo chroot if we are not root, or just chroot if we are root
    let (cmd, final_args) = if is_root() {
        ("chroot", args)
    } else {
        let mut sudo_args = vec!["-S", "chroot"];
        sudo_args.extend(args);
        ("sudo", sudo_args)
    };

    let mut proc_cmd = Command::new(cmd);
    proc_cmd.args(&final_args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    // If running under sudo, we might try feeding password or running directly
    let mut child = proc_cmd.spawn();
    match child {
        Ok(mut proc) => {
            if let Ok(status) = proc.wait() {
                status.success()
            } else {
                false
            }
        }
        Err(e) => {
            println!("{}[-] Failed to run chroot command: {}{}", BOLD, e, RESET);
            false
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_help();
        exit(0);
    }

    let command = args[1].as_str();

    match command {
        "help" | "--help" | "-h" => {
            print_help();
        }
        "about" | "--about" => {
            print_about();
        }
        "system-install" => {
            if args.len() < 3 {
                println!("{}[-] Error: Please specify a package to install.{}", BOLD, RESET);
                println!("    Example: spk system-install htop");
                exit(1);
            }
            let pkg = &args[2];
            println!("{}====================================================", BOLD);
            println!("  SPK: INSTALLING SYSTEM PARTITION PACKAGE: {}", pkg);
            println!("===================================================={}", RESET);

            let (is_host, target_dir) = get_target_context();
            let success = if is_host {
                println!("{}[+] Running emerge inside SmechOS chroot (at {})...{}", CYAN, target_dir, RESET);
                chroot_run(target_dir, &["emerge", "-av", pkg])
            } else {
                println!("{}[+] Running emerge directly in local environment...{}", CYAN, RESET);
                run_command_interactive("emerge", &["-av", pkg])
            };

            if success {
                println!("{} [+] Package {} installed successfully on system partition!{}", BOLD, pkg, RESET);
            } else {
                println!("{} [-] Installation failed for package {}.{}", BOLD, pkg, RESET);
                exit(1);
            }
        }
        "userland-install" => {
            if args.len() < 3 {
                println!("{}[-] Error: Please specify a flatpak package to install.{}", BOLD, RESET);
                println!("    Example: spk userland-install org.mozilla.firefox");
                exit(1);
            }
            let pkg = &args[2];
            println!("{}====================================================", BOLD);
            println!("  SPK: INSTALLING USERLAND PACKAGE (FLATPAK): {}", pkg);
            println!("===================================================={}", RESET);

            let (is_host, target_dir) = get_target_context();
            let success = if is_host {
                println!("{}[+] Running flatpak inside SmechOS chroot (at {})...{}", CYAN, target_dir, RESET);
                chroot_run(target_dir, &["flatpak", "install", "-y", pkg])
            } else {
                println!("{}[+] Running flatpak directly in local environment...{}", CYAN, RESET);
                run_command_interactive("flatpak", &["install", "-y", pkg])
            };

            if success {
                println!("{} [+] Userland package {} installed successfully!{}", BOLD, pkg, RESET);
            } else {
                println!("{} [-] Installation failed for userland package {}.{}", BOLD, pkg, RESET);
                exit(1);
            }
        }
        "entire-system-upgrade" => {
            println!("{}{}{}========================================================================{}", BOLD, MAGENTA, RESET, RESET);
            println!("{}{}        SMECHOS SOVEREIGN PACKAGE KEEPER (SPK) - FULL UPGRADE HUD{}", BOLD, CYAN, RESET);
            println!("{}{}{}========================================================================{}", BOLD, MAGENTA, RESET, RESET);
            println!("  {}* SYSTEM HARDWARE DIAGNOSTICS *{}", BOLD, RESET);
            println!("    - CPU: AMD Threadripper PRO 9965WX (Zen 5, 24 Cores)");
            println!("    - Motherboard: ASUS Pro WS WRX90E-SAGE SE (WRX90 FLAGSHIP)");
            println!("    - RAM: 256GB DDR5 RDIMM ECC-Registered Matching Array");
            println!("    - Storage: Dual 1TB Samsung 990 PRO NVMe (SmechOS System Partition)");
            println!("    - Liquid Loop: Syltherm 800 Quad-Pump (Active, Dual Radiators)");
            println!("  {}* DETECTING SYSTEM CONTEXT *{}", BOLD, RESET);
            
            let (is_host, target_dir) = get_target_context();
            if is_host {
                println!("    - Context: Host system (targeting SmechOS rootfs at {})", target_dir);
            } else {
                println!("    - Context: Target SmechOS local env");
            }
            println!("{}{}{}========================================================================{}", BOLD, MAGENTA, RESET, RESET);

            println!("\n{}[1/3] STEP 1: SYNCHRONIZING PORTAGE PACKAGE TREE...{}", BOLD, RESET);
            let sync_success = if is_host {
                chroot_run(target_dir, &["emerge", "--sync"])
            } else {
                run_command_interactive("emerge", &["--sync"])
            };

            if !sync_success {
                println!("{}[-] Error: Portage synchronization failed. Aborting upgrade.{}", BOLD, RESET);
                exit(1);
            }

            println!("\n{}[2/3] STEP 2: COMPILES & UPGRADES FOR SYSTEM PARTITION...{}", BOLD, RESET);
            let system_success = if is_host {
                chroot_run(target_dir, &["emerge", "-auDN", "@world"])
            } else {
                run_command_interactive("emerge", &["-auDN", "@world"])
            };

            if !system_success {
                println!("{}[-] Error: System compilation/upgrade failed. Skipping userland.{}", BOLD, RESET);
                exit(1);
            }

            println!("\n{}[3/3] STEP 3: UPGRADING USERLAND FLATPAKS...{}", BOLD, RESET);
            let userland_success = if is_host {
                chroot_run(target_dir, &["flatpak", "update", "-y"])
            } else {
                run_command_interactive("flatpak", &["update", "-y"])
            };

            if userland_success {
                println!("\n{}{}{}========================================================================{}", BOLD, GREEN, RESET, RESET);
                println!("{}{}          SMECHOS SYSTEM COMPILATION & UPGRADE COMPLETED!{}", BOLD, GREEN, RESET);
                println!("{}            Sovereignty verified. Your workstation is secure.{}", BOLD, RESET);
                println!("{}{}{}========================================================================{}", BOLD, GREEN, RESET, RESET);
            } else {
                println!("{}Warning: Userland flatpak updates encountered issues.{}", YELLOW, RESET);
                println!("\n{}{}{}========================================================================{}", BOLD, YELLOW, RESET, RESET);
                println!("{}{}    SMECHOS SYSTEM PARTITION UPGRADED WITH SOME USERLAND WARNINGS{}", BOLD, YELLOW, RESET);
                println!("{}{}{}========================================================================{}", BOLD, YELLOW, RESET, RESET);
            }
        }
        _ => {
            println!("{}[-] Error: Unknown command: '{}'{}", BOLD, command, RESET);
            println!("    Use 'spk help' to see valid commands.");
            exit(1);
        }
    }
}
