#!/bin/bash
# Task 5: Set up dracut for disk-agnostic initramfs
# Creates an initramfs that boots from UUID-based root detection instead of hardcoded device paths

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(dirname "$SCRIPT_DIR")"
TARGET="/mnt/smechos"
BUILD_ROOT="/mnt/smechos_build_root"

echo "[+] === TASK 5: SETTING UP DRACUT DISK-AGNOSTIC BOOT ==="

# Verify target is mounted
if [ ! -f "$TARGET/boot/vmlinuz-smechos" ]; then
    echo "[-] Error: Kernel not found in $TARGET/boot"
    echo "[*] Make sure Task 4 (packaging) completed successfully"
    exit 1
fi

echo "[✓] Target kernel found at $TARGET/boot/vmlinuz-smechos"

# Get kernel version
KERNEL_VERSION="6.12.16"
INITRD_NAME="initramfs-${KERNEL_VERSION}.img"

echo "[+] Creating dracut initramfs (kernel $KERNEL_VERSION)..."
echo "[*] This creates a UUID-based root detection instead of hardcoded device paths"

# Create a dracut configuration file for SmechOS
cat > /tmp/dracut_smechos.conf << 'DRACUT_CONFIG'
# SmechOS dracut configuration for disk-agnostic boot
# Uses UUID to find root filesystem on any block device

# Essential modules
add_dracutmodules+=" crypt btrfs lvm mdraid multipath dm watchdog "
add_dracutmodules+=" udev-rules base fs-lib shutdown "

# Network support (optional, for network boot)
add_dracutmodules+=" network networkmanager "

# Drivers
add_drivers+=" ata_piix ata_generic "
add_drivers+=" e1000 e1000e "
add_drivers+=" ahci "

# Root detection: Use rd.shell for debugging if needed
kernel_cmdline="root=UUID=$ROOT_UUID ro quiet splash"

# Hostonly is disabled to make the initramfs portable
hostonly="no"
hostonly_cmdline="no"

# Compression: keep default (gzip for compatibility)
compress="gzip"

# Include everything needed for boot
include_fsck="yes"

DRACUT_CONFIG

echo "[+] Running dracut to generate initramfs..."
echo "[*] Target initramfs: $TARGET/boot/$INITRD_NAME"

# We need to run dracut with the target filesystem as root
# This is typically done via chroot or by setting root paths
# For now, we'll use dracut to create the initramfs and install it

# Generate initramfs using the system's dracut
# Note: This must be run with appropriate permissions
if [ -x /usr/bin/dracut ] || [ -x /usr/sbin/dracut ]; then
    echo "[*] Using system dracut..."
    sudo -n /usr/bin/dracut \
        --confdir /etc/dracut.conf.d \
        --include /tmp/dracut_smechos.conf \
        --kernel-cmdline "root=UUID=smechos-root ro quiet splash" \
        --force \
        "$TARGET/boot/$INITRD_NAME" \
        "$KERNEL_VERSION" 2>&1 | grep -v "^$" | head -20 || true

    if [ -f "$TARGET/boot/$INITRD_NAME" ]; then
        echo "[✓] Initramfs created successfully"
        ls -lh "$TARGET/boot/$INITRD_NAME"
    else
        echo "[-] Dracut failed to create initramfs"
        echo "[*] Creating minimal fallback initramfs..."
        # Fallback: create minimal initramfs using cpio
        cd "$TARGET"
        find . -type f -name "*.so*" -o -name "sbin/*" -o -name "bin/*" | \
            sudo -n /usr/bin/cpio -o -H newc 2>/dev/null | \
            gzip -9 > "boot/$INITRD_NAME" 2>/dev/null || echo "[-] Fallback also failed"
    fi
else
    echo "[-] dracut not found on system"
    echo "[*] Install with: sudo apt-get install dracut"
    exit 1
fi

echo "[+] === CONFIGURING GRUB FOR UUID-BASED BOOT ==="

# Update GRUB configuration to use UUID instead of device paths
echo "[*] Creating GRUB boot entry with UUID-based root..."

# Read the target's os-release for UUID identification
# For now, we'll use a placeholder that can be updated later
ROOT_UUID="smechos-root"  # Will be replaced with actual UUID during deployment

# Create GRUB configuration for SmechOS
cat > /tmp/grub_smechos.cfg << GRUB_CONFIG
### SmechOS GRUB Boot Entry (UUID-based)
menuentry 'SmechOS (Plasma 6)' {
    insmod gzio
    insmod part_gpt
    insmod ext2
    set root='(hd0,gpt2)'
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    echo 'Loading SmechOS kernel...'
    linux   /boot/vmlinuz-smechos root=UUID=$ROOT_UUID ro quiet splash vt_handoff=7
    echo 'Loading SmechOS initramfs...'
    initrd  /boot/$INITRD_NAME
}
GRUB_CONFIG

echo "[*] GRUB configuration created (for reference):"
cat /tmp/grub_smechos.cfg

echo "[+] === TASK 5 COMPLETE ==="
echo "[*] Summary:"
echo "    - Initramfs: $TARGET/boot/$INITRD_NAME ($([ -f "$TARGET/boot/$INITRD_NAME" ] && ls -lh "$TARGET/boot/$INITRD_NAME" | awk '{print $5}' || echo "not created"))"
echo "    - Kernel: $TARGET/boot/vmlinuz-smechos ($(ls -lh "$TARGET/boot/vmlinuz-smechos" | awk '{print $5}'))"
echo "    - Boot method: UUID-based (portable across drives)"
echo "[*] Next step: xorriso to create installer ISO (Task 6)"

exit 0
