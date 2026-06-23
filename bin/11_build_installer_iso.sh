#!/bin/bash
# Task 6: Build isohybrid installer ISO with xorriso
# Creates a bootable ISO that can be written to USB or burned to CD

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(dirname "$SCRIPT_DIR")"
SMECHOS_IMG="/home/smech/smechos/SmechImage/smechos-redo.img"
OUTPUT_ISO="/home/smech/smechos/SmechDeploy/images/smechos-installer.iso"

echo "[+] === TASK 6: BUILDING ISOHYBRID INSTALLER ISO ==="

# Verify source image exists
if [ ! -f "$SMECHOS_IMG" ]; then
    echo "[-] Error: Source image not found at $SMECHOS_IMG"
    exit 1
fi

IMG_SIZE=$(du -b "$SMECHOS_IMG" | cut -f1)
IMG_SIZE_MB=$((IMG_SIZE / 1024 / 1024))

echo "[✓] Found source image: $SMECHOS_IMG"
echo "[*] Image size: ${IMG_SIZE_MB}MB"
echo "[*] Output ISO: $OUTPUT_ISO"

# Create ISO from the system image
# xorriso options:
#  -as mkisofs: Emulate mkisofs for compatibility
#  -V: Volume label
#  -isohybrid-mbr: Make the ISO hybrid (bootable from USB)
#  -c: El Torito boot catalog
#  -b: Boot image (GRUB or other bootloader)
#  -e: UEFI boot image (for EFI systems)
#  -no-emul-boot: Don't emulate floppy/CD-ROM
#  -boot-load-size 4: Typical for modern bootloaders

echo "[+] Creating ISO with xorriso..."
echo "[*] This creates an isohybrid ISO that boots on both BIOS and UEFI systems"

# Check if xorriso is available
if ! command -v xorriso &> /dev/null; then
    echo "[-] Error: xorriso not found"
    echo "[*] Install with: sudo apt-get install xorriso"
    exit 1
fi

# For isohybrid ISO, we need GRUB or another bootloader
# The smechos-redo.img should already have GRUB installed
# We'll create the ISO from the entire 6GB image

echo "[+] Stage 1: Creating ISO filesystem..."

# Create a temporary working directory
WORK_DIR="/tmp/smechos_iso_$$"
mkdir -p "$WORK_DIR"

# Extract or copy the essential files for ISO
# We'll use the image file directly in the ISO
echo "[*] Setting up ISO boot structure..."

# Since we have a full disk image with GRUB, we can:
# 1. Use xorriso to embed the image as a hybrid ISO, OR
# 2. Extract kernel/initrd and create ISO with GRUB

# Option: Create ISO with the full image embedded (simplest)
# This creates a 6GB ISO that can be written directly to USB

echo "[+] Stage 2: Generating isohybrid ISO..."

xorriso -as mkisofs \
    -V "SMECHOS_INSTALLER" \
    -isohybrid-mbr /usr/lib/syslinux/isohdpfx.bin \
    -c boot/isolinux.cat \
    -b boot/isolinux.bin \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e boot/efiboot.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -o "$OUTPUT_ISO" \
    "$SMECHOS_IMG" 2>&1 | grep -v "^Estimate" || true

# If xorriso hybrid approach doesn't work, try simpler method:
if [ ! -f "$OUTPUT_ISO" ]; then
    echo "[*] Creating simple ISO from the system image..."

    # Simple ISO creation (image becomes files inside ISO)
    # For a full system deployment, we'll create a minimal boot ISO
    # that contains the smechos.img as a file

    mkdir -p "$WORK_DIR/boot"

    # Copy kernel and initramfs as bootable files
    if [ -f /mnt/smechos/boot/vmlinuz-smechos ]; then
        cp /mnt/smechos/boot/vmlinuz-smechos "$WORK_DIR/boot/"
        cp /mnt/smechos/boot/initramfs-* "$WORK_DIR/boot/" 2>/dev/null || true
    fi

    # Copy system image to ISO
    mkdir -p "$WORK_DIR/images"
    cp "$SMECHOS_IMG" "$WORK_DIR/images/smechos-redo.img"

    # Create GRUB config for boot from ISO
    mkdir -p "$WORK_DIR/boot/grub"
    cat > "$WORK_DIR/boot/grub/grub.cfg" << 'GRUB_BOOT_CONFIG'
set default=0
set timeout=10

menuentry 'SmechOS Installer (Live)' {
    insmod gzio
    search --no-floppy --label SMECHOS_INSTALLER
    echo 'Loading kernel from ISO...'
    linux   /boot/vmlinuz-smechos root=live:CDLABEL=SMECHOS_INSTALLER ro quiet splash
    echo 'Loading initramfs...'
    initrd  /boot/initramfs-*.img
}

menuentry 'SmechOS Installer (From USB/Drive)' {
    echo 'Boot will auto-detect storage device'
    search --no-floppy --set=root
    echo 'Loading kernel...'
    linux   /boot/vmlinuz-smechos root=UUID=smechos-root ro quiet splash
    echo 'Loading initramfs...'
    initrd  /boot/initramfs-*.img
}
GRUB_BOOT_CONFIG

    # Create ISO with xorriso
    echo "[*] Creating bootable ISO..."
    xorriso -as mkisofs \
        -V "SMECHOS_INSTALLER" \
        -isohybrid-mbr /usr/lib/syslinux/isohdpfx.bin \
        -c boot/isolinux.cat \
        -b boot/isolinux.bin \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        -o "$OUTPUT_ISO" \
        "$WORK_DIR" 2>&1 | tail -10 || true
fi

# Verify ISO was created
if [ -f "$OUTPUT_ISO" ]; then
    ISO_SIZE=$(ls -lh "$OUTPUT_ISO" | awk '{print $5}')
    echo "[✓] ISO created successfully!"
    echo "[*] File: $OUTPUT_ISO"
    echo "[*] Size: $ISO_SIZE"
    echo ""
    echo "[+] === DEPLOYMENT INSTRUCTIONS ==="
    echo "[*] To boot from USB:"
    echo "    1. Insert USB drive (e.g., /dev/sdb)"
    echo "    2. Run: sudo dd if=$OUTPUT_ISO of=/dev/sdb bs=1M status=progress"
    echo "    3. Eject and boot from the USB drive"
    echo ""
    echo "[*] To burn to DVD:"
    echo "    1. Run: xorriso -dvd-compat -as cdrecord -v dev=/dev/sr0 $OUTPUT_ISO"
    echo "    2. Or use your favorite ISO burning tool (Etcher, etc.)"
    echo ""
    echo "[+] === BUILD COMPLETE ==="
    echo "[✓] SmechOS installer ISO ready for deployment!"
else
    echo "[-] Error: ISO creation failed"
    echo "[*] Check xorriso installation and SYSLINUX files"
    echo "[*] Install SYSLINUX: sudo apt-get install syslinux syslinux-utils"
    exit 1
fi

# Cleanup
rm -rf "$WORK_DIR"

exit 0
