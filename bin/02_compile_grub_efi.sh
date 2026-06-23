#!/bin/bash
set -e

# Auto-detect directory layout
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCES_DIR="$DEPLOY_ROOT/essentials/sources"

export SMECH_TARGET="/mnt/smechos_build_root"
unset TARGET
export PATH="$SMECH_TARGET/usr/bin:$PATH"
export PKG_CONFIG_PATH="$SMECH_TARGET/usr/lib/x86_64-linux-gnu/pkgconfig:$SMECH_TARGET/usr/share/pkgconfig:$SMECH_TARGET/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export CFLAGS="-I$SMECH_TARGET/usr/include"
export CXXFLAGS="-I$SMECH_TARGET/usr/include"
export LDFLAGS="-L$SMECH_TARGET/usr/lib/x86_64-linux-gnu -L$SMECH_TARGET/usr/lib"
export LD_LIBRARY_PATH="$SMECH_TARGET/usr/lib:$SMECH_TARGET/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

echo "[+] COMPILING GRUB 2.12 FOR UEFI (X86_64-EFI)..."
rm -rf /tmp/smechos_build/grub-efi
mkdir -p /tmp/smechos_build/grub-efi
tar -xf "$SOURCES_DIR/grub-2.12.tar.xz" -C /tmp/smechos_build/grub-efi --strip-components=1
cd /tmp/smechos_build/grub-efi

./configure --prefix=/usr --sysconfdir=/etc --with-platform=efi --target=x86_64 --disable-werror
touch grub-core/extra_deps.lst
make -j8
sudo make DESTDIR="$SMECH_TARGET" install

echo "[+] GRUB UEFI COMPILATION COMPLETE!"
