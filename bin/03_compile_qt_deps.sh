#!/bin/bash
set -e

# Auto-detect directory layout
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCES_DIR="$DEPLOY_ROOT/essentials/sources"

export SMECH_TARGET="/mnt/smechos_build_root"
unset TARGET
export PATH="$PATH:$SMECH_TARGET/usr/bin"
export PKG_CONFIG_PATH="$SMECH_TARGET/usr/lib/x86_64-linux-gnu/pkgconfig:$SMECH_TARGET/usr/share/pkgconfig:$SMECH_TARGET/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export CFLAGS="-I$SMECH_TARGET/usr/include"
export CXXFLAGS="-I$SMECH_TARGET/usr/include"
export LDFLAGS="-L$SMECH_TARGET/usr/lib/x86_64-linux-gnu -L$SMECH_TARGET/usr/lib"
export LD_LIBRARY_PATH="$SMECH_TARGET/usr/lib:$SMECH_TARGET/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

mkdir -p "$SOURCES_DIR"

# 1. QtPositioning
if [ ! -f "$SOURCES_DIR/qtpositioning-everywhere-src-6.8.2.tar.xz" ]; then
    echo "[+] Downloading qtpositioning..."
    wget -O "$SOURCES_DIR/qtpositioning-everywhere-src-6.8.2.tar.xz" "https://download.qt.io/official_releases/qt/6.8/6.8.2/submodules/qtpositioning-everywhere-src-6.8.2.tar.xz"
fi

echo "[+] Extracting qtpositioning..."
rm -rf /tmp/smechos_build/qtpositioning
mkdir -p /tmp/smechos_build/qtpositioning
tar -xf "$SOURCES_DIR/qtpositioning-everywhere-src-6.8.2.tar.xz" -C /tmp/smechos_build/qtpositioning --strip-components=1

echo "[+] Configuring qtpositioning..."
cd /tmp/smechos_build/qtpositioning
cmake -B build_dir -GNinja \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_PREFIX_PATH="$SMECH_TARGET/usr" \
    -DBUILD_TESTING=OFF

echo "[+] Compiling qtpositioning..."
cmake --build build_dir -j4

echo "[+] Installing qtpositioning..."
sudo DESTDIR="$SMECH_TARGET" cmake --install build_dir


# 2. QtLocation
if [ ! -f "$SOURCES_DIR/qtlocation-everywhere-src-6.8.2.tar.xz" ]; then
    echo "[+] Downloading qtlocation..."
    wget -O "$SOURCES_DIR/qtlocation-everywhere-src-6.8.2.tar.xz" "https://download.qt.io/official_releases/qt/6.8/6.8.2/submodules/qtlocation-everywhere-src-6.8.2.tar.xz"
fi

echo "[+] Extracting qtlocation..."
rm -rf /tmp/smechos_build/qtlocation
mkdir -p /tmp/smechos_build/qtlocation
tar -xf "$SOURCES_DIR/qtlocation-everywhere-src-6.8.2.tar.xz" -C /tmp/smechos_build/qtlocation --strip-components=1

echo "[+] Configuring qtlocation..."
cd /tmp/smechos_build/qtlocation
cmake -B build_dir -GNinja \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_PREFIX_PATH="$SMECH_TARGET/usr" \
    -DBUILD_TESTING=OFF

echo "[+] Compiling qtlocation..."
cmake --build build_dir -j4

echo "[+] Installing qtlocation..."
sudo DESTDIR="$SMECH_TARGET" cmake --install build_dir

echo "[+] Qt location/positioning dependencies installed successfully!"
