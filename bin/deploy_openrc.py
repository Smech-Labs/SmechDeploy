import os
import subprocess
import tempfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")
master_image_path = os.path.join(DEPLOY_ROOT, "images", "smechos.img")
openrc_install_dir = os.path.join(DEPLOY_ROOT, "deps", "others", "openrc_install")
host_dash_path = "/usr/bin/dash"

print("[+] Starting SmechOS OpenRC & Dash Deployment Script...")

# Temporary folder for debugfs command file
temp_dir = tempfile.mkdtemp()
cmd_file_path = os.path.join(temp_dir, "deploy_cmds.txt")
print(f"[+] Created temporary folder: {temp_dir}")

debugfs_cmds = []

# List to store directory creations, file writes, and symlink creations
dirs_to_create = set()
files_to_write = []  # tuple: (host_path, image_path, mode)
symlinks_to_create = []  # tuple: (link_path, target_path)

# Map host openrc_install path to image path
def map_path(host_path):
    rel_path = os.path.relpath(host_path, openrc_install_dir)
    # Normalize paths with forward slashes
    parts = rel_path.split(os.sep)
    
    if parts[0] == "bin":
        # /bin -> /usr/bin
        parts[0] = "usr/bin"
    elif parts[0] == "sbin":
        # /sbin -> /usr/sbin
        parts[0] = "usr/sbin"
    elif parts[0] == "lib":
        # /lib -> /usr/lib
        parts[0] = "usr/lib"
    elif parts[0] == "usr":
        pass # Keep as usr/...
    elif parts[0] == "etc":
        pass # Keep as etc/...
    else:
        # Fallback
        pass
        
    return "/" + "/".join(parts)

# 1. Traverse /tmp/openrc_install and catalog all items
print("[+] Scanning compiled OpenRC installation files...")
for root, dirs, files in os.walk(openrc_install_dir):
    for d in dirs:
        host_path = os.path.join(root, d)
        img_path = map_path(host_path)
        dirs_to_create.add(img_path)
        
    for f in files:
        host_path = os.path.join(root, f)
        img_path = map_path(host_path)
        
        if os.path.islink(host_path):
            target = os.readlink(host_path)
            symlinks_to_create.append((img_path, target))
        elif os.path.isfile(host_path):
            st_mode = os.stat(host_path).st_mode
            files_to_write.append((host_path, img_path, st_mode))

# 2. Add dash to the list of files to copy from the host
if os.path.exists(host_dash_path):
    print(f"[+] Found host dash shell at {host_dash_path}. Queueing deployment to SmechOS /usr/bin/dash...")
    files_to_write.append((host_dash_path, "/usr/bin/dash", 0o100755))
else:
    print("[!] Warning: Host dash shell not found at /usr/bin/dash!")

# 3. Generate debugfs commands
# We sort directories by depth (length of path parts) to ensure parents are created before children
sorted_dirs = sorted(list(dirs_to_create), key=lambda x: len(x.split("/")))

print("[+] Generating debugfs commands...")

# Directory commands
for d in sorted_dirs:
    # Try to create dir (errors if it exists are safe to ignore, but we'll issue the command)
    debugfs_cmds.append(f"mkdir {d}")

# Symlink commands
for link_path, target in symlinks_to_create:
    debugfs_cmds.append(f"rm {link_path}")
    debugfs_cmds.append(f"symlink {link_path} {target}")

# File commands
for host_path, img_path, mode in files_to_write:
    # Format octal permissions
    mode_str = '0%o' % (mode & 0xFFFF)
    debugfs_cmds.append(f"rm {img_path}")
    debugfs_cmds.append(f"write {host_path} {img_path}")
    debugfs_cmds.append(f"sif {img_path} mode {mode_str}")

print(f"[+] Total debugfs commands generated: {len(debugfs_cmds)}")

# Write to commands file
with open(cmd_file_path, "w") as f:
    for cmd in debugfs_cmds:
        f.write(cmd + "\n")

# Run debugfs
print("[+] Executing debugfs to apply changes to part2.img...")
proc = subprocess.Popen(["debugfs", "-w", "-f", cmd_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()

print("[+] debugfs stdout (first 500 chars):")
print(stdout.decode("utf-8", errors="ignore")[:500])

if stderr:
    print("[!] debugfs stderr (first 500 chars):")
    print(stderr.decode("utf-8", errors="ignore")[:500])

# Synchronize back to master image
print("[+] Synchronizing restored part2.img partition back to master image (smechos.img)...")
dd_cmd = ["dd", f"if={image_path}", f"of={master_image_path}", "bs=1M", "seek=1025", "count=19454", "conv=notrunc"]
print(f"    -> Running: {' '.join(dd_cmd)}")
subprocess.check_call(dd_cmd)
print("[+] Synchronization complete!")

# Clean up
shutil.rmtree(temp_dir)
print("[+] Deployment completed successfully!")
