#!/bin/bash
# Phase 2.5: Package and optimize build-root into 5GB target image
# This script copies runtime files from /mnt/smechos_build_root into the 5GB
# mounted filesystem at /mnt/smechos, excluding development files, debug symbols,
# and unnecessary content.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_ROOT="/mnt/smechos_build_root"
TARGET="/mnt/smechos"

echo "[+] === PHASE 2.5: PACKAGING BUILD-ROOT INTO 5GB TARGET ==="

# Mount target image if not already mounted
if ! mountpoint -q "$TARGET"; then
    echo "[*] Mounting target image..."
    # The target image is mounted via qemu-nbd + debugfs in earlier phases
    # For now, verify it can be accessed
    if [ ! -d "$TARGET/usr" ]; then
        echo "[-] Error: $TARGET doesn't appear to be mounted and doesn't have expected structure"
        exit 1
    fi
fi

echo "[+] Target accessed at $TARGET"

# Get available space on target
TARGET_SPACE=$(df "$TARGET" | awk 'NR==2 {print $4}')
echo "[*] Available space on target: ${TARGET_SPACE}KB (~$((TARGET_SPACE / 1024 / 1024))GB)"

# Function to copy all runtime files from build root
copy_runtime_files() {
    echo "[+] Copying all runtime files from build root..."
    echo "[*] Build root size: $(du -sh "$BUILD_ROOT" | cut -f1)"

    # Use rsync to copy entire build root, excluding only unnecessary files
    # --archive: recursive, preserve permissions/timestamps/symlinks
    # --delete: remove files in target that don't exist in source
    # --exclude: skip unnecessary files

    echo "[*] Running rsync from $BUILD_ROOT to $TARGET..."
    sudo -n /usr/bin/rsync -a --delete \
        --exclude='*.o' \
        --exclude='*.a' \
        --exclude='*.la' \
        --exclude='.cmake' \
        --exclude='CMakeFiles' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='usr/include' \
        --exclude='usr/share/man' \
        --exclude='usr/share/doc' \
        --exclude='usr/share/examples' \
        --exclude='usr/lib/cmake' \
        --exclude='*.pc' \
        "$BUILD_ROOT/" "$TARGET/"

    if [ $? -eq 0 ]; then
        echo "[✓] Rsync completed successfully"
    else
        echo "[-] Rsync encountered errors, continuing..."
    fi
}

# Function to strip development files
strip_dev_files() {
    echo "[+] Stripping development files from target..."

    # Remove development headers
    echo "[*] Removing /usr/include..."
    sudo -n rm -rf "$TARGET/usr/include" 2>/dev/null || true

    # Remove static libraries
    echo "[*] Removing static libraries (*.a)..."
    find "$TARGET/usr/lib" -name "*.a" -delete 2>/dev/null || true

    # Remove CMake configs
    echo "[*] Removing CMake configs..."
    find "$TARGET/usr/lib" -path "*/cmake/*" -delete 2>/dev/null || true

    # Remove pkg-config files (dev tools)
    echo "[*] Removing pkg-config files..."
    find "$TARGET/usr/lib" -name "*.pc" -delete 2>/dev/null || true

    # Remove debug symbols from shared libraries (selective)
    echo "[*] Stripping debug symbols..."
    find "$TARGET/usr/lib/x86_64-linux-gnu" -name "*.so*" -type f -exec file {} \; | grep -E "ELF.*not stripped" | awk '{print $1}' | sed 's/:$//' | while read f; do
        echo "[*] Stripping $f..."
        sudo -n /usr/bin/strip "$f" 2>/dev/null || true
    done
}

# Function to remove unnecessary files
remove_unnecessary() {
    echo "[+] Removing unnecessary files..."

    # Remove man pages (will save significant space)
    echo "[*] Removing man pages..."
    sudo -n rm -rf "$TARGET/usr/share/man" 2>/dev/null || true

    # Remove doc files
    echo "[*] Removing documentation..."
    sudo -n rm -rf "$TARGET/usr/share/doc" 2>/dev/null || true

    # Remove examples
    echo "[*] Removing examples..."
    sudo -n rm -rf "$TARGET/usr/share/examples" 2>/dev/null || true

    # Remove test files
    echo "[*] Removing test files..."
    find "$TARGET" -type d -name "*test*" -delete 2>/dev/null || true

    # Remove unnecessary locales (keep only en)
    echo "[*] Pruning locales..."
    for locale_dir in "$TARGET/usr/share/locale" "$TARGET/usr/share/locales"; do
        if [ -d "$locale_dir" ]; then
            find "$locale_dir" -mindepth 1 -maxdepth 1 ! -name "en*" ! -name "C" -delete 2>/dev/null || true
        fi
    done

    # Remove systemd catalog (if exists)
    sudo -n rm -rf "$TARGET/var/lib/systemd/catalog" 2>/dev/null || true
}

# Function to verify critical files exist
verify_critical_files() {
    echo "[+] Verifying critical files..."

    local critical_files=(
        "/bin/bash"
        "/usr/bin/startplasma-wayland"
        "/usr/bin/plasmashell"
        "/boot/vmlinuz-6.12.16"
        "/usr/lib/x86_64-linux-gnu/libc.so.6"
    )

    for file in "${critical_files[@]}"; do
        if [ -f "$TARGET$file" ]; then
            echo "[✓] Found $file"
        else
            echo "[-] Missing critical file: $file"
        fi
    done
}

# Main execution
echo "[*] Starting packaging process..."
copy_runtime_files
strip_dev_files
remove_unnecessary
verify_critical_files

# Final space check
TARGET_SPACE_AFTER=$(df "$TARGET" | awk 'NR==2 {print $4}')
SPACE_USED=$((TARGET_SPACE - TARGET_SPACE_AFTER))
echo "[+] === PACKAGING COMPLETE ==="
echo "[*] Space used: ~$((SPACE_USED / 1024 / 1024))GB / ~5000MB target"

if [ "$SPACE_USED" -lt $((5000 * 1024)) ]; then
    echo "[✓] Successfully packaged within 5GB target"
else
    echo "[-] WARNING: Packaged files may exceed 5GB target"
    echo "[*] Consider further optimization or increasing target image size"
fi

exit 0
