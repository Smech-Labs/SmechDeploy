import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")
host_lib_dir = "/mnt/kaymium_sovereign/usr/lib64"

print("[+] Scanning host /mnt/kaymium_sovereign/usr/lib64 recursively...")
host_items = []

def scan_dir(dir_path):
    try:
        entries = list(os.scandir(dir_path))
    except PermissionError:
        return
    for entry in entries:
        rel_path = os.path.relpath(entry.path, host_lib_dir).replace("\\", "/")
        if entry.is_symlink():
            host_items.append({"rel_path": rel_path, "type": "link", "target": os.readlink(entry.path), "path": entry.path})
        elif entry.is_dir():
            host_items.append({"rel_path": rel_path, "type": "dir", "path": entry.path})
            scan_dir(entry.path)
        elif entry.is_file():
            host_items.append({"rel_path": rel_path, "type": "file", "path": entry.path})

scan_dir(host_lib_dir)
print(f"[+] Found {len(host_items)} items in host usr/lib64.")

# 1. Create usr/lib64 directory in image first
cmds = ["mkdir /usr/lib64"]

# 2. Add subdirectories
dirs = [item for item in host_items if item["type"] == "dir"]
dirs.sort(key=lambda x: x["rel_path"].count("/"))
for item in dirs:
    cmds.append(f"mkdir /usr/lib64/{item['rel_path']}")

# 3. Add symlinks and files
other_items = [item for item in host_items if item["type"] != "dir"]
for item in other_items:
    if item["type"] == "link":
        cmds.append(f"symlink /usr/lib64/{item['rel_path']} {item['target']}")
    elif item["type"] == "file":
        cmds.append(f"write {item['path']} /usr/lib64/{item['rel_path']}")

# 4. Now modify root symlink /lib64 to point to usr/lib64!
# (Wait, first delete old /lib64 which is a symlink pointing to usr/lib)
cmds.append("rm /lib64")
cmds.append("symlink /lib64 usr/lib64")

# Also let's check /usr/lib/ld-linux-x86-64.so.2 and modify it to point to /usr/lib64/ld-linux-x86-64.so.2!
cmds.append("rm /usr/lib/ld-linux-x86-64.so.2")
cmds.append("symlink /usr/lib/ld-linux-x86-64.so.2 /usr/lib64/ld-linux-x86-64.so.2")

print(f"[+] Generated {len(cmds)} commands to restore lib64. Writing to temp file...")

dump_temp_dir = tempfile.mkdtemp()
cmd_file_path = os.path.join(dump_temp_dir, "lib64_cmds.txt")
with open(cmd_file_path, "w") as f:
    for cmd in cmds:
        f.write(cmd + "\n")

print("[+] Running debugfs to execute commands... This may take 1-2 minutes...")
proc = subprocess.Popen(["debugfs", "-w", "-f", cmd_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()

print("[+] debugfs completed!")
print("[+] debugfs stdout (first 500 chars):")
print(stdout.decode("utf-8", errors="ignore")[:500])
if stderr:
    print("[!] debugfs stderr (first 500 chars):")
    print(stderr.decode("utf-8", errors="ignore")[:500])

# Clean up
os.remove(cmd_file_path)
os.rmdir(dump_temp_dir)

print("[+] Done!")
