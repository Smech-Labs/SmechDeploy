import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")
host_etc_dir = "/mnt/kaymium_sovereign/etc"

print("[+] Scanning host /mnt/kaymium_sovereign/etc recursively...")

host_items = []  # list of dict: {"rel_path": ..., "type": "dir"|"file"|"link", "target": ...}

def scan_dir(dir_path):
    try:
        entries = list(os.scandir(dir_path))
    except PermissionError:
        # If we cannot read the directory, we still record the directory itself
        # but we cannot scan its children.
        return
    
    for entry in entries:
        rel_path = os.path.relpath(entry.path, host_etc_dir).replace("\\", "/")
        if entry.is_symlink():
            target = os.readlink(entry.path)
            host_items.append({"rel_path": rel_path, "type": "link", "target": target, "path": entry.path})
        elif entry.is_dir():
            host_items.append({"rel_path": rel_path, "type": "dir", "path": entry.path})
            scan_dir(entry.path)
        elif entry.is_file():
            host_items.append({"rel_path": rel_path, "type": "file", "path": entry.path})

# Start recursive scanning
scan_dir(host_etc_dir)

# Add any directories that might have been skipped due to permission errors on scanning their parent but we found them listed in a scan
# Wait, os.scandir listing itself will include restricted folders!
# Let us verify if there are folders we know of but need to explicitly add if we couldn't list them.
# The parent os.scandir(host_etc_dir) will return ssl, ssh, polkit-1 which are directories,
# and they are added as "dir" and scan_dir(entry.path) will raise PermissionError and return immediately.
# So those directories are successfully recorded!

print(f"[+] Found {len(host_items)} total items on host /etc.")

# 2. Query target image to see which ones are missing using a batch of stat commands
print("[+] Generating stat commands for debugfs...")
stat_cmds = []
for item in host_items:
    stat_cmds.append(f"stat /etc/{item['rel_path']}")

# Write stat commands to a temp file
dump_temp_dir = tempfile.mkdtemp()
stat_file_path = os.path.join(dump_temp_dir, "stat_cmds.txt")
with open(stat_file_path, "w") as f:
    for cmd in stat_cmds:
        f.write(cmd + "\n")

print("[+] Running debugfs to check existence of paths...")
proc = subprocess.Popen(["debugfs", "-f", stat_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
stdout, _ = proc.communicate()
stdout_lines = stdout.decode("utf-8", errors="ignore").split("\n")

# Process the output to determine missing files
# Debugfs output prints "debugfs: stat /etc/..." followed by either info or "File not found"
missing_items = []
current_item_index = 0

# We can match the output line-by-line with the host_items
# Let us search for "File not found" or "ext2_lookup" in the output for each item.
# To make it perfectly robust, we can parse the output sequentially.
# For each "debugfs: stat /etc/..." we look at the next line. If it contains "File not found" or "lookup", it is missing!
output_iter = iter(stdout_lines)
for item in host_items:
    # Find the corresponding debugfs command output
    found_stat = False
    for line in output_iter:
        if line.startswith("debugfs: stat"):
            found_stat = True
            break
    if not found_stat:
        # If we reached the end of output, assume missing
        missing_items.append(item)
        continue
    
    # Check the next line
    try:
        next_line = next(output_iter)
        if "not found" in next_line or "lookup" in next_line:
            missing_items.append(item)
    except StopIteration:
        missing_items.append(item)

print(f"[+] Found {len(missing_items)} missing items in the target /etc.")

# 3. Generate debugfs mkdir, symlink, and write commands
cmds = []
# Ensure directories are created first (sorted by length or hierarchy)
dirs_to_create = [item for item in missing_items if item["type"] == "dir"]
dirs_to_create.sort(key=lambda x: x["rel_path"].count("/"))

for item in dirs_to_create:
    cmds.append(f"mkdir /etc/{item['rel_path']}")

# Now generate write and symlink commands
other_items = [item for item in missing_items if item["type"] != "dir"]
for item in other_items:
    if item["type"] == "link":
        cmds.append(f"symlink /etc/{item['rel_path']} {item['target']}")
    elif item["type"] == "file":
        cmds.append(f"write {item['path']} /etc/{item['rel_path']}")

print(f"[+] Generated {len(cmds)} commands to restore missing items.")

if len(cmds) > 0:
    cmd_file_path = os.path.join(dump_temp_dir, "restore_cmds.txt")
    with open(cmd_file_path, "w") as f:
        for cmd in cmds:
            f.write(cmd + "\n")
            
    print("[+] Running debugfs to restore missing items... This may take a moment...")
    proc = subprocess.Popen(["debugfs", "-w", "-f", cmd_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    
    print("[+] Restoration output (first 1000 chars):")
    print(stdout.decode("utf-8", errors="ignore")[:1000])
    if stderr:
        print("[!] Restoration errors (first 1000 chars):")
        print(stderr.decode("utf-8", errors="ignore")[:1000])
else:
    print("[+] No missing items to restore!")

# Clean up
for root, dirs, files in os.walk(dump_temp_dir, topdown=False):
    for name in files:
        os.remove(os.path.join(root, name))
    for name in dirs:
        os.rmdir(os.path.join(root, name))
os.rmdir(dump_temp_dir)

print("[+] Done!")
