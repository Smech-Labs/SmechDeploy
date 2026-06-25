#!/bin/bash
# SmechOS Sovereign Build Orchestrator
set -e

# Target mount point
TARGET_MOUNT="/mnt/smechos"

# Auto-detect SmechDeploy directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$ROOT_DIR/build_order.txt"
VENV_DIR="$ROOT_DIR/.venv"

echo "--- Starting SmechOS Sovereign Build Sequence ---"
echo "Targeting mount point: $TARGET_MOUNT"
echo "Manifest file: $MANIFEST"

# Ensure Python Virtual Environment is ready
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Export variables for Python/Bash scripts
export SMECHOS_TARGET="$TARGET_MOUNT"
export SMECH_TARGET="$TARGET_MOUNT"

# Read manifest and execute each script in order
while read -r script; do
    # Skip comments and empty lines
    [[ "$script" =~ ^#.*$ ]] || [[ -z "$script" ]] && continue
    
    # Strip carriage returns if present
    script=$(echo "$script" | tr -d '\r')
    
    full_path="$ROOT_DIR/$script"
    if [ ! -f "$full_path" ]; then
        echo "Error: script $script not found at $full_path"
        exit 1
    fi
    
    # Phase 1b scripts operate directly on part2.img via debugfs and need
    # TARGET_MOUNT UNMOUNTED.
    if [[ "$script" == *deploy_openrc* ]] || [[ "$script" == *edit_inittab* ]] || [[ "$script" == *write_unreadable* ]]; then
        if mountpoint -q "$TARGET_MOUNT"; then
            echo "[*] Unmounting $TARGET_MOUNT for safe debugfs execution..."
            sudo umount -R "$TARGET_MOUNT" || true
        fi
    fi

    # Phase 1 (musl/userland/etc-skeleton bootstrap) and Phase 2 (compile/
    # configure/copy/patch) scripts all install directly into the mounted
    # target via DESTDIR or plain file writes, so TARGET_MOUNT must be MOUNTED.
    if [[ "$script" == *bootstrap* ]] || [[ "$script" == *write_etc_skeleton* ]] || [[ "$script" == *compile* ]] || [[ "$script" == *configure* ]] || [[ "$script" == *copy* ]] || [[ "$script" == *patch* ]]; then
        if ! mountpoint -q "$TARGET_MOUNT"; then
            echo "[*] SmechOS target is not mounted. Attempting to mount..."
            if [ -b "/dev/nbd1p2" ]; then
                sudo mount /dev/nbd1p2 "$TARGET_MOUNT"
                if [ -b "/dev/nbd1p1" ]; then
                    sudo mkdir -p "$TARGET_MOUNT/boot"
                    sudo mount /dev/nbd1p1 "$TARGET_MOUNT/boot"
                fi
            elif [ -b "/dev/nbd0p2" ]; then
                sudo mount /dev/nbd0p2 "$TARGET_MOUNT"
                if [ -b "/dev/nbd0p1" ]; then
                    sudo mkdir -p "$TARGET_MOUNT/boot"
                    sudo mount /dev/nbd0p1 "$TARGET_MOUNT/boot"
                fi
            else
                echo "Error: Target is not mounted and no NBD device found to mount it."
                exit 1
            fi
        fi
    fi

    echo "--------------------------------------------------"
    echo "Executing: $script"
    echo "--------------------------------------------------"

    # Run script based on extension
    if [[ "$script" == *.py ]]; then
        python3 "$full_path"
    elif [[ "$script" == *.sh ]]; then
        bash "$full_path"
    else
        echo "Error: Unknown script type for $script"
        exit 1
    fi
done < "$MANIFEST"

# Clean up mounts at the end of the run
if mountpoint -q "$TARGET_MOUNT"; then
    echo "[*] Final build step: unmounting target filesystem..."
    sudo umount -R "$TARGET_MOUNT" || true
fi

echo "--- Build Complete ---"
