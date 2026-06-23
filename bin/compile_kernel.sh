#!/bin/bash
set -e

# Auto-detect directory layout
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KERNEL_SRC="$DEPLOY_ROOT/essentials/linux-6.12.16"

export SMECH_TARGET="/mnt/smechos_build_root"
unset TARGET

echo "[+] --- COMPILING LINUX KERNEL 6.12.16 ---"
if [ ! -d "$KERNEL_SRC" ]; then
    echo "Error: Kernel source directory not found at $KERNEL_SRC"
    exit 1
fi

cd "$KERNEL_SRC"
if [ ! -f .config ]; then
    make defconfig
fi

make -j8
sudo make modules_install INSTALL_MOD_PATH="$SMECH_TARGET"
sudo mkdir -p "$SMECH_TARGET/boot"
sudo cp arch/x86/boot/bzImage "$SMECH_TARGET/boot/vmlinuz-smechos"

echo "[+] LINUX KERNEL INSTALLED SUCCESSFULLY!"
