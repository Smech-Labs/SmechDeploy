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

# ROOT CAUSE (found after chasing several individual symptoms one at a
# time): autoconf's own compiler sanity check compiles a trivial test
# program with musl-clang and then tries to *execute* it to decide whether
# it's cross-compiling. Since the musl-linked test binary happens to run
# fine on this same-arch build host (just linked against a different libc,
# not actually unable to execute), autoconf concludes cross_compiling=no --
# which then makes every gnulib portability probe actually run its runtime
# test against musl instead of taking the safe cross-compile-assumed
# fallback (several of which already have correct musl-specific logic,
# e.g. gnulib's own `*-musl*) gl_cv_func_getgroups_works=yes` case, that
# never gets reached because cross-compiling was never properly detected).
#
# The real fix is forcing autoconf to trust the explicit --host designation
# instead of guessing via execution -- passing --build explicitly (below,
# in build_pkg) does this. These two cache variable exports are kept as a
# narrow extra safety net for the two specific probes that broke before
# --build was added; --build alone may already be sufficient.
export gl_cv_func_fflush_stdin=cross
export gl_cv_func_getgroups_works=yes

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

    CC="$CC" ./configure --prefix=/usr --build=x86_64-linux-gnu --host=x86_64-linux-musl "${configure_args[@]}"
    # Man-page generation runs the freshly-built binary with --help via
    # help2man. This works fine as long as the binary doesn't depend on a
    # host-side optional library that wasn't built for musl (selinux/
    # openssl/gmp/libcap turned out to be exactly that for coreutils, fixed
    # via configure flags above) -- once it's a clean musl binary, real
    # help2man runs it successfully, so it's left enabled rather than
    # stubbed out (a HELP2MAN=true override was tried and breaks packages
    # whose Makefiles invoke it as a Perl script path rather than a
    # standalone command, e.g. sed).
    make -j"$(nproc)"
    sudo make DESTDIR="$SMECH_TARGET" install
}

build_pkg coreutils  9.5    coreutils-9.5.tar.xz    https://ftp.gnu.org/gnu/coreutils/coreutils-9.5.tar.xz \
    --disable-acl --disable-xattr --without-selinux --without-openssl --without-libgmp --disable-libcap

build_pkg grep       3.11   grep-3.11.tar.xz        https://ftp.gnu.org/gnu/grep/grep-3.11.tar.xz \
    --without-selinux --disable-perl-regexp

build_pkg sed        4.9    sed-4.9.tar.xz          https://ftp.gnu.org/gnu/sed/sed-4.9.tar.xz \
    --without-selinux --disable-acl

build_pkg tar        1.35   tar-1.35.tar.xz         https://ftp.gnu.org/gnu/tar/tar-1.35.tar.xz \
    --disable-acl --without-selinux --without-posix-acls

build_pkg gzip       1.13   gzip-1.13.tar.xz        https://ftp.gnu.org/gnu/gzip/gzip-1.13.tar.xz

build_pkg xz         5.6.2  xz-5.6.2.tar.xz         https://github.com/tukaani-project/xz/releases/download/v5.6.2/xz-5.6.2.tar.xz

build_pkg findutils  4.10.0 findutils-4.10.0.tar.xz https://ftp.gnu.org/gnu/findutils/findutils-4.10.0.tar.xz \
    --without-selinux

build_pkg diffutils  3.10   diffutils-3.10.tar.xz   https://ftp.gnu.org/gnu/diffutils/diffutils-3.10.tar.xz

build_pkg gawk       5.3.0  gawk-5.3.0.tar.xz       https://ftp.gnu.org/gnu/gawk/gawk-5.3.0.tar.xz \
    --disable-mpfr

build_pkg make       4.4.1  make-4.4.1.tar.gz       https://ftp.gnu.org/gnu/make/make-4.4.1.tar.gz

# file(1) is not a GNU package and uses its own configure, but the same
# CC=musl-clang / --host=x86_64-linux-musl pattern applies.
build_pkg file        5.45   file-5.45.tar.gz        https://astron.com/pub/file/file-5.45.tar.gz \
    --disable-zlib --disable-bzlib --disable-zstdlib --disable-libseccomp

echo "[+] STAGE 2 COMPLETE -- GNU userland compiled against musl"
