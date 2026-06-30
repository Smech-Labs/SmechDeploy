#!/bin/bash
# SmechDeploy Phase -- Build SmechVisor install ISO (offline / local packages)
#
# Unlike the SmechOS netinst ISO, this ISO bundles all packages on-disc so
# the installer requires NO internet connection. The TUI installer
# (smechvisor-installer, built from repo-packs-installer-visor/) reads
# packages from /packages/ on the mounted ISO.
#
# Package layout inside the ISO:
#   /packages/smechvisor-base.tar.xz   -- musl base, kernel, OpenRC, GRUB
#   /packages/smechvisor-daemon.tar.xz -- smechvisord binary, web assets,
#                                         cloud-hypervisor, OpenRC init scripts
#   /installer/smechvisor-installer    -- the TUI installer binary
#
# The GRUB menu on the ISO boots into a minimal live environment that runs
# the installer automatically. After install the user reboots into the
# installed SmechVisor on their disk.
#
# Requires: xorriso, grub-mkrescue or grub-mkstandalone, cargo, tar, xz
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SMECH_TARGET="${SMECH_TARGET:-/mnt/smechvisor_build_root}"

OUTPUT_DIR="$DEPLOY_ROOT/images"
ISO_NAME="smechvisor-install-$(date +%Y%m%d).iso"
ISO_PATH="$OUTPUT_DIR/$ISO_NAME"
WORK_DIR="/tmp/smechos_build/smechvisor_install_iso"
PKGS_DIR="$WORK_DIR/packages"
INST_DIR="$WORK_DIR/installer"
BOOT_DIR="$WORK_DIR/boot/grub"

INSTALLER_SRC="$DEPLOY_ROOT/repo-packs-installer-visor"
INSTALLER_BIN="$INSTALLER_SRC/target/release/smechvisor-installer"

CH_VERSION="${CH_VERSION:-42.0}"
CH_URL="https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CH_VERSION}/cloud-hypervisor-static"

echo "[smechvisor-install-iso] Building SmechVisor install ISO..."
echo "[smechvisor-install-iso] Source target: $SMECH_TARGET"
echo "[smechvisor-install-iso] Output: $ISO_PATH"

mkdir -p "$OUTPUT_DIR" "$PKGS_DIR" "$INST_DIR" "$BOOT_DIR"
rm -f "$ISO_PATH"

# ── Build the TUI installer ────────────────────────────────────────────────────
echo "[smechvisor-install-iso] Building smechvisor-installer (Rust)..."
cd "$INSTALLER_SRC"
cargo build --release
cd "$DEPLOY_ROOT"
cp "$INSTALLER_BIN" "$INST_DIR/smechvisor-installer"

# ── Pack smechvisor-base.tar.xz ───────────────────────────────────────────────
# Contains: kernel, initramfs, musl userland, OpenRC, GRUB binaries, firmware
# These come from SMECH_TARGET (built by the smechvisor SmechDeploy profile).
echo "[smechvisor-install-iso] Packing smechvisor-base..."
if [ -d "$SMECH_TARGET" ]; then
    sudo tar -cJf "$PKGS_DIR/smechvisor-base.tar.xz" \
        --exclude="$SMECH_TARGET/usr/sbin/smechvisord" \
        --exclude="$SMECH_TARGET/usr/sbin/cloud-hypervisor" \
        --exclude="$SMECH_TARGET/usr/sbin/vhost-user-gpu" \
        --exclude="$SMECH_TARGET/usr/share/smechvisord" \
        --exclude="$SMECH_TARGET/etc/init.d/smechvisord" \
        --exclude="$SMECH_TARGET/etc/init.d/vhost-user-gpu" \
        --exclude="$SMECH_TARGET/etc/runlevels/default/smechvisord" \
        --exclude="$SMECH_TARGET/etc/runlevels/default/vhost-user-gpu" \
        -C "$SMECH_TARGET" .
else
    echo "[smechvisor-install-iso] Warning: SMECH_TARGET $SMECH_TARGET not found."
    echo "  Run the smechvisor SmechDeploy profile first, or set SMECH_TARGET."
    echo "  Creating empty placeholder for ISO structure testing..."
    touch "$PKGS_DIR/smechvisor-base.tar.xz"
fi

# ── Pack smechvisor-daemon.tar.xz ─────────────────────────────────────────────
# Contains: smechvisord binary, web assets, cloud-hypervisor, OpenRC scripts
echo "[smechvisor-install-iso] Packing smechvisor-daemon..."
DAEMON_STAGE="/tmp/smechos_build/smechvisor_daemon_stage"
rm -rf "$DAEMON_STAGE"
mkdir -p \
    "$DAEMON_STAGE/usr/sbin" \
    "$DAEMON_STAGE/usr/share/smechvisord/web" \
    "$DAEMON_STAGE/etc/init.d" \
    "$DAEMON_STAGE/etc/runlevels/default" \
    "$DAEMON_STAGE/var/lib/smechvisord/vms" \
    "$DAEMON_STAGE/var/log/smechvisord"

# smechvisord binary -- prefer pre-installed in SMECH_TARGET, else build fresh
if [ -f "$SMECH_TARGET/usr/sbin/smechvisord" ]; then
    cp "$SMECH_TARGET/usr/sbin/smechvisord" "$DAEMON_STAGE/usr/sbin/smechvisord"
elif [ -d "/tmp/smechos_build/smechvisord" ]; then
    cp "/tmp/smechos_build/smechvisord/daemon/target/release/smechvisord" \
       "$DAEMON_STAGE/usr/sbin/smechvisord"
else
    echo "[smechvisor-install-iso] Warning: smechvisord binary not found."
    echo "  Run 13_install_smechvisor.sh first."
fi

# web assets
if [ -d "$SMECH_TARGET/usr/share/smechvisord/web" ]; then
    cp -r "$SMECH_TARGET/usr/share/smechvisord/web/." \
          "$DAEMON_STAGE/usr/share/smechvisord/web/"
elif [ -d "/tmp/smechos_build/smechvisord/web" ]; then
    cp -r "/tmp/smechos_build/smechvisord/web/." \
          "$DAEMON_STAGE/usr/share/smechvisord/web/"
fi

# cloud-hypervisor
if [ -f "$SMECH_TARGET/usr/sbin/cloud-hypervisor" ]; then
    cp "$SMECH_TARGET/usr/sbin/cloud-hypervisor" "$DAEMON_STAGE/usr/sbin/cloud-hypervisor"
else
    echo "[smechvisor-install-iso] Downloading cloud-hypervisor v${CH_VERSION}..."
    wget -q -O "$DAEMON_STAGE/usr/sbin/cloud-hypervisor" "$CH_URL"
    chmod 755 "$DAEMON_STAGE/usr/sbin/cloud-hypervisor"
fi

# OpenRC init scripts
if [ -d "/tmp/smechos_build/smechvisord/openrc" ]; then
    install -m 755 "/tmp/smechos_build/smechvisord/openrc/smechvisord" \
        "$DAEMON_STAGE/etc/init.d/smechvisord"
    install -m 755 "/tmp/smechos_build/smechvisord/openrc/vhost-user-gpu" \
        "$DAEMON_STAGE/etc/init.d/vhost-user-gpu"
elif [ -f "$SMECH_TARGET/etc/init.d/smechvisord" ]; then
    cp "$SMECH_TARGET/etc/init.d/smechvisord"    "$DAEMON_STAGE/etc/init.d/smechvisord"
    cp "$SMECH_TARGET/etc/init.d/vhost-user-gpu" "$DAEMON_STAGE/etc/init.d/vhost-user-gpu"
    chmod 755 "$DAEMON_STAGE/etc/init.d/smechvisord" \
              "$DAEMON_STAGE/etc/init.d/vhost-user-gpu"
fi

ln -sf "/etc/init.d/vhost-user-gpu" "$DAEMON_STAGE/etc/runlevels/default/vhost-user-gpu" 2>/dev/null || true
ln -sf "/etc/init.d/smechvisord"    "$DAEMON_STAGE/etc/runlevels/default/smechvisord"    2>/dev/null || true

tar -cJf "$PKGS_DIR/smechvisor-daemon.tar.xz" -C "$DAEMON_STAGE" .
rm -rf "$DAEMON_STAGE"

# ── Copy kernel and initramfs for live installer environment ───────────────────
echo "[smechvisor-install-iso] Copying kernel and initramfs..."
mkdir -p "$WORK_DIR/boot"
KERNEL=$(ls "$SMECH_TARGET/boot/vmlinuz-"* 2>/dev/null | sort -V | tail -1 || true)
INITRD=$(ls "$SMECH_TARGET/boot/initramfs-"* 2>/dev/null | sort -V | tail -1 || true)

if [ -z "$KERNEL" ]; then
    echo "[smechvisor-install-iso] Warning: no kernel in $SMECH_TARGET/boot/ -- ISO will not be bootable."
    echo "  Run compile_kernel.sh via the smechvisor profile first."
else
    cp "$KERNEL" "$WORK_DIR/boot/vmlinuz"
    [ -n "$INITRD" ] && cp "$INITRD" "$WORK_DIR/boot/initramfs.img"
fi

# ── GRUB config -- boots the live installer environment ───────────────────────
cat > "$BOOT_DIR/grub.cfg" <<'GRUBCFG'
set timeout=5
set default=0

menuentry "Install SmechVisor" {
    linux   /boot/vmlinuz root=live:LABEL=SMECHVISOR_INST ro quiet loglevel=3 \
            intel_iommu=on amd_iommu=on iommu=pt \
            init=/installer/smechvisor-installer
    initrd  /boot/initramfs.img
}

menuentry "Install SmechVisor (debug console)" {
    linux   /boot/vmlinuz root=live:LABEL=SMECHVISOR_INST ro \
            console=ttyS0,115200 \
            intel_iommu=on amd_iommu=on iommu=pt \
            init=/installer/smechvisor-installer
    initrd  /boot/initramfs.img
}
GRUBCFG

# ── Build ISO ─────────────────────────────────────────────────────────────────
echo "[smechvisor-install-iso] Building ISO with grub-mkrescue..."
grub-mkrescue \
    --output="$ISO_PATH" \
    "$WORK_DIR" \
    -- -volid "SMECHVISOR_INST" 2>/dev/null \
|| {
    echo "[smechvisor-install-iso] grub-mkrescue not found -- falling back to xorriso..."

    EFI_DIR="$WORK_DIR/EFI/BOOT"
    mkdir -p "$EFI_DIR"
    grub-mkstandalone \
        -O x86_64-efi \
        -o "$EFI_DIR/BOOTX64.EFI" \
        "boot/grub/grub.cfg=$BOOT_DIR/grub.cfg"

    xorriso -as mkisofs \
        -iso-level 3 \
        -full-iso9660-filenames \
        -volid "SMECHVISOR_INST" \
        -eltorito-boot boot/grub/core.img \
        -eltorito-catalog boot/grub/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        --efi-boot EFI/BOOT/BOOTX64.EFI \
        -efi-boot-part \
        --efi-boot-image \
        -o "$ISO_PATH" \
        "$WORK_DIR"
}

echo ""
echo "[smechvisor-install-iso] ISO COMPLETE: $ISO_PATH"
echo "[smechvisor-install-iso] Size: $(du -sh "$ISO_PATH" | cut -f1)"
echo ""
echo "  Package checksums:"
sha256sum "$PKGS_DIR/"*.tar.xz 2>/dev/null | sed 's|^|    |'
echo ""
echo "  Test in QEMU (attach a target disk too):"
echo "  qemu-system-x86_64 -enable-kvm -m 2G \\"
echo "    -cdrom $ISO_PATH \\"
echo "    -drive file=/tmp/smechvisor-test.img,format=raw,if=virtio \\"
echo "    -serial stdio"
echo ""
echo "  Write to USB:"
echo "  sudo dd if=$ISO_PATH of=/dev/sdX bs=4M status=progress && sync"
