import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")
host_bin_dir = "/mnt/kaymium_sovereign/usr/bin"

# 1. Get files in image /usr/bin
print("[+] Reading image /usr/bin files...")
debugfs_bin = subprocess.check_output(["debugfs", "-R", "ls /usr/bin", image_path], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
img_bin_files = set()
for line in debugfs_bin.split("\n"):
    parts = line.strip().split()
    for p in parts:
        if "(" in p and ")" in p: continue
        if p and not p.isdigit() and p not in [".", "..", "lost+found"]:
            img_bin_files.add(p)

# 2. Get files in image /usr/sbin
print("[+] Reading image /usr/sbin files...")
debugfs_sbin = subprocess.check_output(["debugfs", "-R", "ls /usr/sbin", image_path], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
img_sbin_files = set()
for line in debugfs_sbin.split("\n"):
    parts = line.strip().split()
    for p in parts:
        if "(" in p and ")" in p: continue
        if p and not p.isdigit() and p not in [".", "..", "lost+found"]:
            img_sbin_files.add(p)

print(f"[+] Image usr/bin: {len(img_bin_files)} files. usr/sbin: {len(img_sbin_files)} files.")

# 3. Create a temporary folder on the host to dump files if we need to copy sbin files to bin
cmds = []
dump_temp_dir = tempfile.mkdtemp()

for f in img_sbin_files:
    if f not in img_bin_files:
        print(f"[-] Migrating {f} from usr/sbin to usr/bin...")
        host_temp_path = os.path.join(dump_temp_dir, f)
        cmds.append(f"dump /usr/sbin/{f} {host_temp_path}")
        cmds.append(f"write {host_temp_path} /usr/bin/{f}")

# 4. Now we delete all files in /usr/sbin and then the directory itself, then create a symlink /usr/sbin -> bin
for f in img_sbin_files:
    cmds.append(f"rm /usr/sbin/{f}")
cmds.append("rmdir /usr/sbin")
cmds.append("symlink /usr/sbin bin")

# 5. Now we copy all missing files from host /mnt/kaymium_sovereign/usr/bin into /usr/bin in the image
host_files = set(os.listdir(host_bin_dir))
missing_binaries = host_files - img_bin_files

print(f"[+] Found {len(missing_binaries)} missing binaries to restore.")
for f in sorted(list(missing_binaries)):
    host_path = os.path.join(host_bin_dir, f)
    if os.path.islink(host_path):
        # If it is a symlink on the host, we can replicate it in the image!
        target = os.readlink(host_path)
        cmds.append(f"symlink /usr/bin/{f} {target}")
    elif os.path.isfile(host_path):
        cmds.append(f"write {host_path} /usr/bin/{f}")

# 6. Write all debugfs commands to a temporary file
cmd_file_path = os.path.join(dump_temp_dir, "debugfs_cmds.txt")
with open(cmd_file_path, "w") as f:
    for cmd in cmds:
        f.write(cmd + "\n")

print(f"[+] Generated {len(cmds)} debugfs commands.")
print("[+] Running debugfs to execute commands... This may take a moment...")

# Run debugfs
proc = subprocess.Popen(["debugfs", "-w", "-f", cmd_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()

print("[+] debugfs output:")
print(stdout.decode("utf-8", errors="ignore")[:1000])
if stderr:
    print("[!] debugfs errors:")
    print(stderr.decode("utf-8", errors="ignore")[:1000])

print("[+] Clean up...")
# Clean up temp files
for root, dirs, files in os.walk(dump_temp_dir, topdown=False):
    for name in files:
        os.remove(os.path.join(root, name))
    for name in dirs:
        os.rmdir(os.path.join(root, name))
os.rmdir(dump_temp_dir)

print("[+] Restoration script finished!")
