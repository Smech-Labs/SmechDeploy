# Building SmechOS images (kernel, VHDX, installer ISO, live ISO)

This document picks up after the Phase 1/Phase 2 build described in `README.md`
has produced a working `images/part2.img` mounted at `/mnt/smechos` (set via
`SMECH_TARGET`). It covers everything needed to go from "compiled root
filesystem" to the four image deliverables in `images/`:

- `smechos.img` — raw GPT disk image (EFI + root)
- `smechos.vhdx` — Hyper-V virtual disk (full pre-installed system, no installer)
- `smechos-installer.iso` — minimal boot-chain test ISO (kernel + initramfs + GRUB only)
- `smechos-live.iso` — full Ubuntu/Fedora-style live ISO (squashfs + dmsquash-live + overlayfs)

All steps below assume `/mnt/smechos` is the mounted root partition and the
kernel source is `essentials/linux-6.12.16/`.

## 1. Kernel configuration

The shipped kernel (`6.12.16`) needs extra config beyond Gentoo defaults for:

- **Hyper-V guest support** (so `smechos.vhdx` boots under Hyper-V):
  `CONFIG_HYPERV=y`, plus modules `CONFIG_HYPERV_STORAGE`, `CONFIG_HYPERV_NET`,
  `CONFIG_HYPERV_KEYBOARD`, `CONFIG_HYPERV_UTILS`, `CONFIG_HYPERV_BALLOON`,
  `CONFIG_HYPERV_TIMER=y`, `CONFIG_HYPERV_IOMMU=y`.
- **Live-boot support** (squashfs root + writable overlay):
  `CONFIG_SQUASHFS=m` with `CONFIG_SQUASHFS_COMPILE_DECOMP_MULTI=y`,
  `CONFIG_SQUASHFS_ZLIB=y`, `CONFIG_SQUASHFS_XZ=y`; and
  `CONFIG_OVERLAY_FS=m` with `CONFIG_OVERLAY_FS_REDIRECT_DIR=y`,
  `CONFIG_OVERLAY_FS_INDEX=y`.

Apply with `scripts/config` (avoids re-running the interactive `menuconfig`):

```sh
cd essentials/linux-6.12.16
./scripts/config --enable CONFIG_HYPERV \
  --module CONFIG_HYPERV_STORAGE --module CONFIG_HYPERV_NET \
  --module CONFIG_HYPERV_KEYBOARD --module CONFIG_HYPERV_UTILS \
  --module CONFIG_HYPERV_BALLOON --enable CONFIG_HYPERV_TIMER \
  --enable CONFIG_HYPERV_IOMMU \
  --module CONFIG_SQUASHFS --enable CONFIG_SQUASHFS_FILE_CACHE \
  --disable CONFIG_SQUASHFS_DECOMP_SINGLE --enable CONFIG_SQUASHFS_COMPILE_DECOMP_MULTI \
  --enable CONFIG_SQUASHFS_ZLIB --enable CONFIG_SQUASHFS_XZ \
  --disable CONFIG_SQUASHFS_LZ4 --disable CONFIG_SQUASHFS_LZO --disable CONFIG_SQUASHFS_ZSTD \
  --module CONFIG_OVERLAY_FS --enable CONFIG_OVERLAY_FS_REDIRECT_DIR \
  --enable CONFIG_OVERLAY_FS_INDEX
sudo -n make olddefconfig
```

**Important:** enabling `CONFIG_OVERLAY_FS` auto-selects `CONFIG_FS_STACK=y`,
which pulls `fs/backing-file.o` into the build. If you only run `make modules`
after a config change like this, `overlay.ko` fails `modpost` with undefined
symbols (`backing_file_mmap`, `backing_file_write_iter`, etc.) because those
symbols live in `vmlinux`, not in any module. **Run a full `make -j8`** (not
just `make modules`) so `vmlinux`/`Module.symvers` are regenerated first:

```sh
sudo -n make -j8
sudo -n make modules_install INSTALL_MOD_PATH=/mnt/smechos/usr
sudo -n make INSTALL_PATH=/mnt/smechos/boot install   # or manual cp of bzImage
sudo -n chroot /mnt/smechos depmod -a 6.12.16
sudo -n cp arch/x86/boot/bzImage /mnt/smechos/boot/vmlinuz-smechos
```

## 2. Regenerating the initramfs with dracut

Two different initramfs images are built from the same kernel/module tree —
one for the **installed system** (root on a real partition, by UUID) and one
for the **live ISO** (root on a squashfs via `dmsquash-live`).

### 2a. Installed-system initramfs (UUID root)

```sh
sudo -n dracut -k /mnt/smechos/lib/modules/6.12.16 \
  --no-hostonly --no-hostonly-cmdline \
  --add "udev-rules base fs-lib shutdown" \
  --add-drivers "ata_piix ata_generic e1000 e1000e ahci \
    hv_vmbus hv_storvsc hv_netvsc hv_utils hid_hyperv hyperv_keyboard \
    hyperv_fb hv_balloon pci_hyperv pci_hyperv_intf" \
  --kernel-cmdline "root=UUID=<ROOT-FS-UUID> ro quiet splash vt_handoff=7" \
  --force /mnt/smechos/boot/initramfs-6.12.16.img 6.12.16
```

Get `<ROOT-FS-UUID>` with `blkid` on the root partition. The `hv_*`/`pci_hyperv*`
drivers make the resulting image bootable as a Hyper-V Gen2 VM; the
`ata_*`/`e1000*`/`ahci` drivers cover BIOS/QEMU/bare-metal.

### 2b. Live-ISO initramfs (dmsquash-live)

Requires the `dracut-live` package's modules
(`90dmsquash-live`, `99img-lib`, `90dmsquash-live-autooverlay`) installed into
`/usr/lib/dracut/modules.d/` on the **build host** (not the target) — on
Debian/Ubuntu:

```sh
apt-get download dracut-live
dpkg-deb -x dracut-live_*.deb /tmp/dracut-live
sudo cp -r /tmp/dracut-live/usr/lib/dracut/modules.d/90dmsquash-live* \
           /tmp/dracut-live/usr/lib/dracut/modules.d/99img-lib \
           /usr/lib/dracut/modules.d/
```

Then build the live initramfs, adding `dmsquash-live` plus the drivers needed
to read the boot media and mount the squashfs/overlay:

```sh
sudo -n dracut -k /mnt/smechos/lib/modules/6.12.16 \
  --no-hostonly --no-hostonly-cmdline \
  --add "dmsquash-live udev-rules base fs-lib shutdown" \
  --add-drivers "ata_piix ata_generic e1000 e1000e ahci sr_mod usb-storage \
    squashfs overlay loop isofs \
    hv_vmbus hv_storvsc hv_netvsc hv_utils hid_hyperv hyperv_keyboard \
    hyperv_fb hv_balloon pci_hyperv pci_hyperv_intf" \
  --force /tmp/live_build/initramfs-live-6.12.16.img 6.12.16
```

No `--kernel-cmdline` here — the live root is specified entirely via the
`root=live:CDLABEL=...` kernel parameter in GRUB (below), which
`90dmsquash-live`'s cmdline hook (`30-parse-dmsquash-live.sh`) parses at boot.

## 3. GRUB configurations

### 3a. Installed system (`/mnt/smechos/boot/grub/grub.cfg`)

UUID-based, two entries (normal splash boot + verbose serial debug):

```
set timeout=5
set default=0

insmod all_video
insmod gzio
insmod part_gpt
insmod fat
insmod ext2

search --no-floppy --fs-uuid --set=root <EFI-PARTITION-UUID>

menuentry 'SmechOS (Plasma 6)' {
    linux   /vmlinuz-smechos root=UUID=<ROOT-FS-UUID> ro quiet splash vt_handoff=7
    initrd  /initramfs-6.12.16.img
}

menuentry 'SmechOS (Plasma 6) - verbose/debug (serial console)' {
    linux   /vmlinuz-smechos root=UUID=<ROOT-FS-UUID> rw console=ttyS0,115200n8 console=tty0
    initrd  /initramfs-6.12.16.img
}
```

### 3b. Live ISO (`LiveOS` layout, `root=live:CDLABEL=...`)

```
set timeout=5
set default=0

insmod all_video
insmod gzio

menuentry 'SmechOS (Plasma 6) - Live' {
    linux   /boot/vmlinuz-smechos root=live:CDLABEL=SMECHOS_LIVE rd.live.image rw quiet splash vt_handoff=7
    initrd  /boot/initramfs-live-6.12.16.img
}

menuentry 'SmechOS (Plasma 6) - Live (verbose/debug, serial console)' {
    linux   /boot/vmlinuz-smechos root=live:CDLABEL=SMECHOS_LIVE rd.live.image rw rd.debug console=ttyS0,115200n8 console=tty0
    initrd  /boot/initramfs-live-6.12.16.img
}
```

`CDLABEL=SMECHOS_LIVE` must match the ISO9660 volume label set by
`grub-mkrescue -- -volid SMECHOS_LIVE` (step 5). `dmsquash-live` looks for
`LiveOS/squashfs.img` on that labeled volume by default.

## 4. Building the squashfs root (`LiveOS/squashfs.img`)

`mksquashfs` is **not** in the NOPASSWD sudoers list, so it must run as the
unprivileged build user against a source tree it can fully read. The root
filesystem contains root-owned, mode-640 files (`/etc/shadow`, `/etc/shadow-`)
that `mksquashfs` silently replaces with empty 0-byte placeholders if it can't
read them — there is no reliable `-p`/pseudo-file override for files that
already exist in the source tree. The fix is to make a fully-readable copy of
the tree first:

```sh
sudo -n rsync -a --chown=smech:smech \
  --exclude=boot --exclude=tmp --exclude=proc --exclude=sys --exclude=dev \
  /mnt/smechos/ /tmp/smechos_copy/
```

Then build the squashfs from that copy, adding empty placeholder directories
for the excluded mount points/pseudo-filesystems:

```sh
mksquashfs /tmp/smechos_copy /tmp/live_build/filesystem.squashfs \
  -comp xz -b 1M \
  -p "tmp d 1777 0 0" -p "boot d 755 0 0" \
  -p "proc d 555 0 0" -p "sys d 555 0 0" -p "dev d 755 0 0" \
  -noappend
```

Verify `/etc/shadow` survived intact (should show real hashes, not be empty):

```sh
unsquashfs -cat /tmp/live_build/filesystem.squashfs etc/shadow | head -3
```

**Never** run `mksquashfs <src> <existing-squashfs.img> -noappend` against a
squashfs you want to keep — `-noappend` discards the existing image's content
entirely, even in "append" mode invocations.

Because the squashfs root has a top-level `/proc` (it's a full-OS image, not a
nested `LiveOS/rootfs.img`), `dmsquash-live` automatically treats it as
`FSIMG` and layers a writable `overlay` on top — no extra `rootfs.img`
wrapping step is needed.

### 4a. Disable `/etc/fstab` entries in the squashfs source

The installed system's `/etc/fstab` lists the real root (`UUID=... / ext4`)
and EFI/`/boot` (`UUID=... /boot vfat`) partitions by UUID. Neither exists on
the live medium — root is already the squashfs+overlay mounted by
`dmsquash-live` before OpenRC runs, and there's no separate `/boot` partition.

If these entries are left in place, OpenRC's `checkfs` runs `fsck.fat` against
the non-existent `/boot` UUID, which fails (`open: No such file or directory`),
prints `* rc: Aborting!`, and the default runlevel aborts entirely
(`fsck: caught SIGTERM, aborting`) — the boot never reaches `sddm`/login.

Fix by commenting out both entries in `/tmp/smechos_copy/etc/fstab` (the
squashfs source copy only — **do not** touch `/mnt/smechos/etc/fstab`, which
is the real installed-system fstab needed for `smechos.img`/`smechos.vhdx`):

```sh
sudo sed -i '/^UUID=/ s/^/#/' /tmp/smechos_copy/etc/fstab
```

With an empty/fully-commented fstab, `checkfs` and `localmount` both report
`fstabinfo: empty fstab` and pass cleanly, and the default runlevel proceeds
to `sddm`.

## 5. Assembling the ISO with grub-mkrescue

`grub-mkrescue` needs `xorriso`, `mformat`/`mcopy` (from `mtools`), and
`unicode.pf2`. If these aren't installed on the build host, extract them from
`.deb` packages and stage them inside the chroot:

```sh
apt-get download xorriso mtools
dpkg-deb -x xorriso_*.deb /tmp/xorriso_local/extract
dpkg-deb -x mtools_*.deb  /tmp/xorriso_local/extract
sudo -n cp /tmp/xorriso_local/extract/usr/bin/{xorriso,mformat,mcopy} /mnt/smechos/tmp/xorriso_bin/
sudo -n cp /tmp/xorriso_local/extract/usr/lib/x86_64-linux-gnu/{libburn.so.4*,libisofs.so.6*,libisoburn.so.1*,libreadline.so.8*,libhistory.so.8*} \
  /mnt/smechos/tmp/xorriso_libs/
```

`unicode.pf2` ships with the compiled GRUB at `/usr/share/grub/unicode.pf2`
inside the target — no extraction needed if GRUB was already built (step 2 of
`README.md`'s Phase 2).

### 5a. Installer ISO (boot-chain test only — no root filesystem)

```sh
mkdir -p /tmp/isosrc/boot/grub
cp /mnt/smechos/boot/vmlinuz-smechos /tmp/isosrc/boot/
cp /mnt/smechos/boot/initramfs-6.12.16.img /tmp/isosrc/boot/
cp /tmp/iso_grub.cfg /tmp/isosrc/boot/grub/grub.cfg   # UUID-based, see 3a

sudo -n chroot /mnt/smechos /bin/bash -c '
  export PATH=/tmp/xorriso_bin:$PATH LD_LIBRARY_PATH=/tmp/xorriso_libs
  grub-mkrescue -o /tmp/smechos-installer.iso /tmp/isosrc
'
```

This produces a small (~55 MB) ISO containing only kernel + initramfs + GRUB —
useful for testing the boot chain in a VM, but **not** a usable installer or
live system since there's no root filesystem to switch into.

### 5b. Live ISO (full system, squashfs + overlay)

```sh
mkdir -p /tmp/isosrc_live/boot/grub /tmp/isosrc_live/LiveOS
cp /mnt/smechos/boot/vmlinuz-smechos /tmp/isosrc_live/boot/
cp /tmp/live_build/initramfs-live-6.12.16.img /tmp/isosrc_live/boot/
cp /tmp/iso_grub_live.cfg /tmp/isosrc_live/boot/grub/grub.cfg   # see 3b
cp /tmp/live_build/filesystem.squashfs /tmp/isosrc_live/LiveOS/squashfs.img

sudo -n chroot /mnt/smechos /bin/bash -c '
  export PATH=/tmp/xorriso_bin:$PATH LD_LIBRARY_PATH=/tmp/xorriso_libs
  grub-mkrescue -o /tmp/smechos-live.iso /tmp/isosrc_live -- -volid SMECHOS_LIVE
'
```

The `-volid SMECHOS_LIVE` is **required** — it sets the ISO9660 label that
`root=live:CDLABEL=SMECHOS_LIVE` in grub.cfg (3b) matches at boot. Verify with
`blkid smechos-live.iso` (should show `LABEL="SMECHOS_LIVE"`).

Copy the result to `images/smechos-live.iso`.

## 6. Producing the Hyper-V VHDX

The raw disk image (`smechos-redo.img` / `smechos.img`) converts directly:

```sh
qemu-img convert -f raw -O vhdx images/smechos.img images/smechos.vhdx
```

This is the **full pre-installed system** for Hyper-V — boot it as a Gen2 VM
with Secure Boot disabled. It requires the Hyper-V-enabled kernel/initramfs
from steps 1–2a.

## 7. Testing in QEMU

Both the installer and live ISOs can be smoke-tested with QEMU + OVMF
(UEFI firmware), without KVM if running inside a VM/container that doesn't
expose `/dev/kvm`:

```sh
cp /usr/share/OVMF/OVMF_VARS_4M.fd /tmp/OVMF_VARS.fd
qemu-system-x86_64 -M q35 -m 4096 -nographic \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=/tmp/OVMF_VARS.fd \
  -cdrom images/smechos-live.iso \
  -boot d -serial mon:stdio
```

Without KVM (TCG-only), boot is roughly 7-8x slower than real time — a normal
boot to login can take several minutes of wall-clock time. Use the
"verbose/debug, serial console" GRUB entry (set `default=1`) to get kernel +
dracut + OpenRC logs on the serial console (`-serial mon:stdio`) for
debugging.

## 8. Building the systemd-based live ISO variant (`smechos-live-systemd.iso`)

SmechOS ships two live ISO variants from the same compiled root
(`/mnt/smechos`): the default **OpenRC** image (`smechos-live-openrc.iso`,
built from the `/tmp/smechos_copy` source tree per sections 4-5 above) and a
**systemd** image (`smechos-live-systemd.iso`), built from a separate source
tree at `/tmp/smechos_copy_systemd`. The systemd tree starts as a copy of the
OpenRC tree with donor `systemd` binaries/units copied in from the Ubuntu
build host (`/lib/systemd/systemd` as `/sbin/init`, plus `/usr/lib/systemd/`,
`/etc/systemd/`, `systemd-logind`, `dbus`, etc.), `default.target` symlinked to
`graphical.target`, and `display-manager.service` symlinked to `sddm.service`.

### 8a. Required fixes for a working systemd boot

Three OS-level fixes are required in `/tmp/smechos_copy_systemd` for the
systemd image to reach a working Plasma session (all confirmed working as of
the `filesystem35.squashfs` / v39 build):

1. **D-Bus policy for `org.freedesktop.systemd1`** — without
   `/usr/share/dbus-1/system.d/org.freedesktop.systemd1.conf`, the default
   `<deny own="*"/>` policy prevents PID 1 from owning
   `org.freedesktop.systemd1` on the system bus. `systemd-logind` then times
   out (25s) trying to call it to start `user@<uid>.service`, so the user's
   systemd instance (needed for `startplasma-wayland` via
   `plasma-dbus-run-session-if-needed`) never starts. Fix: add a policy file
   granting `root` ownership of `org.freedesktop.systemd1` and allowing the
   default context to call `Manager`/`Unit`/`Service`/`Socket`/`Target`
   methods on it (see the file in the tree for the full method list).

2. **`/home/<live-user>` ownership** — SDDM redirects the autologin session's
   stdout/stderr to `~/.local/share/sddm/wayland-session.log`. If
   `~/.local/share/sddm` isn't owned/writable by the session user, SDDM logs
   `(WW) HELPER: Could not open stderr to "..."` and the actual Plasma session
   output is silently discarded, making the crash undebuggable. Fix:
   `chown -R <uid>:<gid> /home/<live-user>` for the live autologin user (in
   this build, `Live`, uid 1003, gid 100) inside the systemd tree.

3. **`libLLVM.so.18.1`** — Mesa's DRI loader (`dri_gbm.so` → `*_dri.so`)
   `dlopen`s the exact versioned soname `libLLVM.so.18.1` for the GBM
   software/3D paths. If this file is missing (dangling symlink with no real
   target), MESA-LOADER fails with `cannot open shared object file`, which
   cascades into `kwin_core: Failed to create gbm device`. Fix: copy the real
   library to that exact filename, e.g.
   `cp /usr/lib/llvm-18/lib/libLLVM.so.1 <tree>/usr/lib/x86_64-linux-gnu/libLLVM.so.18.1`.

### 8b. Rebuilding and testing

Build a squashfs from the systemd tree the same way as section 4 (readable
copy + `mksquashfs ... -noappend`), then use the NOPASSWD helper
`/usr/local/sbin/smechos-rebuild.sh` to splice it into the ISO and run
`grub-mkrescue`:

```sh
sudo -n /usr/local/sbin/smechos-rebuild.sh /tmp/live_build/filesystemN.squashfs vNN
cp images/smechos-live.iso images/smechos-live-systemd.iso
```

`smechos-rebuild.sh` requires the squashfs path to match
`^/tmp/live_build/filesystem[0-9]+\.squashfs$` and the version to match
`^v[0-9]+$` (no letter suffixes). It copies the squashfs to
`/mnt/smechos/tmp/isosrc_live/LiveOS/squashfs.img`, runs `grub-mkrescue` inside
the chroot, and copies the result to `images/smechos-live.iso` — the
`-systemd` rename is a manual step.

`/mnt/smechos` (a 19GB loop-mounted ext4 image) accumulates a
`smechos-live-vN.iso` per rebuild and can fill up, causing `grub-mkrescue` to
fail with `libisofs: MISHAP: Image write cancelled` / `No space left on
device`. Old ISOs are root-owned in a sticky-bit `/tmp`, so the build user
can't `rm` them directly; use `sudo -n chroot /mnt/smechos /bin/rm -fv
/tmp/smechos-live-v{...}.iso` to clear space.

### 8c. Debugging boot/session issues

For diagnosing why a session doesn't reach a usable desktop, add
`/etc/local.d/99-debug.start` (enabled via `/etc/systemd/system/local.service`,
`WantedBy=multi-user.target`) that sleeps ~35s then dumps `ps auxww`,
`journalctl -b -o short-precise`, `dmesg | grep -iE 'drm|gpu|virtio|vga'`, and
any `*sddm*log*`/`*wayland-session*`/`plasma*.log` files to a second serial
port (`/dev/ttyS1`), to avoid contending with `serial-getty@ttyS0.service` on
`/dev/ttyS0`. Launch QEMU with two `-serial file:...` arguments and read the
second log file after boot.

**Known QEMU/test-environment limitation**: under WSL2, `-device virtio-vga`
reports `[drm] features: -virgl -context_init`, so Mesa's `virtio_gpu` gallium
driver can't create a GBM device (`virtio_gpu: driver missing` →
`kwin_core: Failed to create gbm device for "/dev/dri/card0"` →
`kwin_wayland_drm: No suitable DRM devices have been found`), and
`kwin_wayland_wrapper` crash-loops so the session exits after ~4 seconds
(cursor-only). Switching to `-device virtio-vga-gl -display gtk,gl=on` makes
the kernel report `+virgl +edid` but still `-context_init`, and the *host*
EGL/GL stack itself fails (`MESA: error: ZINK: failed to choose pdev`,
`screendump` → `Error: no surface`) — this WSL2 host has no working
GPU/EGL passthrough for QEMU's GL display. This is a test-environment
limitation, not a SmechOS image bug — the three fixes in 8a are sufficient for
systemd, D-Bus, and the user session/Plasma launch to work correctly; full
graphical verification requires real hardware or a host with working virgl.

## Summary: full pipeline at a glance

```
essentials/linux-6.12.16/  --(scripts/config + make -j8 + modules_install)-->  /mnt/smechos/{boot,lib/modules}
                                          |
                                          +--> dracut (UUID root)      --> initramfs-6.12.16.img      --> smechos.img / smechos.vhdx
                                          |
                                          +--> dracut (dmsquash-live)  --> initramfs-live-6.12.16.img -+
                                                                                                          |
/mnt/smechos/ --(rsync --chown readable copy)--> /tmp/smechos_copy --(mksquashfs)--> filesystem.squashfs +--> grub-mkrescue -volid SMECHOS_LIVE --> smechos-live.iso
```
