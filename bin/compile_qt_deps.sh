#!/bin/bash
set -e

export SMECH_TARGET="/mnt/smechos"
unset TARGET
export PATH="$SMECH_TARGET/usr/bin:$PATH"
export PKG_CONFIG_PATH="$SMECH_TARGET/usr/lib/x86_64-linux-gnu/pkgconfig:$SMECH_TARGET/usr/share/pkgconfig:$SMECH_TARGET/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export CFLAGS="-I$SMECH_TARGET/usr/include"
export CXXFLAGS="-I$SMECH_TARGET/usr/include"
export LDFLAGS="-L$SMECH_TARGET/usr/lib/x86_64-linux-gnu -L$SMECH_TARGET/usr/lib"
export LD_LIBRARY_PATH="$SMECH_TARGET/usr/lib:$SMECH_TARGET/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

mkdir -p /tmp/smechos_build/sources

# 1. QtPositioning
if [ ! -f /tmp/smechos_build/sources/qtpositioning-everywhere-src-6.8.2.tar.xz ]; then
    echo "[+] Downloading qtpositioning..."
    wget -O /tmp/smechos_build/sources/qtpositioning-everywhere-src-6.8.2.tar.xz "https://download.qt.io/official_releases/qt/6.8/6.8.2/submodules/qtpositioning-everywhere-src-6.8.2.tar.xz"
fi

echo "[+] Extracting qtpositioning..."
rm -rf /tmp/smechos_build/qtpositioning
mkdir -p /tmp/smechos_build/qtpositioning
tar -xf /tmp/smechos_build/sources/qtpositioning-everywhere-src-6.8.2.tar.xz -C /tmp/smechos_build/qtpositioning --strip-components=1

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
if [ ! -f /tmp/smechos_build/sources/qtlocation-everywhere-src-6.8.2.tar.xz ]; then
    echo "[+] Downloading qtlocation..."
    wget -O /tmp/smechos_build/sources/qtlocation-everywhere-src-6.8.2.tar.xz "https://download.qt.io/official_releases/qt/6.8/6.8.2/submodules/qtlocation-everywhere-src-6.8.2.tar.xz"
fi

echo "[+] Extracting qtlocation..."
rm -rf /tmp/smechos_build/qtlocation
mkdir -p /tmp/smechos_build/qtlocation
tar -xf /tmp/smechos_build/sources/qtlocation-everywhere-src-6.8.2.tar.xz -C /tmp/smechos_build/qtlocation --strip-components=1

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
