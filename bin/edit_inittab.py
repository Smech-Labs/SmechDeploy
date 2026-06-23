import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")
master_image_path = os.path.join(DEPLOY_ROOT, "images", "smechos.img")
tmp_inittab = "/tmp/smechos_inittab_edit"

print("[+] Modifying /etc/inittab to enable serial console (ttyS0)...")

# Dump /etc/inittab from image
subprocess.check_call(["debugfs", "-R", f"dump /etc/inittab {tmp_inittab}", image_path])

# Read and modify contents
with open(tmp_inittab, "r") as f:
    lines = f.readlines()

new_lines = []
modified = False
for line in lines:
    if "ttyS0" in line and line.strip().startswith("#s0:"):
        print("    -> Found ttyS0 line, uncommenting...")
        line = line.replace("#s0:", "s0:")
        modified = True
    new_lines.append(line)

if not modified:
    print("[!] Warning: Could not find commented ttyS0 line in inittab!")
else:
    # Write back modified inittab
    with open(tmp_inittab, "w") as f:
        f.writelines(new_lines)
        
    # Write inittab to image
    subprocess.check_call(["debugfs", "-w", "-R", f"rm /etc/inittab", image_path])
    subprocess.check_call(["debugfs", "-w", "-R", f"write {tmp_inittab} /etc/inittab", image_path])
    subprocess.check_call(["debugfs", "-w", "-R", f"sif /etc/inittab mode 0100644", image_path])
    print("[+] Successfully wrote modified /etc/inittab to SmechOS image!")

    # Sync back to master image
    print("[+] Synchronizing part2.img back to master image...")
    dd_cmd = ["dd", f"if={image_path}", f"of={master_image_path}", "bs=1M", "seek=1025", "count=19454", "conv=notrunc"]
    subprocess.check_call(dd_cmd)
    print("[+] Sync complete!")

# Clean up
if os.path.exists(tmp_inittab):
    os.remove(tmp_inittab)
