import os
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
image_path = os.path.join(DEPLOY_ROOT, "images", "part2.img")

# Create a temp directory on host
temp_dir = tempfile.mkdtemp()

# 1. Create gshadow based on group file from image
print("[+] Generating /etc/gshadow...")
try:
    # Read group file from image
    group_content = subprocess.check_output(["debugfs", "-R", "cat /etc/group", image_path], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
    gshadow_lines = []
    for line in group_content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split(":")
            if parts:
                gshadow_lines.append(f"{parts[0]}:::")
    gshadow_content = "\n".join(gshadow_lines) + "\n"
except Exception as e:
    print("[!] Failed to parse image /etc/group, using default gshadow.", e)
    gshadow_content = "root:::\nbin:::\ndaemon:::\nsys:::\nadm:::\ntty:::\ndisk:::\nlp:::\nmem:::\nkmem:::\nwheel:::\nfloppy:::\nmail:::\nnews:::\nuucp:::\nsyslog:::\naudio:::\ncdrom:::\ndialout:::\ntape:::\nvideo:::\ncron:::\ngentoo:::\n"

# 2. Define other configs
sshd_config = """# SmechOS sshd_config
Port 22
PermitRootLogin yes
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp /usr/libexec/sftp-server
UsePAM yes
"""

useradd = """# SmechOS useradd defaults
GROUP=100
HOME=/home
INACTIVE=-1
EXPIRE=
SHELL=/bin/bash
SKEL=/etc/skel
CREATE_MAIL_SPOOL=no
"""

cupsd_config = """# SmechOS cupsd.conf
LogLevel info
MaxLogSize 0
Port 631
Listen /run/cups/cups.sock
<Location />
  Order allow,deny
</Location>
<Location /admin>
  Order allow,deny
</Location>
"""

cups_files = """# SmechOS cups-files.conf
SystemGroup wheel
"""

snmp_config = """# SmechOS snmp.conf
"""

configs = {
    "gshadow": gshadow_content,
    "ssh/sshd_config": sshd_config,
    "default/useradd": useradd,
    "cups/cupsd.conf": cupsd_config,
    "cups/cups-files.conf": cups_files,
    "cups/cups-files.conf.default": cups_files,
    "cups/snmp.conf": snmp_config,
    "cups/snmp.conf.default": snmp_config
}

cmds = []
for rel_path, content in configs.items():
    host_path = os.path.join(temp_dir, os.path.basename(rel_path))
    with open(host_path, "w") as f:
        f.write(content)
    
    # We must ensure parent directories exist in the image!
    # Parents like /etc/ssh, /etc/default, /etc/cups should already exist, but let's double check or mkdir them just in case.
    # Note: mkdir will print an error if they exist, which is fine to ignore.
    parent = os.path.dirname(os.path.join("/etc", rel_path)).replace("\\", "/")
    cmds.append(f"mkdir {parent}")
    cmds.append(f"write {host_path} /etc/{rel_path}")

# Run debugfs
cmd_file_path = os.path.join(temp_dir, "write_cmds.txt")
with open(cmd_file_path, "w") as f:
    for cmd in cmds:
        f.write(cmd + "\n")

print("[+] Running debugfs to write missing configurations...")
proc = subprocess.Popen(["debugfs", "-w", "-f", cmd_file_path, image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate()

print("[+] Output:")
print(stdout.decode("utf-8", errors="ignore"))
if stderr:
    print("[!] Errors:")
    print(stderr.decode("utf-8", errors="ignore"))

# Clean up
for f in os.listdir(temp_dir):
    os.remove(os.path.join(temp_dir, f))
os.rmdir(temp_dir)

print("[+] Unreadable etc items restored successfully!")
