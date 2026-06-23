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

# Ensure Usr-Merge symlinks exist in target
sudo mkdir -p "$SMECH_TARGET/usr/bin" "$SMECH_TARGET/usr/sbin" "$SMECH_TARGET/usr/lib"
sudo ln -snf usr/bin "$SMECH_TARGET/bin"
sudo ln -snf usr/sbin "$SMECH_TARGET/sbin"
sudo ln -snf usr/lib "$SMECH_TARGET/lib"
sudo ln -snf usr/lib "$SMECH_TARGET/lib64"

# 1. Compile and Deploy GNU Bash 5.2
if [ ! -f "$SMECH_TARGET/bin/bash" ]; then
    echo "[+] --- STEP 1: COMPILING GNU BASH 5.2 ---"
    rm -rf /tmp/smechos_build/bash-5.2
    mkdir -p /tmp/smechos_build/bash-5.2
    tar -xf "$SOURCES_DIR/bash-5.2.tar.gz" -C /tmp/smechos_build/bash-5.2 --strip-components=1
    cd /tmp/smechos_build/bash-5.2
    ./configure --prefix=/usr --sysconfdir=/etc --without-bash-malloc --disable-nls
    make -j8
    sudo make DESTDIR="$SMECH_TARGET" install
fi
# Make sure bash is the default shell
sudo ln -sf bash "$SMECH_TARGET/bin/sh"
sudo ln -sf ../bin/bash "$SMECH_TARGET/usr/bin/bash"

# 2. Compile and Deploy OpenRC 0.54
if [ ! -f "$SMECH_TARGET/sbin/openrc-init" ]; then
    echo "[+] --- STEP 2: COMPILING OPENRC 0.54 ---"
    rm -rf /tmp/smechos_build/openrc-0.54
    mkdir -p /tmp/smechos_build/openrc-0.54
    tar -xf "$SOURCES_DIR/openrc-0.54.tar.gz" -C /tmp/smechos_build/openrc-0.54 --strip-components=1
    cd /tmp/smechos_build/openrc-0.54
    meson setup build_dir --prefix=/usr -Daudit=disabled -Dpam=false
    ninja -C build_dir -j8
    sudo DESTDIR="$SMECH_TARGET" ninja -C build_dir install
fi

# 3. Compile and Deploy GRUB 2.12 (BIOS Platform)
echo "[+] --- STEP 3: COMPILING GRUB 2.12 ---"
rm -rf /tmp/smechos_build/grub-2.12
mkdir -p /tmp/smechos_build/grub-2.12
tar -xf "$SOURCES_DIR/grub-2.12.tar.xz" -C /tmp/smechos_build/grub-2.12 --strip-components=1
cd /tmp/smechos_build/grub-2.12
./configure --prefix=/usr --sysconfdir=/etc --disable-werror
touch grub-core/extra_deps.lst
make -j8
sudo make DESTDIR="$SMECH_TARGET" install

echo "[+] CORE SYSTEM INSTALLED SUCCESSFULLY!"
