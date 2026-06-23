#!/bin/bash
export SMECH_TARGET="/mnt/smechos"
unset TARGET
export PATH="$SMECH_TARGET/usr/bin:$PATH"
export PKG_CONFIG_PATH="$SMECH_TARGET/usr/lib/x86_64-linux-gnu/pkgconfig:$SMECH_TARGET/usr/share/pkgconfig:$SMECH_TARGET/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
export CFLAGS="-I$SMECH_TARGET/usr/include"
export CXXFLAGS="-I$SMECH_TARGET/usr/include"
export LDFLAGS="-L$SMECH_TARGET/usr/lib/x86_64-linux-gnu -L$SMECH_TARGET/usr/lib"
export LD_LIBRARY_PATH="$SMECH_TARGET/usr/lib:$SMECH_TARGET/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

cd /tmp/smechos_build/plasma-workspace-6.6.5
cmake -B build_dir -GNinja \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_PREFIX_PATH="$SMECH_TARGET/usr" \
    -DBUILD_TESTING=OFF
