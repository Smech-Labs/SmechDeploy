#!/bin/bash
# SmechDeploy -- Build SmechVisor Deploy Shim ISO
#
# The shim is a minimal network-boot ISO that makes a bare machine ready to
# receive a SmechVisor install over the network from another SmechVisor node
# running:  spk-visor deploy-system-img-copy <code>
#
# On boot the shim:
#   1. Gets DHCP on all Ethernet and Wi-Fi interfaces
#   2. Runs `spk-visor receive-deploy` which:
#      - Generates a random short code (e.g. e13gts2)
#      - Displays the code full-screen so the operator can read it
#      - Broadcasts the code via UDP every 2s
#      - Listens for the package stream on TCP 9192
#      - Extracts packages into /mnt/target and reboots
#
# This ISO is tiny (~50MB) -- it contains only the shim binary, kernel,
# initramfs, and GRUB. No SmechVisor packages are bundled.
#
# Requires: cargo, xorriso, GRUB tools (from SMECH_TARGET)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SMECH_TARGET="${SMECH_TARGET:-/mnt/smechos_build_root}"

OUTPUT_DIR="$DEPLOY_ROOT/images"
ISO_NAME="smechvisor-deploy-shim-$(date +%Y%m%d).iso"
ISO_PATH="$OUTPUT_DIR/$ISO_NAME"
WORK_DIR="/tmp/smechos_build/smechvisor_shim_iso"
BOOT_DIR="$WORK_DIR/boot/grub"

SHIM_SRC="$DEPLOY_ROOT/repo-packs-smechvisor-shim"
SHIM_BIN="$SHIM_SRC/target/release/smechvisor-shim"

GRUB_MKRESCUE=""
for c in grub-mkrescue "$SMECH_TARGET/usr/bin/grub-mkrescue"; do
    command -v "$c" &>/dev/null && GRUB_MKRESCUE="$c" && break
done
GRUB_MKIMAGE=""
for c in grub-mkimage "$SMECH_TARGET/usr/bin/grub-mkimage"; do
    command -v "$c" &>/dev/null && GRUB_MKIMAGE="$c" && break
done
GRUB_LIB_DIR="$SMECH_TARGET/usr/lib/grub"

echo "[smechvisor-shim] Building SmechVisor Deploy Shim ISO..."
echo "[smechvisor-shim] Output: $ISO_PATH"

mkdir -p "$OUTPUT_DIR" "$BOOT_DIR" "$WORK_DIR/shim"
rm -f "$ISO_PATH"

# ── Build smechvisor-shim ──────────────────────────────────────────────────────
echo "[smechvisor-shim] Building smechvisor-shim TUI binary (Rust)..."
cd "$SHIM_SRC"
cargo build --release
cd "$DEPLOY_ROOT"
cp "$SHIM_BIN" "$WORK_DIR/shim/smechvisor-shim"
chmod 755 "$WORK_DIR/shim/smechvisor-shim"

# ── Copy kernel and initramfs ──────────────────────────────────────────────────
echo "[smechvisor-shim] Copying kernel and initramfs..."
mkdir -p "$WORK_DIR/boot"
KERNEL=$(ls "$SMECH_TARGET/boot/vmlinuz-"* 2>/dev/null | sort -V | tail -1 || true)
INITRD=$(ls "$SMECH_TARGET/boot/initramfs-"* 2>/dev/null | sort -V | tail -1 || true)

if [ -z "$KERNEL" ]; then
    echo "[smechvisor-shim] Warning: no kernel found -- ISO will not be bootable."
else
    cp "$KERNEL" "$WORK_DIR/boot/vmlinuz"
    [ -n "$INITRD" ] && cp "$INITRD" "$WORK_DIR/boot/initramfs.img"
fi

# ── GRUB config ───────────────────────────────────────────────────────────────
cat > "$BOOT_DIR/grub.cfg" <<'GRUBCFG'
set timeout=3
set default=0

menuentry "SmechVisor Deploy Shim" {
    linux   /boot/vmlinuz quiet loglevel=3 \
            init=/shim/smechvisor-shim-init
    initrd  /boot/initramfs.img
}
GRUBCFG

# The shim init wrapper: mount essentials then launch the TUI wizard
cat > "$WORK_DIR/shim/smechvisor-shim-init" <<'INITSH'
#!/bin/sh
# Minimal init for the deploy shim
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /mnt/target /var/run /tmp /etc
echo "nameserver 1.1.1.1" > /etc/resolv.conf
exec /shim/smechvisor-shim
INITSH
chmod 755 "$WORK_DIR/shim/smechvisor-shim-init"

# ── Build ISO ─────────────────────────────────────────────────────────────────
echo "[smechvisor-shim] Building ISO (grub-mkrescue: ${GRUB_MKRESCUE:-not found})..."

if [ -n "$GRUB_MKRESCUE" ]; then
    "$GRUB_MKRESCUE" \
        --directory="$GRUB_LIB_DIR/x86_64-efi" \
        --directory="$GRUB_LIB_DIR/i386-pc" \
        --output="$ISO_PATH" \
        "$WORK_DIR" \
        -- -volid "SMECHVISOR_SHIM"
else
    EFI_DIR="$WORK_DIR/EFI/BOOT"
    mkdir -p "$EFI_DIR"

    "$GRUB_MKIMAGE" \
        -O x86_64-efi \
        -p "/boot/grub" \
        -d "$GRUB_LIB_DIR/x86_64-efi" \
        -o "$EFI_DIR/BOOTX64.EFI" \
        fat iso9660 part_gpt part_msdos normal boot linux configfile \
        loopback chain efifwsetup efi_gop efi_uga ls search \
        search_label search_fs_uuid search_fs_file gfxterm \
        test all_video loadenv ext2

    "$GRUB_MKIMAGE" \
        -O i386-pc \
        -p "/boot/grub" \
        -d "$GRUB_LIB_DIR/i386-pc" \
        -o "$WORK_DIR/boot/grub/core.img" \
        biosdisk iso9660 normal linux echo configfile search \
        search_label search_fs_uuid part_gpt part_msdos ls test

    cat "$GRUB_LIB_DIR/i386-pc/cdboot.img" \
        "$WORK_DIR/boot/grub/core.img" \
        > "$WORK_DIR/boot/grub/bios.img"

    xorriso -as mkisofs \
        -iso-level 3 \
        -full-iso9660-filenames \
        -volid "SMECHVISOR_SHIM" \
        -eltorito-boot boot/grub/bios.img \
        -eltorito-catalog boot/grub/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        --efi-boot EFI/BOOT/BOOTX64.EFI \
        -efi-boot-part \
        --efi-boot-image \
        -o "$ISO_PATH" \
        "$WORK_DIR"
fi

echo ""
echo "[smechvisor-shim] SHIM ISO COMPLETE: $ISO_PATH"
echo "[smechvisor-shim] Size: $(du -sh "$ISO_PATH" | cut -f1)"
echo ""
echo "  SHA-256: $(sha256sum "$ISO_PATH" | cut -d' ' -f1)"
echo "  MD5:     $(md5sum "$ISO_PATH" | cut -d' ' -f1)"
echo ""
echo "  Usage:"
echo "  1. Write to USB: sudo dd if=$ISO_PATH of=/dev/sdX bs=4M status=progress && sync"
echo "  2. Boot the target machine from the USB"
echo "  3. Note the code displayed on screen (e.g. e13gts2)"
echo "  4. On this machine: spk-visor deploy-system-img-copy e13gts2"
