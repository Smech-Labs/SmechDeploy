#!/usr/bin/env python3
import os
import shutil

SMECH_TARGET = "/mnt/smechos_build_root"

# List of simple folder copy tasks (Source on host -> Destination under SMECH_TARGET)
copies = [
    # --- 1. Qt6UiTools ---
    # Headers
    ("/usr/include/x86_64-linux-gnu/qt6/QtUiTools", f"{SMECH_TARGET}/usr/include/x86_64-linux-gnu/qt6/QtUiTools"),
    ("/usr/include/x86_64-linux-gnu/qt6/QtUiTools", f"{SMECH_TARGET}/usr/include/QtUiTools"),
    # CMake configs
    ("/usr/lib/x86_64-linux-gnu/cmake/Qt6UiTools", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/cmake/Qt6UiTools"),
    ("/usr/lib/x86_64-linux-gnu/cmake/Qt6UiTools", f"{SMECH_TARGET}/usr/lib/cmake/Qt6UiTools"),
    # Metatypes
    ("/usr/lib/x86_64-linux-gnu/metatypes", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/metatypes"),
    # Share files
    ("/usr/share/qt6/modules/UiTools.json", f"{SMECH_TARGET}/usr/share/qt6/modules/UiTools.json"),
    # Pkgconfig
    ("/usr/lib/x86_64-linux-gnu/pkgconfig/Qt6UiTools.pc", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/Qt6UiTools.pc"),

    # --- 2. Qt6UiPlugin ---
    # Headers
    ("/usr/include/x86_64-linux-gnu/qt6/QtUiPlugin", f"{SMECH_TARGET}/usr/include/x86_64-linux-gnu/qt6/QtUiPlugin"),
    ("/usr/include/x86_64-linux-gnu/qt6/QtUiPlugin", f"{SMECH_TARGET}/usr/include/QtUiPlugin"),
    # CMake configs
    ("/usr/lib/x86_64-linux-gnu/cmake/Qt6UiPlugin", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/cmake/Qt6UiPlugin"),
    ("/usr/lib/x86_64-linux-gnu/cmake/Qt6UiPlugin", f"{SMECH_TARGET}/usr/lib/cmake/Qt6UiPlugin"),
    # Share files
    ("/usr/share/qt6/modules/UiPlugin.json", f"{SMECH_TARGET}/usr/share/qt6/modules/UiPlugin.json"),
    # Pkgconfig
    ("/usr/lib/x86_64-linux-gnu/pkgconfig/Qt6UiPlugin.pc", f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig/Qt6UiPlugin.pc")
]

# Copy operations
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

# Copy the libraries to both x86_64-linux-gnu and flat /usr/lib
lib_files = [
    "libQt6UiTools.so",
    "libQt6UiTools.so.6",
    "libQt6UiTools.so.6.4.2",
    "libQt6UiTools.prl"
]

for lib in lib_files:
    src_lib = os.path.join("/usr/lib/x86_64-linux-gnu", lib)
    dst_lib1 = os.path.join(f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu", lib)
    dst_lib2 = os.path.join(f"{SMECH_TARGET}/usr/lib", lib)
    
    for dst in [dst_lib1, dst_lib2]:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst) or os.path.islink(dst):
            os.remove(dst)
        # Check if it's a symlink on the host
        if os.path.islink(src_lib):
            link_target = os.readlink(src_lib)
            print(f"[+] Creating symlink {dst} -> {link_target}")
            os.symlink(link_target, dst)
        else:
            print(f"[+] Copying file {src_lib} -> {dst}")
            shutil.copy2(src_lib, dst)

# Function to patch config depth and internal path
def patch_cmake_config(module_name):
    flat_cmake_dir = f"{SMECH_TARGET}/usr/lib/cmake/{module_name}"
    
    config_file = os.path.join(flat_cmake_dir, f"{module_name}Config.cmake")
    if os.path.exists(config_file):
        print(f"[+] Patching {config_file} for 3-level depth...")
        with open(config_file, "r") as f:
            content = f.read()
        content = content.replace("get_filename_component(PACKAGE_PREFIX_DIR \"${CMAKE_CURRENT_LIST_DIR}/../../../../\" ABSOLUTE)", 
                                  "get_filename_component(PACKAGE_PREFIX_DIR \"${CMAKE_CURRENT_LIST_DIR}/../../../\" ABSOLUTE)")
        content = content.replace(f"/usr/lib/x86_64-linux-gnu/cmake/{module_name}", f"/usr/lib/cmake/{module_name}")
        with open(config_file, "w") as f:
            f.write(content)

    targets_file = os.path.join(flat_cmake_dir, f"{module_name}Targets.cmake")
    if os.path.exists(targets_file):
        print(f"[+] Patching {targets_file} for 3-level depth...")
        with open(targets_file, "r") as f:
            content = f.read()
        
        old_prefix_block = """get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)"""

        new_prefix_block = """get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)"""

        content = content.replace(old_prefix_block, new_prefix_block)
        content = content.replace(f"/usr/lib/x86_64-linux-gnu/cmake/{module_name}", f"/usr/lib/cmake/{module_name}")
        with open(targets_file, "w") as f:
            f.write(content)

# Patch both
patch_cmake_config("Qt6UiTools")
patch_cmake_config("Qt6UiPlugin")

# Patch version check strings to 6.8.2 in ConfigVersionImpl files
version_files = [
    f"{SMECH_TARGET}/usr/lib/cmake/Qt6UiTools/Qt6UiToolsConfigVersionImpl.cmake",
    f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/cmake/Qt6UiTools/Qt6UiToolsConfigVersionImpl.cmake",
    f"{SMECH_TARGET}/usr/lib/cmake/Qt6UiPlugin/Qt6UiPluginConfigVersionImpl.cmake",
    f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/cmake/Qt6UiPlugin/Qt6UiPluginConfigVersionImpl.cmake"
]

for vf in version_files:
    if os.path.exists(vf):
        print(f"[+] Patching {vf} to version 6.8.2...")
        with open(vf, "r") as f:
            content = f.read()
        content = content.replace('"6.4.2"', '"6.8.2"')
        with open(vf, "w") as f:
            f.write(content)

print("[+] Done bootstrapping Qt6UiTools and Qt6UiPlugin!")
