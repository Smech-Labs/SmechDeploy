#!/bin/bash
set -e

# Auto-detect directory layout
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MESA_SRC="$DEPLOY_ROOT/essentials/mesa"

export SMECH_TARGET="/mnt/smechos_build_root"
unset TARGET
export PATH="$PATH:$SMECH_TARGET/usr/bin"
export PKG_CONFIG_PATH="$SMECH_TARGET/usr/lib/x86_64-linux-gnu/pkgconfig:$SMECH_TARGET/usr/share/pkgconfig:$SMECH_TARGET/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export CFLAGS="-I$SMECH_TARGET/usr/include"
export CXXFLAGS="-I$SMECH_TARGET/usr/include"
export LDFLAGS="-L$SMECH_TARGET/usr/lib/x86_64-linux-gnu -L$SMECH_TARGET/usr/lib"
export LD_LIBRARY_PATH="$SMECH_TARGET/usr/lib:$SMECH_TARGET/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# Set up LLVM env configuration
export LLVM_CONFIG=/usr/bin/llvm-config-18

echo "[+] --- COMPILING MESA GRAPHICS STACK ---"
if [ ! -d "$MESA_SRC" ]; then
    echo "Error: Mesa source directory not found at $MESA_SRC"
    exit 1
fi

cd "$MESA_SRC"
rm -rf build_dir

# Pointing to Meson and configuring
meson setup build_dir --prefix=/usr \
    --libdir=lib/x86_64-linux-gnu \
    -Dgallium-drivers=radeonsi,iris,crocus \
    -Dgallium-opencl=icd \
    -Dgallium-rusticl=true \
    -Dvulkan-drivers=amd \
    -Dglx=disabled \
    -Dllvm=enabled \
    -Dplatforms=wayland \
    -Dbuildtype=release

ninja -C build_dir -j8
sudo DESTDIR="$SMECH_TARGET" ninja -C build_dir install

echo "[+] MESA STACK INSTALLED SUCCESSFULLY!"
