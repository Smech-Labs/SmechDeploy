#!/usr/bin/env python3
import os
import shutil

SMECH_TARGET = "/mnt/smechos_build_root"

# Source -> Destination mappings
copies = [
    # 1. Headers
    ("/usr/include/libinput.h", f"{SMECH_TARGET}/usr/include/libinput.h"),
    ("/usr/include/epoxy", f"{SMECH_TARGET}/usr/include/epoxy"),
    ("/usr/include/libxcvt", f"{SMECH_TARGET}/usr/include/libxcvt"),
    
    # 2. Pkgconfig files
    ("/usr/lib/x86_64-linux-gnu/pkgconfig/libinput.pc", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/libinput.pc"),
    ("/usr/lib/x86_64-linux-gnu/pkgconfig/epoxy.pc", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/epoxy.pc"),
    ("/usr/lib/x86_64-linux-gnu/pkgconfig/libxcvt.pc", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/libxcvt.pc"),
    
    # 3. Libxcvt shared library actual file
    ("/usr/lib/x86_64-linux-gnu/libxcvt.so.0.1.2", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/libxcvt.so.0.1.2"),
    ("/usr/lib/x86_64-linux-gnu/libxcvt.so.0.1.2", f"{SMECH_TARGET}/usr/lib/libxcvt.so.0.1.2"),
]

# Run copy operations
for src, dst in copies:
    print(f"[+] Copying {src} -> {dst}...")
    if os.path.isdir(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    elif os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copy2(src, dst, follow_symlinks=False)

# Development symlinks and library symlinks to copy/create
symlinks_to_create = [
    # (Symlink Path, Target)
    # libinput
    (f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/libinput.so", "libinput.so.10"),
    (f"{SMECH_TARGET}/usr/lib/libinput.so", "libinput.so.10"),
    
    # libepoxy
    (f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/libepoxy.so", "libepoxy.so.0"),
    (f"{SMECH_TARGET}/usr/lib/libepoxy.so", "libepoxy.so.0"),
    
    # libxcvt
    (f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/libxcvt.so.0", "libxcvt.so.0.1.2"),
    (f"{SMECH_TARGET}/usr/lib/libxcvt.so.0", "libxcvt.so.0.1.2"),
    (f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/libxcvt.so", "libxcvt.so.0"),
    (f"{SMECH_TARGET}/usr/lib/libxcvt.so", "libxcvt.so.0"),
]

for sym_path, target in symlinks_to_create:
    os.makedirs(os.path.dirname(sym_path), exist_ok=True)
    if os.path.exists(sym_path) or os.path.islink(sym_path):
        os.remove(sym_path)
    print(f"[+] Creating symlink {sym_path} -> {target}")
    os.symlink(target, sym_path)

# Ensure pkgconfig folder flat under /usr/lib also gets a copy of pc files
for pc_name in ["libinput.pc", "epoxy.pc", "libxcvt.pc"]:
    src_pc = f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/{pc_name}"
    dst_pc1 = f"{SMECH_TARGET}/usr/lib/pkgconfig/{pc_name}"
    dst_pc2 = f"{SMECH_TARGET}/usr/share/pkgconfig/{pc_name}"
    
    for dst_pc in [dst_pc1, dst_pc2]:
        os.makedirs(os.path.dirname(dst_pc), exist_ok=True)
        if os.path.exists(dst_pc):
            os.remove(dst_pc)
        print(f"[+] Copying {src_pc} -> {dst_pc}")
        shutil.copy2(src_pc, dst_pc)

print("[+] All kwin dependencies successfully bootstrapped and configured!")
