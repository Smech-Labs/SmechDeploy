#!/bin/bash
# SmechOS independent userland bootstrap -- Stage 2 (see MUSL_BOOTSTRAP_PLAN.md)
#
# Compiles the GNU userland (coreutils, grep, sed, tar, gzip, xz, findutils,
# diffutils, gawk, make, file) from source against the musl install produced
# by 10_bootstrap_musl.sh, using musl-clang instead of host GCC/glibc. This
# is what replaces restore_utils.py's copy-from-/mnt/kaymium_sovereign
# behavior for the bulk of /usr/bin.
#
# Wired into build_order.txt as the second Phase 1 step, run immediately
# after 10_bootstrap_musl.sh against the same $SMECH_TARGET. Not yet
# test-run -- see MUSL_BOOTSTRAP_PLAN.md.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCES_DIR="$DEPLOY_ROOT/essentials/sources"

export SMECH_TARGET="${SMECH_TARGET:-/mnt/smechos_build_root}"
export CC="$SMECH_TARGET/usr/bin/musl-clang"

if [ ! -x "$CC" ]; then
    echo "Error: $CC not found. Run 10_bootstrap_musl.sh first."
    exit 1
fi

build_pkg() {
    local name="$1" version="$2" tarball="$3" url="$4"
    shift 4
    local configure_args=("$@")

    echo "[+] --- Compiling $name $version (musl) ---"
    if [ ! -f "$SOURCES_DIR/$tarball" ]; then
        echo "[+] Downloading $name $version..."
        wget -O "$SOURCES_DIR/$tarball" "$url"
    fi

    local build_dir="/tmp/smechos_build/${name}-${version}-musl"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"
    tar -xf "$SOURCES_DIR/$tarball" -C "$build_dir" --strip-components=1
    cd "$build_dir"

    CC="$CC" ./configure --prefix=/usr --host=x86_64-linux-musl "${configure_args[@]}"
    make -j"$(nproc)"
    sudo make DESTDIR="$SMECH_TARGET" install
}

build_pkg coreutils  9.5    coreutils-9.5.tar.xz    https://ftp.gnu.org/gnu/coreutils/coreutils-9.5.tar.xz \
    --disable-acl --disable-xattr

build_pkg grep       3.11   grep-3.11.tar.xz        https://ftp.gnu.org/gnu/grep/grep-3.11.tar.xz

build_pkg sed        4.9    sed-4.9.tar.xz          https://ftp.gnu.org/gnu/sed/sed-4.9.tar.xz

build_pkg tar        1.35   tar-1.35.tar.xz         https://ftp.gnu.org/gnu/tar/tar-1.35.tar.xz

build_pkg gzip       1.13   gzip-1.13.tar.xz        https://ftp.gnu.org/gnu/gzip/gzip-1.13.tar.xz

build_pkg xz         5.6.2  xz-5.6.2.tar.xz         https://github.com/tukaani-project/xz/releases/download/v5.6.2/xz-5.6.2.tar.xz

build_pkg findutils  4.10.0 findutils-4.10.0.tar.xz https://ftp.gnu.org/gnu/findutils/findutils-4.10.0.tar.xz

build_pkg diffutils  3.10   diffutils-3.10.tar.xz   https://ftp.gnu.org/gnu/diffutils/diffutils-3.10.tar.xz

build_pkg gawk       5.3.0  gawk-5.3.0.tar.xz       https://ftp.gnu.org/gnu/gawk/gawk-5.3.0.tar.xz

build_pkg make       4.4.1  make-4.4.1.tar.gz       https://ftp.gnu.org/gnu/make/make-4.4.1.tar.gz

# file(1) is not a GNU package and uses its own configure, but the same
# CC=musl-clang / --host=x86_64-linux-musl pattern applies.
build_pkg file        5.45   file-5.45.tar.gz        https://astron.com/pub/file/file-5.45.tar.gz

echo "[+] STAGE 2 COMPLETE -- GNU userland compiled against musl"
