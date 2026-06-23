# SmechDeploy

Build/deployment toolkit for **SmechOS** — a sovereign Linux distribution with a
from-source core system (Bash, OpenRC, GRUB, Mesa, KDE Plasma 6, custom kernel) and
a KDE Plasma 6 desktop, assembled onto raw GPT disk images (EFI System Partition +
ext4 root). SmechOS itself is not Gentoo-based, but its package manager `spk` uses
`emerge`/Portage under the hood for `spk system-install`.

This repo contains the scripts that compile the system from source and write the
results into a disk image. It does **not** contain the OS itself — running these
scripts produces `smechos-redo.img`, a bootable raw disk image.

## Prerequisites

### Host system

A Debian/Ubuntu-like (tested on Ubuntu 24.04 "noble") x86_64 Linux host with:

```sh
sudo apt-get install -y \
  build-essential cmake ninja-build meson pkg-config bison flex \
  qemu-utils e2fsprogs dosfstools rsync python3 wget \
  libwayland-dev wayland-protocols libwayland-egl-backend-dev \
  llvm-18 clang-18 \
  libx11-dev libxcb1-dev libdrm-dev libgbm-dev \
  libelf-dev libssl-dev zlib1g-dev bc cpio
```

Notes on the less-obvious entries:
- `libwayland-egl-backend-dev` provides `wayland-egl-backend.pc`, required by
  Mesa's `-Dplatforms=wayland` config — not installed by default even when
  `libwayland-dev` is.
- `llvm-18`/`clang-18` provide `llvm-config-18`, which Mesa's LLVM/RadeonSI/OpenCL
  paths need (`LLVM_CONFIG=/usr/bin/llvm-config-18` in `compile_mesa_stack.sh`).
- `libelf-dev`, `bc`, `cpio`, `flex` are needed by `compile_kernel.sh` (Linux 6.12.16).

Also required:
- A Rust toolchain (`rustc`, `cargo`, `bindgen`) on `$PATH` — used by Mesa's
  `-Dgallium-rusticl=true` and by `repo-packs/` (`spk`). Install via
  [rustup](https://rustup.rs/); `bindgen` via `cargo install bindgen-cli`.
- A reference Gentoo/KDE Plasma 6 host system mounted at `/mnt/kaymium_sovereign`
  (used by the Phase 1 restore scripts as the source of `/usr/bin`, `/usr/lib64`,
  `/etc`, etc.). **This is currently a hard dependency of Phase 1** — without it,
  Phase 1 has nothing to copy from. See "Known limitations" below.

### sudo configuration

Phase 1 (`debugfs -w`) and Phase 2 (`make`/`cmake`/`ninja install` with `DESTDIR`,
mounting/unmounting the image, etc.) need root for specific operations. The scripts
call plain `sudo` — no password is embedded anywhere. For unattended multi-hour
builds, add a scoped NOPASSWD drop-in:

```sh
sudo visudo -f /etc/sudoers.d/smechos-build
```

```
<youruser> ALL=(root) NOPASSWD: /usr/bin/mount, /usr/bin/umount, /usr/bin/mkdir, /usr/bin/cp, /usr/bin/ln, /usr/bin/make, /usr/bin/cmake, /usr/bin/ninja, /usr/sbin/debugfs, /usr/bin/strip, /usr/bin/qemu-nbd, /usr/bin/rsync, /usr/bin/dracut, /usr/sbin/chroot, /usr/bin/tee
Defaults:<youruser> setenv
```

The `setenv` line is required because several build steps run things like
`sudo DESTDIR=/path ninja install` — sudo blocks custom environment variables
without it.

**Important:** even with `setenv`, sudo's `secure_path` default still resets `PATH`
to a fixed safe list for the invoked command, and resets `HOME` to `/root`. If a
build step needs tools outside that safe list (e.g. a Rust toolchain installed via
rustup under `~/.cargo`), pass `PATH` and `HOME` through explicitly:

```sh
sudo DESTDIR="$SMECH_TARGET" PATH="$PATH" HOME="$HOME" ninja -C build_dir install
```

Without `HOME`, `rustc`/`cargo` (Mesa's `rusticl` frontend, etc.) fail with
`rustup could not choose a version of rustc to run` because rustup looks for its
toolchain config under `/root/.rustup` instead of the real user's.

## Repo layout

| Path | Contents |
| --- | --- |
| `images/` | Raw disk image pieces (`part1.img` = EFI, `part2.img` = root, `smechos.img` = master). Multi-GB, don't copy wholesale. |
| `bin/` | All build scripts. Numbered scripts (`01_...` – `08_...`) are the canonical ones run by the build; unnumbered duplicates are earlier drafts. |
| `essentials/` | Vendored upstream source trees (KDE Frameworks 6, Plasma 6.6.5, Qt6 modules, Mesa, GRUB 2.12, Linux 6.12.16, etc.) |
| `deps/` | Smaller third-party deps: `openrc_install` skeleton, Portage tree snapshot |
| `repo-packs/` | Rust source for `spk`, SmechOS's package manager CLI |
| `config/` | OpenRC service files and SDDM/autologin config deployed onto the target |

## The `spk` package manager

`spk` ("SmechOS Sovereign Package Keeper") is the in-OS package manager, built with:

```sh
cd repo-packs
cargo build --release   # binary at target/release/spk
```

Once inside SmechOS: `spk system-install <pkg>` (emerge), `spk userland-install <pkg>`
(flatpak), `spk entire-system-upgrade`.

## Build process

The build has two phases. Because the final image's root partition is fixed at
**5 GB** (plus a 1 GB EFI partition = 6 GB total), Phase 2 compiles into a **scratch
root** on the host disk (which has plenty of space), and only a stripped runtime
subset is later packaged into the 5 GB image.

### 1. Create the target image

`images/part1.img` (1 GB, EFI/vfat) and `images/part2.img` (root, ext4) — or a
combined GPT image like `smechos-redo.img` with a 1 GB EFI partition + 5 GB Linux
root partition — must exist before running anything.

### 2. Phase 1 — base system restoration

Operates directly on `images/part2.img` via `debugfs -w` (no mount needed). Pulls
files from the reference host at `/mnt/kaymium_sovereign`:

```sh
python3 bin/restore_utils.py
python3 bin/restore_lib64.py
python3 bin/restore_etc.py
python3 bin/deploy_openrc.py
python3 bin/edit_inittab.py
python3 bin/write_unreadable_etc.py
```

### 3. Seed the scratch build root

Mount `part2.img` read-only and copy the Phase 1 result into a scratch directory
on the host disk (e.g. `/mnt/smechos_build_root`):

```sh
sudo mkdir -p /mnt/smechos_build_root /mnt/part2_ro
sudo qemu-nbd -f raw --connect=/dev/nbd2 --read-only images/part2.img
sudo mount -o ro /dev/nbd2 /mnt/part2_ro
sudo rsync -aHAX /mnt/part2_ro/ /mnt/smechos_build_root/
sudo umount /mnt/part2_ro
sudo qemu-nbd --disconnect /dev/nbd2
```

### 4. Phase 2 — compilation

Each script auto-detects its own paths and exports `SMECH_TARGET` (set to
`/mnt/smechos_build_root` for the scratch-root build). Run in order:

```sh
cd bin
bash 01_compile_core_system.sh   # GNU Bash 5.2, OpenRC 0.54, GRUB 2.12 (BIOS)
bash 02_compile_grub_efi.sh      # GRUB 2.12 (UEFI x86_64-efi)
bash 03_compile_qt_deps.sh       # QtPositioning, QtLocation
bash compile_mesa_stack.sh       # Mesa graphics stack
python3 04_compile_kde_stack.py  # KDE Frameworks 6 + Plasma 6.6.5 + Calamares
bash 05_configure_plasma.sh      # Plasma session/SDDM configuration
python3 06_copy_kwin_deps.py     # KWin runtime deps (libinput, epoxy, libxcvt, ...)
python3 07_copy_qt6uitools.py    # Qt6UiTools headers/cmake configs
bash compile_kernel.sh           # Linux 6.12.16 kernel + modules
python3 08_patch_metadata.py     # KCoreAddons metadata patch
```

Notes:
- `09_rotate_auth.py` is **not** part of the OS build — it toggles Gemini CLI auth
  settings (`~/.gemini/settings.json`) and just happens to live in `bin/`.
- Ignore `build_order.txt` / `build-order/build-order.txt` — they reference the old
  `/mnt/smechos`-mounted-image workflow, not the scratch-root workflow above.

### 5. Package into the target image

Rsync only the runtime-needed files from the scratch root into the mounted 5 GB
root partition, stripping dev headers (`/usr/include`), static libs (`*.a`),
CMake/pkgconfig dev configs, and debug symbols (`strip`). *(packaging script TBD)*

### 6. Make it boot anywhere (dracut + GRUB)

Install `dracut` into the packaged image and generate a UUID-based initramfs so the
image isn't tied to a specific disk/device path, then point GRUB's `root=` at the
filesystem UUID.

### 7. Produce an installer/live ISO and VHDX

Three deliverables are built from the kernel + initramfs + root filesystem
produced above: a Hyper-V `.vhdx` (via `qemu-img convert`), a minimal
boot-chain-test `smechos-installer.iso`, and a full Ubuntu/Fedora-style
`smechos-live.iso` (squashfs + dmsquash-live + overlayfs, bootable from a
single CD/USB). See **[BUILDING_IMAGES.md](BUILDING_IMAGES.md)** for the full
step-by-step pipeline, including kernel config flags, dracut invocations,
GRUB configs, the `mksquashfs`/`/etc/shadow` gotcha, `grub-mkrescue` ISO
assembly, and QEMU+OVMF boot testing.

## Known limitations

- **Phase 1 requires `/mnt/kaymium_sovereign`** — a pre-existing Gentoo/KDE
  reference system. There is currently no "build from nothing" path; Phase 1 is a
  restore/copy from a known-good reference machine, not a from-source bootstrap.
- The 6 GB final image size (1 GB EFI + 5 GB root) is a hard constraint — the
  packaging step (5) must strip aggressively to fit.
- Several scripts have unnumbered duplicates in `bin/` (e.g. `compile_core_system.sh`
  vs `01_compile_core_system.sh`) — these are earlier drafts and are not part of the
  build sequence.
