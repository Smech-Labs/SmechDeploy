"""
SmechOS independent userland bootstrap -- Stage 3 (see MUSL_BOOTSTRAP_PLAN.md)

Writes a small, hand-authored /etc skeleton directly into the mounted target
($SMECH_TARGET, e.g. /mnt/smechos), replacing restore_etc.py's behavior of
copying /etc wholesale out of /mnt/kaymium_sovereign. Unlike Stages 0-2,
/etc content isn't really a "compile from source" problem -- it's small,
static configuration that should just be authored once and version-controlled
here, rather than borrowed from whatever happens to be on the build host.

Wired into build_order.txt as the third Phase 1 step. Runs in the same
mounted phase as 10_bootstrap_musl.sh/11_bootstrap_userland_musl.sh -- plain
file writes, no debugfs needed, since the target filesystem is already
mounted and writable at this point in the build sequence. Not yet test-run --
see MUSL_BOOTSTRAP_PLAN.md.
"""

import os

SMECH_TARGET = os.environ.get("SMECH_TARGET", "/mnt/smechos")

# Each entry is (path under /etc, file content). Kept intentionally minimal --
# only what a musl+GNU-userland base system actually needs to boot and let a
# user log in. Packages installed later (KDE, etc.) bring their own /etc
# fragments via their own install steps, same as on any distro.
ETC_FILES = {
    "passwd": (
        "root:x:0:0:root:/root:/bin/bash\n"
    ),
    "group": (
        "root:x:0:\n"
    ),
    "shadow": (
        # Locked root account by default -- root_pw/first-boot setup is
        # expected to set a real password, not ship one in version control.
        "root:!:::::::\n"
    ),
    "hostname": (
        "smechos\n"
    ),
    "hosts": (
        "127.0.0.1\tlocalhost\n"
        "::1\t\tlocalhost\n"
        "127.0.1.1\tsmechos\n"
    ),
    "fstab": (
        "# <file system> <mount point> <type> <options> <dump> <pass>\n"
        "# Populated by the installer at install time -- this is a template.\n"
    ),
    "profile": (
        "export PATH=/usr/bin:/usr/sbin\n"
        "export PS1='\\u@\\h:\\w\\$ '\n"
    ),
    "nsswitch.conf": (
        # musl's resolver doesn't use NSS the way glibc does, but keep a
        # minimal sane default in case any compiled package still consults
        # this file expecting glibc-style behavior.
        "passwd: files\n"
        "group: files\n"
        "shadow: files\n"
        "hosts: files dns\n"
    ),
}


def main():
    etc_dir = os.path.join(SMECH_TARGET, "etc")
    if not os.path.isdir(etc_dir):
        raise SystemExit(
            f"Error: {etc_dir} does not exist -- is $SMECH_TARGET ({SMECH_TARGET}) "
            "actually mounted?"
        )

    written = 0
    for rel_path, content in ETC_FILES.items():
        dest_path = os.path.join(etc_dir, rel_path)
        with open(dest_path, "w") as f:
            f.write(content)
        os.chmod(dest_path, 0o600 if rel_path == "shadow" else 0o644)
        written += 1

    print(f"[+] Wrote {written} hand-authored /etc files into {etc_dir}")
    print("[+] STAGE 3 COMPLETE -- /etc skeleton written")


if __name__ == "__main__":
    main()
