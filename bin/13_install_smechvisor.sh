#!/bin/bash
# SmechDeploy Phase -- Install SmechVisor control plane into $SMECH_TARGET
#
# Clones Smech-Labs/smechvisord, builds the Rust daemon, and installs:
#   - smechvisord binary        → $SMECH_TARGET/usr/sbin/
#   - web assets                → $SMECH_TARGET/usr/share/smechvisord/web/
#   - OpenRC init scripts       → $SMECH_TARGET/etc/init.d/
#   - default runlevel symlinks → $SMECH_TARGET/etc/runlevels/default/
#   - cloud-hypervisor binary   → $SMECH_TARGET/usr/sbin/ (downloaded)
#   - vhost-user-gpu binary     → $SMECH_TARGET/usr/sbin/ (downloaded)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SMECH_TARGET="${SMECH_TARGET:-/mnt/smechos_build_root}"

SMECHVISORD_REPO="https://github.com/Smech-Labs/smechvisord.git"
SMECHVISORD_BUILD_DIR="/tmp/smechos_build/smechvisord"

# cloud-hypervisor release to pin -- update when upstream cuts a new stable
CH_VERSION="${CH_VERSION:-42.0}"
CH_URL="https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CH_VERSION}/cloud-hypervisor-static"

VHOST_GPU_URL="${VHOST_GPU_URL:-}"   # Set externally if a pre-built binary exists

echo "[smechvisor] SMECH_TARGET = $SMECH_TARGET"

# ── Clone / update smechvisord ─────────────────────────────────────────────────
if [ -d "$SMECHVISORD_BUILD_DIR/.git" ]; then
    echo "[smechvisor] Updating smechvisord checkout..."
    git -C "$SMECHVISORD_BUILD_DIR" pull --ff-only
else
    echo "[smechvisor] Cloning smechvisord..."
    rm -rf "$SMECHVISORD_BUILD_DIR"
    git clone "$SMECHVISORD_REPO" "$SMECHVISORD_BUILD_DIR"
fi

# ── Build smechvisord daemon ───────────────────────────────────────────────────
echo "[smechvisor] Compiling smechvisord (Rust/Axum)..."
cd "$SMECHVISORD_BUILD_DIR/daemon"
cargo build --release
DAEMON_BIN="$SMECHVISORD_BUILD_DIR/daemon/target/release/smechvisord"

# ── Create target directories ──────────────────────────────────────────────────
for dir in \
    "$SMECH_TARGET/usr/sbin" \
    "$SMECH_TARGET/usr/share/smechvisord/web" \
    "$SMECH_TARGET/etc/init.d" \
    "$SMECH_TARGET/etc/runlevels/sysinit" \
    "$SMECH_TARGET/etc/runlevels/boot" \
    "$SMECH_TARGET/etc/runlevels/default" \
    "$SMECH_TARGET/etc/runlevels/shutdown" \
    "$SMECH_TARGET/var/log/smechvisord" \
    "$SMECH_TARGET/var/lib/smechvisord/vms" \
    "$SMECH_TARGET/run/smechvisord"; do
    sudo mkdir -p "$dir"
done

# ── Install smechvisord binary and web assets ──────────────────────────────────
echo "[smechvisor] Installing smechvisord daemon..."
sudo install -m 755 "$DAEMON_BIN" "$SMECH_TARGET/usr/sbin/smechvisord"

echo "[smechvisor] Installing web assets..."
sudo cp -r "$SMECHVISORD_BUILD_DIR/web/." "$SMECH_TARGET/usr/share/smechvisord/web/"

# ── Install OpenRC init scripts ────────────────────────────────────────────────
echo "[smechvisor] Installing OpenRC init scripts..."
sudo install -m 755 "$SMECHVISORD_BUILD_DIR/openrc/smechvisord"    "$SMECH_TARGET/etc/init.d/smechvisord"
sudo install -m 755 "$SMECHVISORD_BUILD_DIR/openrc/vhost-user-gpu" "$SMECH_TARGET/etc/init.d/vhost-user-gpu"

# ── Wire OpenRC runlevels ──────────────────────────────────────────────────────
echo "[smechvisor] Configuring OpenRC runlevels..."

# sysinit
for svc in devfs dmesg udev cgroups; do
    sudo ln -sf "/etc/init.d/$svc" "$SMECH_TARGET/etc/runlevels/sysinit/$svc" 2>/dev/null || true
done

# boot
for svc in modules localmount hostname networking; do
    sudo ln -sf "/etc/init.d/$svc" "$SMECH_TARGET/etc/runlevels/boot/$svc" 2>/dev/null || true
done

# default -- GPU daemon before smechvisord, per init script dependency ordering
sudo ln -sf "/etc/init.d/vhost-user-gpu" "$SMECH_TARGET/etc/runlevels/default/vhost-user-gpu"
sudo ln -sf "/etc/init.d/smechvisord"    "$SMECH_TARGET/etc/runlevels/default/smechvisord"

# shutdown
for svc in mount-ro savecache killprocs; do
    sudo ln -sf "/etc/init.d/$svc" "$SMECH_TARGET/etc/runlevels/shutdown/$svc" 2>/dev/null || true
done

# ── Download cloud-hypervisor ──────────────────────────────────────────────────
echo "[smechvisor] Downloading cloud-hypervisor v${CH_VERSION}..."
CH_DEST="$SMECH_TARGET/usr/sbin/cloud-hypervisor"
if [ ! -f "$CH_DEST" ]; then
    sudo wget -q -O "$CH_DEST" "$CH_URL"
    sudo chmod 755 "$CH_DEST"
else
    echo "[smechvisor] cloud-hypervisor already present, skipping download."
fi

# ── Download vhost-user-gpu (if URL provided) ──────────────────────────────────
if [ -n "$VHOST_GPU_URL" ]; then
    echo "[smechvisor] Downloading vhost-user-gpu..."
    sudo wget -q -O "$SMECH_TARGET/usr/sbin/vhost-user-gpu" "$VHOST_GPU_URL"
    sudo chmod 755 "$SMECH_TARGET/usr/sbin/vhost-user-gpu"
else
    echo "[smechvisor] VHOST_GPU_URL not set -- skipping vhost-user-gpu download."
    echo "             Set VHOST_GPU_URL before running to install a pre-built binary."
fi

echo "[smechvisor] INSTALL COMPLETE"
echo "  smechvisord   → $SMECH_TARGET/usr/sbin/smechvisord"
echo "  cloud-hyperv  → $SMECH_TARGET/usr/sbin/cloud-hypervisor"
echo "  web assets    → $SMECH_TARGET/usr/share/smechvisord/web/"
echo "  init scripts  → $SMECH_TARGET/etc/init.d/"
