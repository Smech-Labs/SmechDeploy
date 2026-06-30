#!/bin/bash
# SmechDeploy Phase -- Build SmechVisor bootable ISO
#
# Produces a bootable SmechVisor ISO from the target filesystem assembled
# by the smechvisor profile build sequence. This is NOT an installer ISO --
# it boots directly into the SmechVisor OS (OpenRC + smechvisord), not a
# wizard. The control plane is reachable at http://<host-ip>:8080 after boot.
#
# Requires: xorriso, grub-pc-bin, grub-efi-amd64-bin (on build host)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SMECH_TARGET="${SMECH_TARGET:-/mnt/smechos_build_root}"

OUTPUT_DIR="$DEPLOY_ROOT/images"
ISO_NAME="smechvisor-$(date +%Y%m%d).iso"
ISO_PATH="$OUTPUT_DIR/$ISO_NAME"
WORK_DIR="/tmp/smechos_build/smechvisor_iso"
EFI_DIR="$WORK_DIR/EFI/BOOT"
BOOT_DIR="$WORK_DIR/boot/grub"

echo "[smechvisor-iso] Building SmechVisor bootable ISO..."
echo "[smechvisor-iso] Source: $SMECH_TARGET"
echo "[smechvisor-iso] Output: $ISO_PATH"

mkdir -p "$OUTPUT_DIR" "$EFI_DIR" "$BOOT_DIR"
rm -f "$ISO_PATH"

# ── Copy kernel and initramfs from target ──────────────────────────────────────
echo "[smechvisor-iso] Copying kernel and initramfs..."
KERNEL=$(ls "$SMECH_TARGET/boot/vmlinuz-"* 2>/dev/null | sort -V | tail -1)
INITRD=$(ls "$SMECH_TARGET/boot/initramfs-"* 2>/dev/null | sort -V | tail -1)

if [ -z "$KERNEL" ]; then
    echo "Error: no kernel found in $SMECH_TARGET/boot/. Run compile_kernel.sh first."
    exit 1
fi

cp "$KERNEL" "$WORK_DIR/boot/vmlinuz"
if [ -n "$INITRD" ]; then
    cp "$INITRD" "$WORK_DIR/boot/initramfs.img"
else
    echo "[smechvisor-iso] Warning: no initramfs found -- booting without one."
fi

# ── GRUB config ───────────────────────────────────────────────────────────────
cat > "$BOOT_DIR/grub.cfg" <<'GRUBCFG'
set timeout=3
set default=0

menuentry "SmechVisor" {
    linux   /boot/vmlinuz root=/dev/sda2 ro quiet loglevel=3 \
            intel_iommu=on amd_iommu=on iommu=pt \
            kvm.enable_apicv=1
    initrd  /boot/initramfs.img
}

menuentry "SmechVisor (debug console)" {
    linux   /boot/vmlinuz root=/dev/sda2 ro console=ttyS0,115200 \
            intel_iommu=on amd_iommu=on iommu=pt
    initrd  /boot/initramfs.img
}
GRUBCFG

# ── GRUB BIOS image ───────────────────────────────────────────────────────────
echo "[smechvisor-iso] Building GRUB BIOS El Torito image..."
grub-mkimage \
    -O i386-pc \
    -o "$WORK_DIR/boot/grub/core.img" \
    -p "/boot/grub" \
    biosdisk iso9660 normal linux echo configfile

grub-mkrescue \
    --output="$ISO_PATH" \
    "$WORK_DIR" \
    -- -volid "SMECHVISOR" 2>/dev/null \
|| {
    # Fallback: use xorriso directly if grub-mkrescue is unavailable
    echo "[smechvisor-iso] grub-mkrescue not found -- falling back to xorriso..."

    grub-mkstandalone \
        -O x86_64-efi \
        -o "$EFI_DIR/BOOTX64.EFI" \
        "boot/grub/grub.cfg=$BOOT_DIR/grub.cfg"

    xorriso -as mkisofs \
        -iso-level 3 \
        -full-iso9660-filenames \
        -volid "SMECHVISOR" \
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

echo "[smechvisor-iso] ISO COMPLETE: $ISO_PATH"
echo "[smechvisor-iso] Size: $(du -sh "$ISO_PATH" | cut -f1)"
echo ""
echo "  Boot this ISO on bare metal or in QEMU for testing:"
echo "  qemu-system-x86_64 -enable-kvm -m 2G -cdrom $ISO_PATH -serial stdio"
echo ""
echo "  smechvisord control plane: http://<host-ip>:8080"
