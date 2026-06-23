#!/usr/bin/env python3
import os
import sys
import shutil
import urllib.request
import subprocess

# Configure build paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_ROOT = os.path.dirname(SCRIPT_DIR)
SOURCES_DIR = os.path.join(DEPLOY_ROOT, "essentials", "sources")
BUILD_DIR_BASE = "/tmp/smechos_build"
SMECH_TARGET = "/mnt/smechos_build_root"

# Configure build environment
env = os.environ.copy()
env["SMECH_TARGET"] = SMECH_TARGET
env["DESTDIR"] = SMECH_TARGET
env["PATH"] = f"{env.get('PATH', '')}:{SMECH_TARGET}/usr/bin"
env["PKG_CONFIG_PATH"] = f"{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/pkgconfig:{SMECH_TARGET}/usr/share/pkgconfig:{SMECH_TARGET}/usr/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
env["CFLAGS"] = f"-I{SMECH_TARGET}/usr/include"
env["CXXFLAGS"] = f"-I{SMECH_TARGET}/usr/include"
env["LDFLAGS"] = f"-L{SMECH_TARGET}/usr/lib/x86_64-linux-gnu -L{SMECH_TARGET}/usr/lib"
env["LD_LIBRARY_PATH"] = f"{SMECH_TARGET}/usr/lib:{SMECH_TARGET}/usr/lib/x86_64-linux-gnu:{env.get('LD_LIBRARY_PATH', '')}"

# List of modules in strict build order
# Type: (name, url, check_path)
modules = [
    # 1. Third-party dependencies
    ("yaml-cpp", 
     "https://github.com/jbeder/yaml-cpp/archive/refs/tags/0.8.0.tar.gz",
     f"{SMECH_TARGET}/usr/lib/libyaml-cpp.a"),
     
    ("qcoro",
     "https://github.com/danvratil/qcoro/archive/refs/tags/v0.10.0.tar.gz",
     f"{SMECH_TARGET}/usr/lib/cmake/QCoro6/QCoro6Config.cmake"),
     
    ("polkit-qt-1",
     "https://download.kde.org/stable/polkit-qt-1/polkit-qt-1-0.200.0.tar.xz",
     f"{SMECH_TARGET}/usr/lib/cmake/PolkitQt6-1/PolkitQt6-1Config.cmake"),

    ("qca",
     "https://download.kde.org/stable/qca/2.3.10/qca-2.3.10.tar.xz",
     f"{SMECH_TARGET}/usr/lib/cmake/Qca-qt6/Qca-qt6Config.cmake"),

    # 2. KF6 Tier 1 Frameworks (No dependencies on other frameworks)
    ("karchive", "https://download.kde.org/stable/frameworks/6.22/karchive-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Archive/KF6ArchiveConfig.cmake"),
    ("kcodecs", "https://download.kde.org/stable/frameworks/6.22/kcodecs-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Codecs/KF6CodecsConfig.cmake"),
    ("kconfig", "https://download.kde.org/stable/frameworks/6.22/kconfig-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Config/KF6ConfigConfig.cmake"),
    ("kcoreaddons", "https://download.kde.org/stable/frameworks/6.22/kcoreaddons-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6CoreAddons/KF6CoreAddonsConfig.cmake"),
    ("kdbusaddons", "https://download.kde.org/stable/frameworks/6.22/kdbusaddons-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6DBusAddons/KF6DBusAddonsConfig.cmake"),
    ("kdnssd", "https://download.kde.org/stable/frameworks/6.22/kdnssd-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6DNSSD/KF6DNSSDConfig.cmake"),
    ("plasma-wayland-protocols", "https://download.kde.org/stable/plasma-wayland-protocols/plasma-wayland-protocols-1.21.0.tar.xz", f"{SMECH_TARGET}/usr/share/cmake/PlasmaWaylandProtocols/PlasmaWaylandProtocolsConfig.cmake"),
    ("kguiaddons", "https://download.kde.org/stable/frameworks/6.22/kguiaddons-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6GuiAddons/KF6GuiAddonsConfig.cmake"),
    ("ki18n", "https://download.kde.org/stable/frameworks/6.22/ki18n-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6I18n/KF6I18nConfig.cmake"),
    ("kidletime", "https://download.kde.org/stable/frameworks/6.22/kidletime-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6IdleTime/KF6IdleTimeConfig.cmake"),
    ("kitemmodels", "https://download.kde.org/stable/frameworks/6.22/kitemmodels-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6ItemModels/KF6ItemModelsConfig.cmake"),
    ("kitemviews", "https://download.kde.org/stable/frameworks/6.22/kitemviews-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6ItemViews/KF6ItemViewsConfig.cmake"),
    ("kquickcharts", "https://download.kde.org/stable/frameworks/6.22/kquickcharts-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6QuickCharts/KF6QuickChartsConfig.cmake"),
    ("kwindowsystem", "https://download.kde.org/stable/frameworks/6.22/kwindowsystem-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6WindowSystem/KF6WindowSystemConfig.cmake"),
    ("solid", "https://download.kde.org/stable/frameworks/6.22/solid-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Solid/KF6SolidConfig.cmake"),
    ("sonnet", "https://download.kde.org/stable/frameworks/6.22/sonnet-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Sonnet/KF6SonnetConfig.cmake"),
    ("threadweaver", "https://download.kde.org/stable/frameworks/6.22/threadweaver-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6ThreadWeaver/KF6ThreadWeaverConfig.cmake"),
    ("prison", "https://download.kde.org/stable/frameworks/6.22/prison-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Prison/KF6PrisonConfig.cmake"),
    ("kholidays", "https://download.kde.org/stable/frameworks/6.22/kholidays-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Holidays/KF6HolidaysConfig.cmake"),
    ("kcolorscheme", "https://download.kde.org/stable/frameworks/6.22/kcolorscheme-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6ColorScheme/KF6ColorSchemeConfig.cmake"),
    ("kwidgetsaddons", "https://download.kde.org/stable/frameworks/6.22/kwidgetsaddons-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6WidgetsAddons/KF6WidgetsAddonsConfig.cmake"),
    ("kcompletion", "https://download.kde.org/stable/frameworks/6.22/kcompletion-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Completion/KF6CompletionConfig.cmake"),
    ("attica", "https://download.kde.org/stable/frameworks/6.22/attica-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Attica/KF6AtticaConfig.cmake"),
    ("syntax-highlighting", "https://download.kde.org/stable/frameworks/6.22/syntax-highlighting-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6SyntaxHighlighting/KF6SyntaxHighlightingConfig.cmake"),

    # 3. KF6 Tier 2 Frameworks (Depend only on Tier 1)
    ("kauth", "https://download.kde.org/stable/frameworks/6.22/kauth-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Auth/KF6AuthConfig.cmake"),
    ("kcrash", "https://download.kde.org/stable/frameworks/6.22/kcrash-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Crash/KF6CrashConfig.cmake"),
    ("kpackage", "https://download.kde.org/stable/frameworks/6.22/kpackage-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Package/KF6PackageConfig.cmake"),
    ("kirigami", "https://download.kde.org/stable/frameworks/6.22/kirigami-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Kirigami/KF6KirigamiConfig.cmake"),
    ("ksvg", "https://download.kde.org/stable/frameworks/6.22/ksvg-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Svg/KF6SvgConfig.cmake"),
    ("knotifications", "https://download.kde.org/stable/frameworks/6.22/knotifications-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Notifications/KF6NotificationsConfig.cmake"),
    ("kservice", "https://download.kde.org/stable/frameworks/6.22/kservice-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Service/KF6ServiceConfig.cmake"),
    ("kjobwidgets", "https://download.kde.org/stable/frameworks/6.22/kjobwidgets-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6JobWidgets/KF6JobWidgetsConfig.cmake"),
    ("kstatusnotifieritem", "https://download.kde.org/stable/frameworks/6.22/kstatusnotifieritem-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6StatusNotifierItem/KF6StatusNotifierItemConfig.cmake"),

    # 4. KF6 Tier 3 Frameworks & Complex Libraries
    ("kconfigwidgets", "https://download.kde.org/stable/frameworks/6.22/kconfigwidgets-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6ConfigWidgets/KF6ConfigWidgetsConfig.cmake"),
    ("kglobalaccel", "https://download.kde.org/stable/frameworks/6.22/kglobalaccel-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6GlobalAccel/KF6GlobalAccelConfig.cmake"),
    ("breeze-icons", "https://download.kde.org/stable/frameworks/6.22/breeze-icons-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6BreezeIcons/KF6BreezeIconsConfig.cmake"),
    ("kiconthemes", "https://download.kde.org/stable/frameworks/6.22/kiconthemes-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6IconThemes/KF6IconThemesConfig.cmake"),
    ("kxmlgui", "https://download.kde.org/stable/frameworks/6.22/kxmlgui-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6XmlGui/KF6XmlGuiConfig.cmake"),
    ("kdeclarative", "https://download.kde.org/stable/frameworks/6.22/kdeclarative-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Declarative/KF6DeclarativeConfig.cmake"),
    ("kbookmarks", "https://download.kde.org/stable/frameworks/6.22/kbookmarks-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Bookmarks/KF6BookmarksConfig.cmake"),
    ("ktextwidgets", "https://download.kde.org/stable/frameworks/6.22/ktextwidgets-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6TextWidgets/KF6TextWidgetsConfig.cmake"),
    ("qt5compat", "https://download.qt.io/official_releases/qt/6.8/6.8.2/submodules/qt5compat-everywhere-src-6.8.2.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/Qt6Core5Compat/Qt6Core5CompatConfig.cmake"),
    ("kio", "https://download.kde.org/stable/frameworks/6.22/kio-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6KIO/KF6KIOConfig.cmake"),
    ("kcmutils", "https://download.kde.org/stable/frameworks/6.22/kcmutils-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6KCMUtils/KF6KCMUtilsConfig.cmake"),
    ("kparts", "https://download.kde.org/stable/frameworks/6.22/kparts-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Parts/KF6PartsConfig.cmake"),
    ("knotifyconfig", "https://download.kde.org/stable/frameworks/6.22/knotifyconfig-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6NotifyConfig/KF6NotifyConfigConfig.cmake"),
    ("krunner", "https://download.kde.org/stable/frameworks/6.22/krunner-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Runner/KF6RunnerConfig.cmake"),
    ("knewstuff", "https://download.kde.org/stable/frameworks/6.22/knewstuff-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6NewStuff/KF6NewStuffConfig.cmake"),
    ("kded", "https://download.kde.org/stable/frameworks/6.22/kded-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6KDED/KF6KDEDConfig.cmake"),
    ("kwallet", "https://download.kde.org/stable/frameworks/6.22/kwallet-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Wallet/KF6WalletConfig.cmake"),
    ("ktexteditor", "https://download.kde.org/stable/frameworks/6.22/ktexteditor-6.22.0.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6TextEditor/KF6TextEditorConfig.cmake"),

    # 5. Plasma Core Submodules (Version 6.6.5)
    ("libkscreen", "https://download.kde.org/stable/plasma/6.6.5/libkscreen-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KF6Screen/KF6ScreenConfig.cmake"),
    ("kwayland", "https://download.kde.org/stable/plasma/6.6.5/kwayland-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KWayland/KWaylandConfig.cmake"),
    ("layer-shell-qt", "https://download.kde.org/stable/plasma/6.6.5/layer-shell-qt-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/LayerShellQt/LayerShellQtConfig.cmake"),
    ("plasma-activities", "https://download.kde.org/stable/plasma/6.6.5/plasma-activities-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/PlasmaActivities/PlasmaActivitiesConfig.cmake"),
    ("plasma-activities-stats", "https://download.kde.org/stable/plasma/6.6.5/plasma-activities-stats-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/PlasmaActivitiesStats/PlasmaActivitiesStatsConfig.cmake"),
    ("libplasma", "https://download.kde.org/stable/plasma/6.6.5/libplasma-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/Plasma/PlasmaConfig.cmake"),
    ("libksysguard", "https://download.kde.org/stable/plasma/6.6.5/libksysguard-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KSysGuard/KSysGuardConfig.cmake"),
    ("kdecoration", "https://download.kde.org/stable/plasma/6.6.5/kdecoration-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KDecoration3/KDecoration3Config.cmake"),
    ("kglobalacceld", "https://download.kde.org/stable/plasma/6.6.5/kglobalacceld-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KGlobalAccelD/KGlobalAccelDConfig.cmake"),
    ("knighttime", "https://download.kde.org/stable/plasma/6.6.5/knighttime-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KNightTime/KNightTimeConfig.cmake"),
    ("kwin", "https://download.kde.org/stable/plasma/6.6.5/kwin-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KWinDBusInterface/KWinDBusInterfaceConfig.cmake"),

    # 6. Partition Management & Calamares Installer
    ("kpmcore", "https://download.kde.org/stable/release-service/24.12.3/src/kpmcore-24.12.3.tar.xz", f"{SMECH_TARGET}/usr/lib/cmake/KPMcore/KPMcoreConfig.cmake"),
    ("calamares", "https://github.com/calamares/calamares/archive/refs/tags/v3.3.6.tar.gz", f"{SMECH_TARGET}/usr/bin/calamares"),
    ("sddm", "https://github.com/sddm/sddm/archive/refs/tags/v0.21.0.tar.gz", f"{SMECH_TARGET}/usr/bin/sddm"),

    # 7. Desktop Environment Shell
    ("plasma-workspace", "https://download.kde.org/stable/plasma/6.6.5/plasma-workspace-6.6.5.tar.xz", f"{SMECH_TARGET}/usr/bin/plasmawayland-session")
]

os.makedirs(SOURCES_DIR, exist_ok=True)

# Clean old KF6 6.6.0 cmake configs to force rebuild with KF6 6.22.0
import glob
for cmake_dir in glob.glob(f"{SMECH_TARGET}/usr/lib/*/cmake/KF6*"):
    try:
        shutil.rmtree(cmake_dir)
        print(f"[CLEAN] Removed {cmake_dir}")
    except:
        pass

for name, url, check_path in modules:
    alt_path = check_path.replace("/usr/lib/", "/usr/lib/x86_64-linux-gnu/")
    if os.path.exists(check_path) or os.path.exists(alt_path):
        print(f"[SKIP] {name} already installed.")
        continue

    print(f"\n[+] === BUILDING: {name} ===")
    
    # 1. Download source
    ext = ".tar.gz" if url.endswith(".tar.gz") else ".tar.xz"
    archive_path = os.path.join(SOURCES_DIR, f"{name}{ext}")
    
    if not os.path.exists(archive_path) or os.path.getsize(archive_path) < 1024:
        print(f"[+] Downloading {name} from {url}...")
        res = subprocess.run(["wget", "-c", "--tries=3", "--timeout=15", "-O", archive_path, url])
        if res.returncode != 0:
            print(f"[-] Failed to download {name} via wget")
            sys.exit(1)
            
    # 2. Extract source
    build_dir = os.path.join(BUILD_DIR_BASE, f"build-{name}")
    if os.path.exists(build_dir):
        print(f"[+] Found existing build directory for {name}. Performing incremental build!")
        # 4. Compile source (-j3 to protect WSL memory/prevent OOM)
        print(f"[+] Compiling {name} (incremental)...")
        build_cmd = ["cmake", "--build", "build_dir", "-j3"]
        res = subprocess.run(build_cmd, cwd=build_dir, env=env)
        if res.returncode != 0:
            print(f"[-] Build failed for {name}")
            sys.exit(1)
            
        # 5. Install source
        print(f"[+] Installing {name}...")
        install_cmd = ["cmake", "--install", "build_dir"]
        # Run with sudo and preserve env paths
        sudo_install_cmd = ["sudo", f"PATH={env['PATH']}", f"LD_LIBRARY_PATH={env['LD_LIBRARY_PATH']}", f"HOME={env['HOME']}", f"DESTDIR={SMECH_TARGET}"] + install_cmd

        proc = subprocess.Popen(sudo_install_cmd, cwd=build_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate()
        
        if proc.returncode != 0:
            print(f"[-] Installation failed for {name}")
            print("Stdout:", stdout)
            print("Stderr:", stderr)
            sys.exit(1)
            
        print(f"[+] {name} built and installed successfully!")
        continue

    os.makedirs(build_dir)
    
    print(f"[+] Extracting {name}...")
    tar_cmd = ["tar", "-xf", archive_path, "-C", build_dir, "--strip-components=1"]
    subprocess.run(tar_cmd, check=True)
    
    # 2.5 Patch version requirements in CMakeLists.txt and *.cmake files
    print(f"[+] Patching version constraints in {name}...")
    for root, dirs, files in os.walk(build_dir):
        for file in files:
            if file == "CMakeLists.txt" or file.endswith(".cmake"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    patched = False
                    if "6.5.0" in content:
                        content = content.replace("6.5.0", "6.4.2")
                        patched = True
                    if "6.10.0" in content:
                        content = content.replace("6.10.0", "6.8.2")
                        patched = True
                    if '"6.10"' in content:
                        content = content.replace('"6.10"', '"6.8"')
                        patched = True
                    if "6.22.0" in content:
                        content = content.replace("6.22.0", "6.6.0")
                        patched = True
                    if '"6.22"' in content:
                        content = content.replace('"6.22"', '"6.6"')
                        patched = True
                    if "find_package(Qt6GuiPrivate" in content:
                        content = content.replace("find_package(Qt6GuiPrivate", "# find_package(Qt6GuiPrivate")
                        patched = True
                    if "find_package(Qt6WaylandClientPrivate" in content:
                        content = content.replace("find_package(Qt6WaylandClientPrivate", "# find_package(Qt6WaylandClientPrivate")
                        patched = True
                    if "find_package(Qt6 COMPONENTS GuiPrivate)" in content:
                        content = content.replace("find_package(Qt6 COMPONENTS GuiPrivate)", "find_package(Qt6 COMPONENTS Gui)")
                        patched = True
                    if "Wayland 1.25" in content:
                        content = content.replace("Wayland 1.25", "Wayland 1.22")
                        patched = True
                    if "Wayland 1.24" in content:
                        content = content.replace("Wayland 1.24", "Wayland 1.22")
                        patched = True
                    if "Wayland 1.23" in content:
                        content = content.replace("Wayland 1.23", "Wayland 1.22")
                        patched = True
                    if "find_package(Wayland 1.25" in content:
                        content = content.replace("find_package(Wayland 1.25", "find_package(Wayland 1.22")
                        patched = True
                    if "find_package(Wayland 1.24" in content:
                        content = content.replace("find_package(Wayland 1.24", "find_package(Wayland 1.22")
                        patched = True
                    if "find_package(Wayland 1.23" in content:
                        content = content.replace("find_package(Wayland 1.23", "find_package(Wayland 1.22")
                        patched = True
                    if "WaylandProtocols 1.45" in content:
                        content = content.replace("WaylandProtocols 1.45", "WaylandProtocols 1.38")
                        patched = True
                    if "WaylandProtocols 1.40" in content:
                        content = content.replace("WaylandProtocols 1.40", "WaylandProtocols 1.38")
                        patched = True
                    if "Libinput 1.28" in content:
                        content = content.replace("Libinput 1.28", "Libinput 1.25")
                        patched = True
                    if "Libinput 1.29" in content:
                        content = content.replace("Libinput 1.29", "Libinput 1.25")
                        patched = True
                    if "find_package(Libinput 1.28" in content:
                        content = content.replace("find_package(Libinput 1.28", "find_package(Libinput 1.25")
                        patched = True
                        
                    if patched:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                except Exception as e:
                    print(f"[-] Failed to patch {file_path}: {e}")
    
    # 3. Configure source
    print(f"[+] Configuring {name}...")
    cmake_cmd = [
        "cmake", "-B", "build_dir", "-GNinja",
        "-DCMAKE_INSTALL_PREFIX=/usr",
        f"-DCMAKE_PREFIX_PATH={SMECH_TARGET}/usr;/usr",
        "-DBUILD_TESTING=OFF"
    ]
    # Extra config options
    if name == "qcoro":
        cmake_cmd.extend(["-DQCORO_BUILD_TESTS=OFF", "-DQCORO_WITH_QT5=OFF", "-DQCORO_WITH_QT6=ON", "-DQCORO_WITH_QTWEBSOCKETS=OFF"])
    elif name == "polkit-qt-1":
        cmake_cmd.extend(["-DQT_MAJOR_VERSION=6"])
    elif name == "qca":
        cmake_cmd.extend(["-DQT6=ON"])
    elif name in ["kdbusaddons", "kguiaddons", "kidletime", "kcrash", "kio", "kglobalacceld"]:
        cmake_cmd.extend(["-DWITH_X11=OFF"])
        if name == "kio":
            cmake_cmd.extend(["-DCMAKE_CXX_STANDARD=20"])
    elif name == "kwindowsystem":
        cmake_cmd.extend(["-DKWINDOWSYSTEM_X11=OFF"])
    elif name == "kstatusnotifieritem":
        cmake_cmd.extend(["-DWITHOUT_X11=ON"])
    elif name == "prison":
        cmake_cmd.extend(["-DWITH_MULTIMEDIA=OFF"])
    elif name == "ktextwidgets":
        cmake_cmd.extend(["-DWITH_TEXT_TO_SPEECH=OFF"])
    elif name == "kholidays":
        cmake_cmd.extend(["-DCMAKE_CXX_STANDARD=20"])
    elif name == "knighttime":
        # 1. Patch kdarklightsettings.kcfg to change 'type="Time"' to 'type="String"'
        kcfg_path = os.path.join(build_dir, "src/daemon/kdarklightsettings.kcfg")
        if os.path.exists(kcfg_path):
            with open(kcfg_path, "r") as f:
                content = f.read()
            content = content.replace('type="Time"', 'type="String"')
            with open(kcfg_path, "w") as f:
                f.write(content)
        
        # 2. Patch kdarklightmanager.cpp to parse sunriseStart() and sunsetStart() from string to QTime
        manager_cpp = os.path.join(build_dir, "src/daemon/kdarklightmanager.cpp")
        if os.path.exists(manager_cpp):
            with open(manager_cpp, "r") as f:
                content = f.read()
            content = "#include <QTime>\n" + content
            content = content.replace("m_settings->sunriseStart()", "QTime::fromString(m_settings->sunriseStart())")
            content = content.replace("m_settings->sunsetStart()", "QTime::fromString(m_settings->sunsetStart())")
            content = content.replace(
                'knighttimerc->setSunriseStart(QTime::fromString(nightLight.readEntry(QStringLiteral("MorningBeginFixed"), QStringLiteral("0600")), QStringLiteral("hhmm")))',
                'knighttimerc->setSunriseStart(QTime::fromString(nightLight.readEntry(QStringLiteral("MorningBeginFixed"), QStringLiteral("0600")), QStringLiteral("hhmm")).toString(Qt::ISODate))'
            )
            content = content.replace(
                'knighttimerc->setSunsetStart(QTime::fromString(nightLight.readEntry(QStringLiteral("EveningBeginFixed"), QStringLiteral("1800")), QStringLiteral("hhmm")))',
                'knighttimerc->setSunsetStart(QTime::fromString(nightLight.readEntry(QStringLiteral("EveningBeginFixed"), QStringLiteral("1800")), QStringLiteral("hhmm")).toString(Qt::ISODate))'
            )
            content = content.replace("#include <KSystemClockSkewNotifier>", '#include "ksystemclockskewnotifier_stub.h"')
            with open(manager_cpp, "w") as f:
                f.write(content)

        # 3. Create the KSystemClockSkewNotifier stub header & cpp files
        daemon_dir = os.path.join(build_dir, "src/daemon")
        if os.path.exists(daemon_dir):
            stub_h = os.path.join(daemon_dir, "ksystemclockskewnotifier_stub.h")
            with open(stub_h, "w") as f:
                f.write('''#ifndef KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
#define KSYSTEMCLOCKSKEWNOTIFIER_STUB_H

#include <QObject>

class KSystemClockSkewNotifier : public QObject {
    Q_OBJECT
public:
    explicit KSystemClockSkewNotifier(QObject *parent = nullptr) : QObject(parent) {}
    void setActive(bool active) { Q_UNUSED(active); }
Q_SIGNALS:
    void skewed();
};

#endif // KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
''')
            
            stub_cpp = os.path.join(daemon_dir, "ksystemclockskewnotifier_stub.cpp")
            with open(stub_cpp, "w") as f:
                f.write('''#include "ksystemclockskewnotifier_stub.h"
#include "moc_ksystemclockskewnotifier_stub.cpp"
''')

        # 4. Patch src/daemon/CMakeLists.txt to include ksystemclockskewnotifier_stub.cpp
        daemon_cmake = os.path.join(build_dir, "src/daemon/CMakeLists.txt")
        if os.path.exists(daemon_cmake):
            with open(daemon_cmake, "r") as f:
                content = f.read()
            content = content.replace("main.cpp", "main.cpp\n    ksystemclockskewnotifier_stub.cpp")
            with open(daemon_cmake, "w") as f:
                f.write(content)
    elif name == "knewstuff":
        # Patch resultsstream.cpp to replace request != d->request with !(request == d->request) for C++17 compatibility
        rs_cpp = os.path.join(build_dir, "src/core/resultsstream.cpp")
        if os.path.exists(rs_cpp):
            with open(rs_cpp, "r") as f:
                content = f.read()
            content = content.replace("request != d->request", "!(request == d->request)")
            with open(rs_cpp, "w") as f:
                f.write(content)
    elif name == "kwallet":
        # Patch kwalletd.cpp to bypass X11/KX11Extras
        kwalletd_cpp = os.path.join(build_dir, "src/runtime/kwalletd/kwalletd.cpp")
        if os.path.exists(kwalletd_cpp):
            with open(kwalletd_cpp, "r") as f:
                content = f.read()
            # Force HAVE_X11 to 0 on SmechOS (Wayland-only) and avoid including KX11Extras
            old_block = "#if !defined(Q_OS_WIN) && !defined(Q_OS_MAC)\\n#define HAVE_X11 1\\n#include <KX11Extras>\\n#else\\n#define HAVE_X11 0\\n#endif"
            # Try both raw newlines and literal characters
            content = content.replace(
                "#if !defined(Q_OS_WIN) && !defined(Q_OS_MAC)\\n#define HAVE_X11 1\\n#include <KX11Extras>\\n#else\\n#define HAVE_X11 0\\n#endif",
                "#if !defined(Q_OS_WIN) && !defined(Q_OS_MAC) && 0\\n#define HAVE_X11 1\\n#include <KX11Extras>\\n#else\\n#define HAVE_X11 0\\n#endif"
            )
            content = content.replace(
                "#if !defined(Q_OS_WIN) && !defined(Q_OS_MAC)\\n#define HAVE_X11 1\\n#include <KX11Extras>\\n#else\\n#define HAVE_X11 0\\n#endif".replace("\\n", "\n"),
                "#if !defined(Q_OS_WIN) && !defined(Q_OS_MAC) && 0\\n#define HAVE_X11 1\\n#include <KX11Extras>\\n#else\\n#define HAVE_X11 0\\n#endif".replace("\\n", "\n")
            )
            with open(kwalletd_cpp, "w") as f:
                f.write(content)
    elif name == "ktexteditor":
        # 1. Write the QTextToSpeech stub header file
        utils_dir = os.path.join(build_dir, "src/utils")
        os.makedirs(utils_dir, exist_ok=True)
        stub_path = os.path.join(utils_dir, "qtexttospeech_stub.h")
        with open(stub_path, "w") as f:
            f.write('''#ifndef QTEXTTOSPEECH_STUB_H
#define QTEXTTOSPEECH_STUB_H

#include <QObject>
#include <QString>

class QTextToSpeech : public QObject {
    Q_OBJECT
public:
    enum class ErrorReason {
        NoError = 0,
        Unknown = 1
    };

    explicit QTextToSpeech(QObject *parent = nullptr) : QObject(parent) {}

    ErrorReason errorReason() const { return ErrorReason::NoError; }
    QString errorString() const { return QString(); }

    void say(const QString &text) { Q_UNUSED(text); }
    void stop() {}
    void pause() {}
    void resume() {}

Q_SIGNALS:
    void errorOccurred(QTextToSpeech::ErrorReason reason, const QString &errorString);
};

#endif // QTEXTTOSPEECH_STUB_H
''')

        # 2. Patch kateglobal.cpp and kateview.cpp to include our stub instead of <QTextToSpeech>
        kateglobal_cpp = os.path.join(utils_dir, "kateglobal.cpp")
        if os.path.exists(kateglobal_cpp):
            with open(kateglobal_cpp, "r") as f:
                content = f.read()
            content = content.replace("#include <QTextToSpeech>", '#include "qtexttospeech_stub.h"')
            with open(kateglobal_cpp, "w") as f:
                f.write(content)

        kateview_cpp = os.path.join(build_dir, "src/view/kateview.cpp")
        if os.path.exists(kateview_cpp):
            with open(kateview_cpp, "r") as f:
                content = f.read()
            content = content.replace("#include <QTextToSpeech>", '#include "../utils/qtexttospeech_stub.h"')
            with open(kateview_cpp, "w") as f:
                f.write(content)

        # 3. Patch CMakeLists.txt to remove TextToSpeech component and requirement of Qt6
        cmake_path = os.path.join(build_dir, "CMakeLists.txt")
        if os.path.exists(cmake_path):
            with open(cmake_path, "r") as f:
                content = f.read()
            content = content.replace("PrintSupport TextToSpeech", "PrintSupport")
            with open(cmake_path, "w") as f:
                f.write(content)

        # 4. Patch src/CMakeLists.txt to remove Qt6::TextToSpeech link library and add the stub file to target sources
        src_cmake = os.path.join(build_dir, "src/CMakeLists.txt")
        if os.path.exists(src_cmake):
            with open(src_cmake, "r") as f:
                content = f.read()
            content = content.replace("  Qt6::TextToSpeech", "")
            # Write a .cpp file to compile with AUTOMOC
            stub_cpp_path = os.path.join(utils_dir, "qtexttospeech_stub.cpp")
            with open(stub_cpp_path, "w") as stub_f:
                stub_f.write('#include "qtexttospeech_stub.h"\n#include "moc_qtexttospeech_stub.cpp"\n')
            # Also, add qtexttospeech_stub.cpp to the target sources of KF6TextEditor to trigger AUTOMOC on it
            content = content.replace("utils/kateglobal.cpp", "utils/kateglobal.cpp\nutils/qtexttospeech_stub.cpp")
            with open(src_cmake, "w") as f:
                f.write(content)
    elif name == "calamares":
        cmake_cmd.extend(["-DWITH_QT6=ON", "-DWITH_PYTHON=ON", "-DSKIP_MODULES=webview"])
    elif name == "sddm":
        cmake_cmd.extend(["-DBUILD_WITH_QT6=ON", "-DBUILD_MAN_PAGES=OFF"])
    elif name == "libkscreen":
        # Patch libkscreen to be pure Wayland DPMS (disable XCB DPMS)
        dpms_cmake = os.path.join(build_dir, "src/libdpms/CMakeLists.txt")
        if os.path.exists(dpms_cmake):
            with open(dpms_cmake, "r") as f:
                content = f.read()
            content = content.replace("xcbdpmshelper.cpp", "")
            content = content.replace("XCB::XCB XCB::DPMS XCB::RANDR", "")
            with open(dpms_cmake, "w") as f:
                f.write(content)
        
        dpms_cpp = os.path.join(build_dir, "src/libdpms/dpms.cpp")
        if os.path.exists(dpms_cpp):
            with open(dpms_cpp, "w") as f:
                f.write('''// Pure Wayland DPMS implementation for SmechOS
#include "dpms.h"
#include "kscreendpms_debug.h"
#include "waylanddpmshelper_p.h"
#include <QGuiApplication>

KScreen::Dpms::Dpms(QObject *parent)
    : QObject(parent)
{
    if (QGuiApplication::platformName().startsWith(QLatin1String("wayland"), Qt::CaseInsensitive)) {
        m_helper.reset(new WaylandDpmsHelper);
    } else {
        qCWarning(KSCREEN_DPMS) << "Platform is not Wayland, this doesn't make sense. Platform name is" << QGuiApplication::platformName();
        return;
    }

    connect(m_helper.data(), &AbstractDpmsHelper::supportedChanged, this, &Dpms::supportedChanged);
    connect(m_helper.data(), &AbstractDpmsHelper::modeChanged, this, &Dpms::modeChanged);
    connect(m_helper.data(), &AbstractDpmsHelper::hasPendingChangesChanged, this, &Dpms::hasPendingChangesChanged);
}

KScreen::Dpms::~Dpms() {}
void KScreen::Dpms::switchMode(KScreen::Dpms::Mode mode, const QList<QScreen *> &screens) {
    m_helper->trigger(mode, screens.isEmpty() ? qGuiApp->screens() : screens);
}
bool KScreen::Dpms::isSupported() const { return m_helper->isSupported(); }
bool KScreen::Dpms::hasPendingChanges() const { return m_helper->hasPendingChanges(); }
#include "moc_dpms.cpp"
''')

        # Disable XRandR (X11) backend compilation
        backends_cmake = os.path.join(build_dir, "backends/CMakeLists.txt")
        if os.path.exists(backends_cmake):
            with open(backends_cmake, "r") as f:
                content = f.read()
            content = content.replace("add_subdirectory(xrandr)", "# add_subdirectory(xrandr)")
            with open(backends_cmake, "w") as f:
                f.write(content)

        # Patch backendmanager.cpp to remove X11 private headers and QX11Info dependencies
        bm_cpp = os.path.join(build_dir, "src/backendmanager.cpp")
        if os.path.exists(bm_cpp):
            with open(bm_cpp, "r") as f:
                content = f.read()
            content = content.replace('#include <QtGui/private/qtx11extras_p.h>', '')
            content = content.replace('QX11Info::isPlatformX11()', 'false')
            with open(bm_cpp, "w") as f:
                f.write(content)

        # Patch setconfigoperation.cpp to remove C++23 std::ranges::to and views::drop dependency for GCC 13 compatibility
        sco_cpp = os.path.join(build_dir, "src/setconfigoperation.cpp")
        if os.path.exists(sco_cpp):
            with open(sco_cpp, "r") as f:
                content = f.read()
            content = content.replace("#include <ranges>", "#include <ranges>\n#include <algorithm>")
            old_ranges_block = """    const auto outputs = config->outputs();
    auto enabled = outputs | std::views::filter([](const auto &output) {
                       return output->isEnabled();
                   })
        | std::ranges::to<QList>();
    if (enabled.isEmpty()) {
        return;
    }
    std::ranges::sort(enabled, [](const auto &left, const auto &right) {
        return left->priority() < right->priority();
    });
    uint32_t priority = enabled.front()->priority();
    for (const auto &output : enabled | std::views::drop(1)) {
        if (output->priority() <= priority) {
            output->setPriority(priority + 1);
        }
        priority++;
    }"""
            new_ranges_block = """    const auto outputs = config->outputs();
    QList<KScreen::OutputPtr> enabled;
    for (const auto &output : outputs) {
        if (output->isEnabled()) {
            enabled.append(output);
        }
    }
    if (enabled.isEmpty()) {
        return;
    }
    std::sort(enabled.begin(), enabled.end(), [](const auto &left, const auto &right) {
        return left->priority() < right->priority();
    });
    uint32_t priority = enabled.front()->priority();
    for (int i = 1; i < enabled.size(); ++i) {
        const auto &output = enabled[i];
        if (output->priority() <= priority) {
            output->setPriority(priority + 1);
        }
        priority++;
    }"""
            if old_ranges_block in content:
                content = content.replace(old_ranges_block, new_ranges_block)
            else:
                # If indentation or line endings vary, let's normalize and try a looser match or replace
                content = content.replace("std::ranges::to<QList>()", "")
            with open(sco_cpp, "w") as f:
                f.write(content)

        # Patch doctor.cpp to replace #include <print> with #include <format> for GCC 13 compatibility
        doc_cpp = os.path.join(build_dir, "src/doctor/doctor.cpp")
        if os.path.exists(doc_cpp):
            with open(doc_cpp, "r") as f:
                content = f.read()
            content = content.replace("#include <print>", "#include <format>")
            with open(doc_cpp, "w") as f:
                f.write(content)

        # Patch waylandconfig.cpp to disable Wayland 1.24+ wl_fixes protocol logic on SmechOS (which uses Wayland 1.23.1)
        wc_cpp = os.path.join(build_dir, "backends/kwayland/waylandconfig.cpp")
        if os.path.exists(wc_cpp):
            with open(wc_cpp, "r") as f:
                content = f.read()
            content = content.replace("qstrcmp(interface, wl_fixes_interface.name) == 0", "false")
            content = content.replace("self->m_fixes = static_cast<wl_fixes *>(wl_registry_bind(registry, name, &wl_fixes_interface, 1));", "// m_fixes disabled")
            content = content.replace("wl_fixes_destroy_registry(m_fixes, m_registry);", "// fixes destroy registry")
            content = content.replace("wl_fixes_destroy(m_fixes);", "// fixes destroy")
            with open(wc_cpp, "w") as f:
                f.write(content)
    elif name == "layer-shell-qt":
        # Patch qwaylandlayersurface_p.h to remove 'override' from setWindowSize to compile with Qt 6.8+
        ls_h = os.path.join(build_dir, "src/qwaylandlayersurface_p.h")
        if os.path.exists(ls_h):
            with open(ls_h, "r") as f:
                content = f.read()
            content = content.replace("void setWindowSize(const QSize &size) override;", "void setWindowSize(const QSize &size);")
            with open(ls_h, "w") as f:
                f.write(content)
        
        # Patch qwaylandlayersurface.cpp to replace window()->updateExposure() with window()->sendRecursiveExposeEvent()
        ls_cpp = os.path.join(build_dir, "src/qwaylandlayersurface.cpp")
        if os.path.exists(ls_cpp):
            with open(ls_cpp, "r") as f:
                content = f.read()
            content = content.replace("window()->updateExposure();", "window()->sendRecursiveExposeEvent();")
            with open(ls_cpp, "w") as f:
                f.write(content)
    elif name == "libplasma":
        # Patch CMakeLists.txt to remove I18nQml component search since KF6 6.6.0 doesn't have it separated
        cmake_lists_path = os.path.join(build_dir, "CMakeLists.txt")
        if os.path.exists(cmake_lists_path):
            with open(cmake_lists_path, "r") as f:
                content = f.read()
            content = content.replace("        I18nQml\n", "")
            content = content.replace("        I18nQml", "")
            with open(cmake_lists_path, "w") as f:
                f.write(content)
        
        # Patch src/plasmaquick/CMakeLists.txt to use KF6::I18n instead of KF6::I18nQml
        pq_cmake = os.path.join(build_dir, "src/plasmaquick/CMakeLists.txt")
        if os.path.exists(pq_cmake):
            with open(pq_cmake, "r") as f:
                content = f.read()
            content = content.replace("KF6::I18nQml", "KF6::I18n")
            with open(pq_cmake, "w") as f:
                f.write(content)
                
        # Patch src/declarativeimports/core/CMakeLists.txt to use KF6::I18n instead of KF6::I18nQml
        core_cmake = os.path.join(build_dir, "src/declarativeimports/core/CMakeLists.txt")
        if os.path.exists(core_cmake):
            with open(core_cmake, "r") as f:
                content = f.read()
            content = content.replace("KF6::I18nQml", "KF6::I18n")
            with open(core_cmake, "w") as f:
                f.write(content)

        # Patch KLocalizedQmlContext to KLocalizedContext
        for patch_file in [
            "src/declarativeimports/core/corebindingsplugin.cpp",
            "src/plasmaquick/sharedqmlengine.cpp",
            "src/plasmaquick/configview.cpp"
        ]:
            full_patch_path = os.path.join(build_dir, patch_file)
            if os.path.exists(full_patch_path):
                with open(full_patch_path, "r", encoding="utf-8") as f:
                    p_content = f.read()
                p_content = p_content.replace("<KLocalizedQmlContext>", "<KLocalizedContext>")
                p_content = p_content.replace("KLocalizedQmlContext", "KLocalizedContext")
                with open(full_patch_path, "w", encoding="utf-8") as f:
                    f.write(p_content)

        # Patch KX11Extras / X11 dependency blocks so libplasma buildsWayland-only properly
        # 1. src/plasma/private/theme_p.cpp
        theme_cpp = os.path.join(build_dir, "src/plasma/private/theme_p.cpp")
        if os.path.exists(theme_cpp):
            with open(theme_cpp, "r") as f:
                t_content = f.read()
            t_content = t_content.replace("#include <KX11Extras>", "#if HAVE_X11\n#include <KX11Extras>\n#endif")
            t_content = t_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        compositingActive = KX11Extras::self()->compositingActive();\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        compositingActive = KX11Extras::self()->compositingActive();\n    }\n#endif"
            )
            t_content = t_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        connect(KX11Extras::self(), &KX11Extras::compositingChanged, selectorsUpdateTimer, qOverload<>(&QTimer::start));\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        connect(KX11Extras::self(), &KX11Extras::compositingChanged, selectorsUpdateTimer, qOverload<>(&QTimer::start));\n    }\n#endif"
            )
            with open(theme_cpp, "w") as f:
                f.write(t_content)

        # 2. src/declarativeimports/core/windowthumbnail.cpp
        wt_cpp = os.path.join(build_dir, "src/declarativeimports/core/windowthumbnail.cpp")
        if os.path.exists(wt_cpp):
            with open(wt_cpp, "r") as f:
                wt_content = f.read()
            wt_content = wt_content.replace("#include <KX11Extras>", "#if HAVE_X11\n#include <KX11Extras>\n#endif")
            wt_content = wt_content.replace(
                "    if (KWindowSystem::isPlatformX11() && !KX11Extras::self()->hasWId(winId)) {",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11() && !KX11Extras::self()->hasWId(winId)) {\n#else\n    if (false) {\n#endif"
            )
            wt_content = wt_content.replace(
                "    if (KWindowSystem::isPlatformX11() && KX11Extras::self()->hasWId(m_winId)) {\n        icon = KX11Extras::self()->icon(m_winId, boundingRect().width(), boundingRect().height());",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11() && KX11Extras::self()->hasWId(m_winId)) {\n        icon = KX11Extras::self()->icon(m_winId, boundingRect().width(), boundingRect().height());\n#else\n    if (false) {\n        (void)m_winId;\n#endif"
            )
            with open(wt_cpp, "w") as f:
                f.write(wt_content)

        # 3. src/plasmaquick/plasmawindow.cpp
        pw_cpp = os.path.join(build_dir, "src/plasmaquick/plasmawindow.cpp")
        if os.path.exists(pw_cpp):
            with open(pw_cpp, "r") as f:
                pw_content = f.read()
            pw_content = pw_content.replace('#include "plasmawindow.h"', '#include "plasmawindow.h"\n#include <config-plasma.h>')
            pw_content = pw_content.replace('#include <KX11Extras>', '#if HAVE_X11\n#include <KX11Extras>\n#endif')
            pw_content = pw_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);\n    }\n#endif"
            )
            pw_content = pw_content.replace(
                "    if (!KWindowSystem::isPlatformX11() || KX11Extras::compositingActive()) {\n        q->setMask(QRegion());\n    } else {\n        q->setMask(mask);\n    }",
                "#if HAVE_X11\n    if (!KWindowSystem::isPlatformX11() || KX11Extras::compositingActive()) {\n        q->setMask(QRegion());\n    } else {\n        q->setMask(mask);\n    }\n#else\n    q->setMask(QRegion());\n#endif"
            )
            with open(pw_cpp, "w") as f:
                f.write(pw_content)

        # 4. src/plasmaquick/appletpopup.cpp
        ap_cpp = os.path.join(build_dir, "src/plasmaquick/appletpopup.cpp")
        if os.path.exists(ap_cpp):
            with open(ap_cpp, "r") as f:
                ap_content = f.read()
            ap_content = ap_content.replace('#include "appletpopup.h"', '#include "appletpopup.h"\n#include <config-plasma.h>')
            ap_content = ap_content.replace('#include <KX11Extras>', '#if HAVE_X11\n#include <KX11Extras>\n#endif')
            ap_content = ap_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setType(winId(), NET::AppletPopup);\n    } else {\n        PlasmaShellWaylandIntegration::get(this)->setRole(QtWayland::org_kde_plasma_surface::role::role_appletpopup);\n        PlasmaShellWaylandIntegration::get(this)->setTakesFocus(true);\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setType(winId(), NET::AppletPopup);\n    } else {\n        PlasmaShellWaylandIntegration::get(this)->setRole(QtWayland::org_kde_plasma_surface::role::role_appletpopup);\n        PlasmaShellWaylandIntegration::get(this)->setTakesFocus(true);\n    }\n#else\n    PlasmaShellWaylandIntegration::get(this)->setRole(QtWayland::org_kde_plasma_surface::role::role_appletpopup);\n    PlasmaShellWaylandIntegration::get(this)->setTakesFocus(true);\n#endif"
            )
            with open(ap_cpp, "w") as f:
                f.write(ap_content)

        # 5. src/plasmaquick/dialog.cpp
        diag_cpp = os.path.join(build_dir, "src/plasmaquick/dialog.cpp")
        if os.path.exists(diag_cpp):
            with open(diag_cpp, "r") as f:
                diag_content = f.read()
            diag_content = diag_content.replace('#include <KX11Extras>', '#if HAVE_X11\n#include <KX11Extras>\n#endif')
            diag_content = diag_content.replace(
                "        if (!KWindowSystem::isPlatformX11() || KX11Extras::compositingActive()) {\n            if (hasMask) {\n                hasMask = false;\n                q->setMask(QRegion());\n            }\n        } else {\n            hasMask = true;\n            q->setMask(dialogBackground->mask());\n        }",
                "#if HAVE_X11\n        if (!KWindowSystem::isPlatformX11() || KX11Extras::compositingActive()) {\n            if (hasMask) {\n                hasMask = false;\n                q->setMask(QRegion());\n            }\n        } else {\n            hasMask = true;\n            q->setMask(dialogBackground->mask());\n        }\n#else\n        if (hasMask) {\n            hasMask = false;\n            q->setMask(QRegion());\n        }\n#endif"
            )
            diag_content = diag_content.replace(
                "    if (!wmType && type != Dialog::Normal && KWindowSystem::isPlatformX11()) {\n        KX11Extras::setType(q->winId(), static_cast<NET::WindowType>(type));\n    }",
                "#if HAVE_X11\n    if (!wmType && type != Dialog::Normal && KWindowSystem::isPlatformX11()) {\n        KX11Extras::setType(q->winId(), static_cast<NET::WindowType>(type));\n    }\n#endif"
            )
            diag_content = diag_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        if (type == Dialog::Dock || type == Dialog::Notification || type == Dialog::OnScreenDisplay || type == Dialog::CriticalNotification) {\n            KX11Extras::setOnAllDesktops(q->winId(), true);\n        } else {\n            KX11Extras::setOnAllDesktops(q->winId(), false);\n        }\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        if (type == Dialog::Dock || type == Dialog::Notification || type == Dialog::OnScreenDisplay || type == Dialog::CriticalNotification) {\n            KX11Extras::setOnAllDesktops(q->winId(), true);\n        } else {\n            KX11Extras::setOnAllDesktops(q->winId(), false);\n        }\n    }\n#endif"
            )
            diag_content = diag_content.replace('#include <KWindowInfo>', '#if HAVE_X11\n#include <KWindowInfo>\n#endif')
            diag_content = diag_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        // on X11 we also consider windows with the type Dock\n        const KWindowInfo winInfo(item->window()->winId(), NET::WMWindowType);\n        outsideParentWindow = outsideParentWindow || (winInfo.windowType(NET::AllTypesMask) == NET::Dock && item->window()->mask().isNull());\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        // on X11 we also consider windows with the type Dock\n        const KWindowInfo winInfo(item->window()->winId(), NET::WMWindowType);\n        outsideParentWindow = outsideParentWindow || (winInfo.windowType(NET::AllTypesMask) == NET::Dock && item->window()->mask().isNull());\n    }\n#endif"
            )
            diag_content = diag_content.replace(
                "    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);\n    }",
                "#if HAVE_X11\n    if (KWindowSystem::isPlatformX11()) {\n        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);\n    }\n#endif"
            )
            with open(diag_cpp, "w") as f:
                f.write(diag_content)

        # 6. src/plasma/private/blureffectwatcher_p.h & blureffectwatcher.cpp
        bw_h = os.path.join(build_dir, "src/plasma/private/blureffectwatcher_p.h")
        if os.path.exists(bw_h):
            with open(bw_h, "r") as f:
                bw_h_content = f.read()
            bw_h_content = bw_h_content.replace(
                "#if HAVE_X11\n    bool nativeEventFilter(const QByteArray &eventType, void *message, qintptr *) override;\n#endif",
                "    bool nativeEventFilter(const QByteArray &eventType, void *message, qintptr *) override;"
            )
            with open(bw_h, "w") as f:
                f.write(bw_h_content)

        bw_cpp = os.path.join(build_dir, "src/plasma/private/blureffectwatcher.cpp")
        if os.path.exists(bw_cpp):
            with open(bw_cpp, "r") as f:
                bw_cpp_content = f.read()
            bw_cpp_content = bw_cpp_content.replace(
                "#if HAVE_X11\nbool BlurEffectWatcher::nativeEventFilter(const QByteArray &eventType, void *message, qintptr *result)",
                "bool BlurEffectWatcher::nativeEventFilter(const QByteArray &eventType, void *message, qintptr *result)\n{\n#if HAVE_X11"
            )
            bw_cpp_content = bw_cpp_content.replace(
                "    return false;\n}\n\nbool BlurEffectWatcher::fetchEffectActive() const",
                "    return false;\n#else\n    Q_UNUSED(eventType);\n    Q_UNUSED(message);\n    Q_UNUSED(result);\n    return false;\n#endif\n}\n\n#if HAVE_X11\nbool BlurEffectWatcher::fetchEffectActive() const"
            )
            with open(bw_cpp, "w") as f:
                f.write(bw_cpp_content)

        # Patch src/declarativeimports/kirigamiplasmastyle/plasmatheme.cpp to remove frameContrast and FrameContrastChangedEvent
        pt_cpp = os.path.join(build_dir, "src/declarativeimports/kirigamiplasmastyle/plasmatheme.cpp")
        if os.path.exists(pt_cpp):
            with open(pt_cpp, "r") as f:
                pt_content = f.read()
            pt_content = pt_content.replace(
                "setFrameContrast(KColorScheme::frameContrast());",
                "// setFrameContrast stubbed on SmechOS"
            )
            old_event_check = "if (event->type() == Kirigami::Platform::PlatformThemeEvents::FrameContrastChangedEvent::type) {"
            new_event_check = "if (false) { // FrameContrastChangedEvent stubbed on SmechOS"
            pt_content = pt_content.replace(old_event_check, new_event_check)
            with open(pt_cpp, "w") as f:
                f.write(pt_content)

        # Patch u"..." UTF-16 string literals to QStringLiteral("...") for KF6 6.6.0 compatibility
        import re
        for root_dir, _, files in os.walk(build_dir):
            for file in files:
                if file.endswith((".cpp", ".h")):
                    file_path = os.path.join(root_dir, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            file_content = f.read()
                        if 'u"' in file_content:
                            # Replace u"..."_s first, then u"..." to avoid syntax errors like QStringLiteral("...")_s
                            patched_content = re.sub(r'(\W|^)u"([^\n"]*)"_s', r'\1QStringLiteral("\2")', file_content)
                            patched_content = re.sub(r'(\W|^)u"([^\n"]*)"', r'\1QStringLiteral("\2")', patched_content)
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(patched_content)
                    except Exception as e:
                        print(f"[-] Failed to patch u\" literals in {file_path}: {e}")

        cmake_cmd.extend(["-DWITHOUT_X11=ON"])
    elif name == "kwin":
        # Patch CMakeLists.txt files in kwin to use KF6::I18n instead of KF6::I18nQml
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                if file == "CMakeLists.txt" or file.endswith(".cmake"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if "KF6::I18nQml" in content:
                            content = content.replace("KF6::I18nQml", "KF6::I18n")
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as e:
                        print(f"[-] Failed to patch I18nQml in {file_path}: {e}")
        
        # Patch KLocalizedQmlContext to KLocalizedContext in all kwin source and header files
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                if file.endswith((".cpp", ".h")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if "KLocalizedQmlContext" in content:
                            content = content.replace("KLocalizedQmlContext", "KLocalizedContext")
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as e:
                        print(f"[-] Failed to patch KLocalizedQmlContext in {file_path}: {e}")
        
        # Patch src/helpers/killer/killer.cpp to remove private/qtx11extras_p.h dependency on Wayland-only builds
        killer_cpp = os.path.join(build_dir, "src/helpers/killer/killer.cpp")
        if os.path.exists(killer_cpp):
            try:
                with open(killer_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("#include <private/qtx11extras_p.h>", "/* #include <private/qtx11extras_p.h> */")
                content = content.replace("QX11Info::setAppUserTime(timestamp);", "/* QX11Info::setAppUserTime(timestamp); */")
                with open(killer_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched killer.cpp to remove X11 private headers dependency.")
            except Exception as e:
                print(f"[-] Failed to patch killer.cpp: {e}")

        # Patch src/kcms/screenedges/kwintouchscreenmoduledata.h to define setRelevant stub for older KF6 (6.6.0)
        touch_h = os.path.join(build_dir, "src/kcms/screenedges/kwintouchscreenmoduledata.h")
        if os.path.exists(touch_h):
            try:
                with open(touch_h, "r", encoding="utf-8") as f:
                    content = f.read()
                if "void updateRelevance();" in content and "void setRelevant(" not in content:
                    content = content.replace("void updateRelevance();", "void updateRelevance();\n    void setRelevant(bool) {}")
                    with open(touch_h, "w", encoding="utf-8") as f:
                        f.write(content)
                print("[+] Successfully patched kwintouchscreenmoduledata.h with setRelevant stub.")
            except Exception as e:
                print(f"[-] Failed to patch kwintouchscreenmoduledata.h: {e}")

        # Patch src/kcms/tabbox/layoutpreview.cpp to fix KLocalization namespace / setupLocalizedContext
        layout_cpp = os.path.join(build_dir, "src/kcms/tabbox/layoutpreview.cpp")
        if os.path.exists(layout_cpp):
            try:
                with open(layout_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("KLocalization::setupLocalizedContext(engine);", "engine->rootContext()->setContextObject(new KLocalizedContext(engine));")
                with open(layout_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched layoutpreview.cpp localization call.")
            except Exception as e:
                print(f"[-] Failed to patch layoutpreview.cpp: {e}")

        # Patch src/compositor.h to include unordered_set and unordered_map
        comp_h = os.path.join(build_dir, "src/compositor.h")
        if os.path.exists(comp_h):
            try:
                with open(comp_h, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("#include <QObject>", "#include <QObject>\n#include <unordered_set>\n#include <unordered_map>")
                with open(comp_h, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched compositor.h with unordered_set/map includes.")
            except Exception as e:
                print(f"[-] Failed to patch compositor.h: {e}")

        # Patch src/compositor.cpp to comment out KCrash::setGPUData call
        compositor_cpp = os.path.join(build_dir, "src/compositor.cpp")
        if os.path.exists(compositor_cpp):
            try:
                with open(compositor_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("KCrash::setGPUData(collectCrashInformation(backend.get()));", "/* KCrash::setGPUData(collectCrashInformation(backend.get())); */")
                with open(compositor_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched compositor.cpp to bypass KCrash::setGPUData.")
            except Exception as e:
                print(f"[-] Failed to patch compositor.cpp: {e}")

        # Patch src/outputconfigurationstore.cpp to use std::make_pair instead of std::make_tuple for return type compatibility
        ocs_cpp = os.path.join(build_dir, "src/outputconfigurationstore.cpp")
        if os.path.exists(ocs_cpp):
            try:
                with open(ocs_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("std::make_tuple(config, ConfigType::Preexisting)", "std::make_pair(config, ConfigType::Preexisting)")
                content = content.replace("std::make_tuple(config, ConfigType::Generated)", "std::make_pair(config, ConfigType::Generated)")
                with open(ocs_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched outputconfigurationstore.cpp to use std::make_pair.")
            except Exception as e:
                print(f"[-] Failed to patch outputconfigurationstore.cpp: {e}")

        # Patch src/wayland/shmclientbuffer_p.h and shmclientbuffer.cpp to comment out shm_release since SmechOS's older QtWayland does not have it
        shm_h = os.path.join(build_dir, "src/wayland/shmclientbuffer_p.h")
        if os.path.exists(shm_h):
            try:
                with open(shm_h, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("void shm_release(Resource *resource) override;", "// void shm_release(Resource *resource) override;")
                with open(shm_h, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched shmclientbuffer_p.h.")
            except Exception as e:
                print(f"[-] Failed to patch shmclientbuffer_p.h: {e}")

        shm_cpp = os.path.join(build_dir, "src/wayland/shmclientbuffer.cpp")
        if os.path.exists(shm_cpp):
            try:
                with open(shm_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                old_impl = "void ShmClientBufferIntegrationPrivate::shm_release(Resource *resource)\n{\n    wl_resource_destroy(resource->handle);\n}"
                new_impl = "/*\nvoid ShmClientBufferIntegrationPrivate::shm_release(Resource *resource)\n{\n    wl_resource_destroy(resource->handle);\n}\n*/"
                content = content.replace(old_impl, new_impl)
                with open(shm_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched shmclientbuffer.cpp.")
            except Exception as e:
                print(f"[-] Failed to patch shmclientbuffer.cpp: {e}")

        # Patch src/wayland/keyboard.cpp to replace KeyboardInterfacePrivate::Resource * with auto * to fix any_of compilation
        kbd_cpp = os.path.join(build_dir, "src/wayland/keyboard.cpp")
        if os.path.exists(kbd_cpp):
            try:
                with open(kbd_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("[client](KeyboardInterfacePrivate::Resource *keyboardResource)", "[client](auto *keyboardResource)")
                with open(kbd_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched keyboard.cpp lambda type.")
            except Exception as e:
                print(f"[-] Failed to patch keyboard.cpp: {e}")

        # Patch src/plugins/qpa/eglplatformcontext.h to include <QtGui/qopenglcontext_platform.h> to define QNativeInterface::QEGLContext
        egl_h = os.path.join(build_dir, "src/plugins/qpa/eglplatformcontext.h")
        if os.path.exists(egl_h):
            try:
                with open(egl_h, "r", encoding="utf-8") as f:
                    content = f.read()
                if "qopenglcontext_platform.h" not in content:
                    content = content.replace("#include <qpa/qplatformopenglcontext.h>", "#include <qpa/qplatformopenglcontext.h>\n#include <QtGui/qopenglcontext_platform.h>")
                    with open(egl_h, "w", encoding="utf-8") as f:
                        f.write(content)
                print("[+] Successfully patched eglplatformcontext.h with qopenglcontext_platform.h include.")
            except Exception as e:
                print(f"[-] Failed to patch eglplatformcontext.h: {e}")

        # Patch src/wayland/xdgsession_v1.cpp to replace store()->remove with store()->insert with empty QByteArray
        sess_cpp = os.path.join(build_dir, "src/wayland/xdgsession_v1.cpp")
        if os.path.exists(sess_cpp):
            try:
                with open(sess_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("m_storage->store()->remove(m_sessionId);", "m_storage->store()->insert(m_sessionId, QByteArray());")
                with open(sess_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched xdgsession_v1.cpp cache remove method.")
            except Exception as e:
                print(f"[-] Failed to patch xdgsession_v1.cpp: {e}")

        # Patch src/plugins/qpa/integration.h and integration.cpp to replace QDesktopUnixServices with QGenericUnixServices for Qt 6.8.2 compat
        qpa_int_h = os.path.join(build_dir, "src/plugins/qpa/integration.h")
        if os.path.exists(qpa_int_h):
            try:
                with open(qpa_int_h, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("#include <QtGui/private/qdesktopunixservices_p.h>", "#include <QtGui/private/qgenericunixservices_p.h>")
                content = content.replace("std::unique_ptr<QDesktopUnixServices> m_services;", "std::unique_ptr<QGenericUnixServices> m_services;")
                with open(qpa_int_h, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched integration.h to use QGenericUnixServices.")
            except Exception as e:
                print(f"[-] Failed to patch integration.h: {e}")

        qpa_int_cpp = os.path.join(build_dir, "src/plugins/qpa/integration.cpp")
        if os.path.exists(qpa_int_cpp):
            try:
                with open(qpa_int_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("m_services(new QDesktopUnixServices())", "m_services(new QGenericUnixServices())")
                with open(qpa_int_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched integration.cpp to construct QGenericUnixServices.")
            except Exception as e:
                print(f"[-] Failed to patch integration.cpp: {e}")

        # Patch src/plugins/windowsystem/windowsystem.h to define KWindowSystemPrivateV3 if not present (needed for older kwindowsystem on SmechOS)
        win_sys_h = os.path.join(build_dir, "src/plugins/windowsystem/windowsystem.h")
        if os.path.exists(win_sys_h):
            try:
                with open(win_sys_h, "r", encoding="utf-8") as f:
                    content = f.read()
                if "class KWindowSystemPrivateV3" not in content:
                    content = content.replace(
                        "#include <QObject>",
                        "#include <QObject>\n#include <QFuture>\n\nclass KWindowSystemPrivateV3 : public KWindowSystemPrivateV2\n{\npublic:\n    virtual QFuture<QString> xdgActivationToken(QWindow *window, uint32_t serial, const QString &appId) = 0;\n};"
                    )
                    content = content.replace(
                        "class WindowSystem : public QObject, public KWindowSystemPrivateV3",
                        "class WindowSystem : public QObject, public ::KWindowSystemPrivateV3"
                    )
                    with open(win_sys_h, "w", encoding="utf-8") as f:
                        f.write(content)
                print("[+] Successfully patched windowsystem.h to define KWindowSystemPrivateV3.")
            except Exception as e:
                print(f"[-] Failed to patch windowsystem.h: {e}")

        # Create KSystemClockSkewNotifier stub and patch CMakeLists.txt in the nightlight plugin
        nl_dir = os.path.join(build_dir, "src/plugins/nightlight")
        if os.path.exists(nl_dir):
            try:
                # 1. Create stub header (.h) for AUTOMOC
                stub_hdr_h_path = os.path.join(nl_dir, "KSystemClockSkewNotifier.h")
                with open(stub_hdr_h_path, "w") as f:
                    f.write('''#ifndef KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
#define KSYSTEMCLOCKSKEWNOTIFIER_STUB_H

#include <QObject>

class KSystemClockSkewNotifier : public QObject {
    Q_OBJECT
public:
    explicit KSystemClockSkewNotifier(QObject *parent = nullptr) : QObject(parent) {}
    void setActive(bool active) { Q_UNUSED(active); }
Q_SIGNALS:
    void skewed();
};

#endif // KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
''')
                # 2. Create clean forwarder header (no extension) for nightlightmanager.cpp include
                stub_hdr_path = os.path.join(nl_dir, "KSystemClockSkewNotifier")
                with open(stub_hdr_path, "w") as f:
                    f.write('#include "KSystemClockSkewNotifier.h"\n')

                # 3. Create stub .cpp file including the .h and its moc file
                stub_cpp_path = os.path.join(nl_dir, "ksystemclockskewnotifier_stub.cpp")
                with open(stub_cpp_path, "w") as f:
                    f.write('''#include "KSystemClockSkewNotifier.h"
#include "moc_KSystemClockSkewNotifier.cpp"
''')
                # 3. Patch CMakeLists.txt
                nl_cmake_path = os.path.join(nl_dir, "CMakeLists.txt")
                if os.path.exists(nl_cmake_path):
                    with open(nl_cmake_path, "r") as f:
                        nl_cmake = f.read()
                    old_target_src = "    main.cpp\n)"
                    new_target_src = "    main.cpp\n    ksystemclockskewnotifier_stub.cpp\n)"
                    if old_target_src in nl_cmake:
                        nl_cmake = nl_cmake.replace(old_target_src, new_target_src)
                    else:
                        nl_cmake = nl_cmake.replace("main.cpp", "main.cpp\n    ksystemclockskewnotifier_stub.cpp")
                    with open(nl_cmake_path, "w") as f:
                        f.write(nl_cmake)
                print("[+] Successfully patched nightlight plugin with KSystemClockSkewNotifier stub.")
            except Exception as e:
                print(f"[-] Failed to patch nightlight plugin with KSystemClockSkewNotifier: {e}")

        # Stub out src/wayland/fixes.cpp because wl_fixes is not supported on older Wayland versions used by SmechOS
        fixes_cpp = os.path.join(build_dir, "src/wayland/fixes.cpp")
        if os.path.exists(fixes_cpp):
            try:
                with open(fixes_cpp, "w", encoding="utf-8") as f:
                    f.write('''#include "fixes.h"

namespace KWin
{

class FixesInterfacePrivate
{
};

FixesInterface::FixesInterface(Display *display, QObject *parent)
    : QObject(parent)
    , d{std::make_unique<FixesInterfacePrivate>()}
{
    (void)display;
}

FixesInterface::~FixesInterface()
{
}

} // namespace KWin
''')
                print("[+] Successfully stubbed fixes.cpp.")
            except Exception as e:
                print(f"[-] Failed to stub fixes.cpp: {e}")

        # Create C++23 compatibility header
        compat_h_dir = os.path.join(build_dir, "src")
        os.makedirs(compat_h_dir, exist_ok=True)
        compat_h_path = os.path.join(compat_h_dir, "smech_cpp23_compat.h")
        try:
            with open(compat_h_path, "w", encoding="utf-8") as f:
                f.write('''#ifndef SMECH_CPP23_COMPAT_H
#define SMECH_CPP23_COMPAT_H

#ifdef __cplusplus
#include <ranges>

#ifndef __cpp_lib_ranges_to_container

#include <QList>
#include <QStringList>
#include <algorithm>

namespace std {
namespace ranges {

template <typename Container>
struct ToTmp {
    template <typename Range>
    friend auto operator|(Range&& r, ToTmp) {
        Container c;
        for (auto&& elem : r) {
            if constexpr (requires { c.append(elem); }) {
                c.append(elem);
            } else {
                c.push_back(elem);
            }
        }
        return c;
    }
};

template <template <typename...> class Container>
struct ToTmpTemplate {
    template <typename Range>
    friend auto operator|(Range&& r, ToTmpTemplate) {
        using ElType = std::ranges::range_value_t<Range>;
        Container<ElType> c;
        for (auto&& elem : r) {
            if constexpr (requires { c.append(elem); }) {
                c.append(elem);
            } else {
                c.push_back(elem);
            }
        }
        return c;
    }
};

template <typename Container>
auto to() {
    return ToTmp<Container>{};
}

template <template <typename...> class Container>
auto to() {
    return ToTmpTemplate<Container>{};
}

} // namespace ranges
} // namespace std

#endif // __cpp_lib_ranges_to_container
#endif // __cplusplus

// Libinput 1.25.0 compatibility stubs
#ifdef __cplusplus
#include <libinput.h>

#ifndef LIBINPUT_EVENT_TABLET_PAD_DIAL
#define LIBINPUT_EVENT_TABLET_PAD_DIAL ((libinput_event_type)31337)
#endif

#ifndef LIBINPUT_LED_COMPOSE
#define LIBINPUT_LED_COMPOSE ((libinput_led)0)
#endif

#ifndef LIBINPUT_LED_KANA
#define LIBINPUT_LED_KANA ((libinput_led)0)
#endif

struct libinput_config_area_rectangle {
    double x1, y1, x2, y2;
};

inline double libinput_event_tablet_pad_get_dial_delta_v120(struct libinput_event_tablet_pad *) { return 0.0; }
inline int libinput_event_tablet_pad_get_dial_number(struct libinput_event_tablet_pad *) { return 0; }
inline int libinput_tablet_tool_config_pressure_range_is_available(struct libinput_tablet_tool *) { return 0; }
inline void libinput_tablet_tool_config_pressure_range_set(struct libinput_tablet_tool *, double, double) {}

inline uint32_t libinput_device_get_id_bustype(struct libinput_device *) { return 0; }
inline int libinput_device_tablet_pad_get_num_dials(struct libinput_device *) { return 0; }
inline int libinput_tablet_pad_mode_group_has_dial(struct libinput_tablet_pad_mode_group *, unsigned int) { return 0; }
inline int libinput_device_config_area_has_rectangle(struct libinput_device *) { return 0; }
inline enum libinput_config_status libinput_device_config_area_set_rectangle(struct libinput_device *, const struct libinput_config_area_rectangle *) {
    return LIBINPUT_CONFIG_STATUS_UNSUPPORTED;
}
#endif

#ifndef WL_KEYBOARD_KEY_STATE_REPEATED
#define WL_KEYBOARD_KEY_STATE_REPEATED 2
#endif
#ifndef WL_KEYBOARD_KEY_STATE_REPEATED_SINCE_VERSION
#define WL_KEYBOARD_KEY_STATE_REPEATED_SINCE_VERSION 31337
#endif

#ifdef __cplusplus
#include <QtCore/qnativeinterface.h>

#ifndef SMECH_QEGLCONTEXT_STUB
#define SMECH_QEGLCONTEXT_STUB

class QOpenGLContext;

#ifndef EGL_VERSION_1_0
typedef void *EGLContext;
typedef void *EGLDisplay;
typedef void *EGLConfig;
#endif

namespace QNativeInterface {
    struct QEGLContext
    {
        QT_DECLARE_NATIVE_INTERFACE(QEGLContext, 1, QOpenGLContext)
        static QOpenGLContext *fromNative(EGLContext context, EGLDisplay display, QOpenGLContext *shareContext = nullptr);
        virtual EGLContext nativeContext() const = 0;
        virtual EGLConfig config() const = 0;
        virtual EGLDisplay display() const = 0;
        virtual void invalidateContext() = 0;
    };
}
#endif
#endif

#endif // SMECH_CPP23_COMPAT_H
''')
            print("[+] Successfully created smech_cpp23_compat.h header.")
        except Exception as e:
            print(f"[-] Failed to create smech_cpp23_compat.h: {e}")

        # Patch CMakeLists.txt to add forced include of smech_cpp23_compat.h
        cmake_lists_path = os.path.join(build_dir, "CMakeLists.txt")
        if os.path.exists(cmake_lists_path):
            try:
                with open(cmake_lists_path, "r", encoding="utf-8") as f:
                    content = f.read()
                old_str = "set(CMAKE_CXX_STANDARD_REQUIRED ON)"
                new_str = "set(CMAKE_CXX_STANDARD_REQUIRED ON)\nadd_compile_options(-include ${CMAKE_SOURCE_DIR}/src/smech_cpp23_compat.h)"
                content = content.replace(old_str, new_str)
                with open(cmake_lists_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched CMakeLists.txt with add_compile_options for C++23 compat.")
            except Exception as e:
                print(f"[-] Failed to patch CMakeLists.txt with compile option: {e}")

        cmake_cmd.extend(["-DKWIN_BUILD_X11=OFF", "-DKWIN_BUILD_SCREENLOCKER=OFF", "-DQT_NO_PACKAGE_VERSION_CHECK=ON"])
    elif name == "plasma-workspace":
        # Create global compat header for plasma-workspace to mock X11 symbols elegantly
        compat_path = os.path.join(build_dir, "smech_plasma_compat.h")
        compat_code = """#ifndef SMECH_PLASMA_COMPAT_H
#define SMECH_PLASMA_COMPAT_H

#ifdef __cplusplus

#if __has_include(<QGuiApplication>)
#include <QGuiApplication>
#include <QObject>
#elif __has_include(<QtGui/QGuiApplication>)
#include <QtGui/QGuiApplication>
#include <QObject>
#endif

#if defined(QT_CORE_LIB) || __has_include(<QObject>) || __has_include(<QtCore/QObject>)

#if !defined(QT_GUI_LIB) && !__has_include(<QGuiApplication>) && !__has_include(<QtGui/QGuiApplication>)
// QtGui is not available in include path, so we don't declare things requiring QGuiApplication
#else

namespace QNativeInterface {
    struct QX11Application {
        struct TypeInfo {
            using baseType = QGuiApplication;
            static constexpr char const *name = "QNativeInterface::QX11Application";
            static constexpr int revision = 1;
        };
        
        template <typename, typename>
        friend struct QNativeInterface::Private::has_type_info;
        
        template <typename>
        friend bool constexpr QNativeInterface::Private::hasTypeInfo();
        
        template <typename>
        friend struct QNativeInterface::Private::TypeInfo;

        virtual ~QX11Application() = default;

        void *display() const { return nullptr; }
        void *connection() const { return nullptr; }
    };
}

#endif // QGuiApplication available

#if __has_include(<netwm_def.h>)
#include <netwm_def.h>
#else

struct NET {
    typedef int Properties;
    typedef int Properties2;
    typedef int WindowTypes;
    typedef int Protocols;
    
    enum WindowType {
        Normal = 1,
        Dialog = 2,
        Utility = 3,
        AppletPopup = 4,
        Menu = 5,
        DropdownMenu = 6,
        PopupMenu = 7,
        Notification = 8,
        CriticalNotification = 9,
        Dock = 10,
        Desktop = 11,
        Override = 12,
        OnScreenDisplay = 13,
        Tooltip = 14,
        Unknown = 15
    };

    static const int WMName = 1;
    static const int WMVisibleName = 2;
    static const int WMIcon = 4;
    static const int WMState = 8;
    static const int XAWMState = 16;
    static const int WMDesktop = 32;
    static const int WMGeometry = 64;
    static const int WMFrameExtents = 128;
    static const int WMWindowType = 256;
    static const int WMPid = 512;
    static const int WM2UserTime = 1;
    static const int WM2DesktopFileName = 2;
    static const int WM2Activities = 4;
    static const int WM2WindowClass = 8;
    static const int WM2AllowedActions = 16;
    static const int WM2AppMenuObjectPath = 32;
    static const int WM2AppMenuServiceName = 64;
    static const int WM2GTKApplicationId = 128;
    static const int WM2TransientFor = 256;
    static const int SkipTaskbar = 1;
    static const int SkipPager = 2;
    static const int SkipSwitcher = 4;
    static const int KeepAbove = 8;
    static const int KeepBelow = 16;
    static const int StaysOnTop = 32;
    static const int DemandsAttention = 64;
    static const int MaxHoriz = 128;
    static const int MaxVert = 256;
    
    static const int NormalMask = 1;
    static const int DesktopMask = 2;
    static const int DockMask = 4;
    static const int ToolbarMask = 8;
    static const int MenuMask = 16;
    static const int DialogMask = 32;
    static const int OverrideMask = 64;
    static const int TopMenuMask = 128;
    static const int UtilityMask = 256;
    static const int SplashMask = 512;
    static const int NotificationMask = 1024;
    static const int AllTypesMask = 2048;
    
    static const int ActionClose = 1;
    static const int ActionMove = 2;
    static const int ActionResize = 3;
    static const int ActionMax = 4;
    static const int ActionMinimize = 5;
    
    static const int Supported = 1;
    static const int SupportingWMCheck = 2;
    static const int CloseWindow = 512;
    static const int WMMoveResize = 1024;
    static const int NumberOfDesktops = 2048;
    static const int DesktopNames = 4096;
    static const int WM2DesktopLayout = 8192;
};

#endif

class NETRootInfo {
public:
    NETRootInfo(void*, int) {}
    NETRootInfo(void*, int, int) {}
};

#endif // QObject / QtCore available

#endif // __cplusplus

#endif // SMECH_PLASMA_COMPAT_H
"""
        with open(compat_path, "w", encoding="utf-8") as f:
            f.write(compat_code)
        print("[+] Created global compatibility header smech_plasma_compat.h")

        # Ensure we modify version constraint of Qt6 in CMakeLists.txt if not already done
        cmake_lists_path = os.path.join(build_dir, "CMakeLists.txt")
        if os.path.exists(cmake_lists_path):
            with open(cmake_lists_path, "r") as f:
                content = f.read()
            content = content.replace('set(QT_MIN_VERSION "6.10.0")', 'set(QT_MIN_VERSION "6.8.2")')
            content = content.replace('pkg_check_modules(SYSTEMD "systemd")', '# pkg_check_modules(SYSTEMD "systemd")')
            
            # Inject compilation options to include our global compatibility header
            inject_options = "\nadd_compile_options(-include /tmp/smechos_build/build-plasma-workspace/smech_plasma_compat.h)\n"
            if "smech_plasma_compat.h" not in content:
                content = content.replace("project(plasma-workspace)", "project(plasma-workspace)" + inject_options)
            
            with open(cmake_lists_path, "w") as f:
                f.write(content)
            print("[+] Successfully patched CMakeLists.txt with add_compile_options for smech_plasma_compat.h")

        # Create KSystemClockSkewNotifier stub and patch CMakeLists.txt in the lookandfeel kded plugin
        laf_dir = os.path.join(build_dir, "kcms/lookandfeel/kded")
        if os.path.exists(laf_dir):
            try:
                # 1. Create stub header (.h) for AUTOMOC
                stub_hdr_h_path = os.path.join(laf_dir, "KSystemClockSkewNotifier.h")
                with open(stub_hdr_h_path, "w") as f:
                    f.write('''#ifndef KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
#define KSYSTEMCLOCKSKEWNOTIFIER_STUB_H

#include <QObject>

class KSystemClockSkewNotifier : public QObject {
    Q_OBJECT
public:
    explicit KSystemClockSkewNotifier(QObject *parent = nullptr) : QObject(parent) {}
    void setActive(bool active) { Q_UNUSED(active); }
Q_SIGNALS:
    void skewed();
};

#endif // KSYSTEMCLOCKSKEWNOTIFIER_STUB_H
''')
                # 2. Create clean forwarder header (no extension) for lookandfeelautoswitcher.h include
                stub_hdr_path = os.path.join(laf_dir, "KSystemClockSkewNotifier")
                with open(stub_hdr_path, "w") as f:
                    f.write('#include "KSystemClockSkewNotifier.h"\n')

                # 3. Create stub .cpp file including the .h and its moc file
                stub_cpp_path = os.path.join(laf_dir, "ksystemclockskewnotifier_stub.cpp")
                with open(stub_cpp_path, "w") as f:
                    f.write('''#include "KSystemClockSkewNotifier.h"
#include "moc_KSystemClockSkewNotifier.cpp"
''')
                # 4. Patch CMakeLists.txt
                laf_cmake_path = os.path.join(laf_dir, "CMakeLists.txt")
                if os.path.exists(laf_cmake_path):
                    with open(laf_cmake_path, "r") as f:
                        laf_cmake = f.read()
                    old_target_src = "    idletimeout.cpp\n    lookandfeelautoswitcher.cpp\n)"
                    new_target_src = "    idletimeout.cpp\n    lookandfeelautoswitcher.cpp\n    ksystemclockskewnotifier_stub.cpp\n)"
                    if old_target_src in laf_cmake:
                        laf_cmake = laf_cmake.replace(old_target_src, new_target_src)
                    else:
                        laf_cmake = laf_cmake.replace("lookandfeelautoswitcher.cpp", "lookandfeelautoswitcher.cpp\n    ksystemclockskewnotifier_stub.cpp")
                    with open(laf_cmake_path, "w") as f:
                        f.write(laf_cmake)

                # 5. Patch lookandfeelautoswitcher.h to use local header include
                laf_h_path = os.path.join(laf_dir, "lookandfeelautoswitcher.h")
                if os.path.exists(laf_h_path):
                    with open(laf_h_path, "r") as f:
                        laf_h = f.read()
                    laf_h = laf_h.replace("#include <KSystemClockSkewNotifier>", '#include "KSystemClockSkewNotifier.h"')
                    with open(laf_h_path, "w") as f:
                        f.write(laf_h)
                print("[+] Successfully patched lookandfeel kded plugin with KSystemClockSkewNotifier stub.")
            except Exception as e:
                print(f"[-] Failed to patch lookandfeel kded plugin with KSystemClockSkewNotifier: {e}")

        # Patch kcms/nighttime/nighttimesettings.kcfg to use type="String" instead of type="Time"
        kcfg_path = os.path.join(build_dir, "kcms/nighttime/nighttimesettings.kcfg")
        if os.path.exists(kcfg_path):
            try:
                with open(kcfg_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace('type="Time"', 'type="String"')
                with open(kcfg_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Successfully patched nighttimesettings.kcfg (changed type='Time' to type='String')")
            except Exception as e:
                print(f"[-] Failed to patch nighttimesettings.kcfg: {e}")

        # Patch CMakeLists.txt files in plasma-workspace to use KF6::I18n instead of KF6::I18nQml
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                if file == "CMakeLists.txt" or file.endswith(".cmake"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        if "KF6::I18nQml" in content:
                            content = content.replace("KF6::I18nQml", "KF6::I18n")
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as e:
                        print(f"[-] Failed to patch I18nQml in {file_path}: {e}")
        # Patch KLocalizedQmlContext and KX11Extras in all plasma-workspace source and header files
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                if file.endswith((".cpp", ".h")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        modified = False
                        if "KLocalizedQmlContext" in content:
                            content = content.replace("KLocalizedQmlContext", "KLocalizedContext")
                            modified = True
                        
                        if "&Solid::StorageAccess::checkRequested" in content:
                            content = content.replace("connect(access, &Solid::StorageAccess::checkRequested", "// connect(access, &Solid::StorageAccess::checkRequested")
                            modified = True
                        if "&Solid::StorageAccess::checkDone" in content:
                            content = content.replace("connect(access, &Solid::StorageAccess::checkDone", "// connect(access, &Solid::StorageAccess::checkDone")
                            modified = True

                        if "KColorScheme::frameContrast(config)" in content:
                            content = content.replace("KColorScheme::frameContrast(config)", "0.2")
                            modified = True
                        if "KColorScheme::frameContrast()" in content:
                            content = content.replace("KColorScheme::frameContrast()", "0.2")
                            modified = True
                        
                        if "runnerManager()->querying()" in content:
                            content = content.replace("runnerManager()->querying()", "false")
                            modified = True
                        if "connect(runnerManager(), &KRunner::RunnerManager::queryingChanged" in content:
                            content = content.replace("connect(runnerManager(), &KRunner::RunnerManager::queryingChanged", "// connect(runnerManager(), &KRunner::RunnerManager::queryingChanged")
                            modified = True
                        
                        if "#include <KX11Extras>" in content:
                            stub_code = """#include <config-X11.h>
#if HAVE_X11
#include <KX11Extras>
#else
#ifndef SM_KX11EXTRAS_STUB
#define SM_KX11EXTRAS_STUB
#include <QObject>
#include <QWindow>
#include <QPixmap>
#include <QStringList>
#include <QList>
class KX11Extras : public QObject {
public:
    static void forceActiveWindow(WId) {}
    template <typename T>
    static void setState(WId, T) {}
    template <typename T>
    static void clearState(WId, T) {}
    static void setOnAllDesktops(WId, bool) {}
    template <typename T>
    static void setType(WId, T) {}
    static void setCurrentDesktop(int) {}
    static void setOnDesktop(WId, int) {}
    static int numberOfDesktops() { return 1; }
    static int currentDesktop() { return 1; }
    static QString desktopName(int) { return QString(); }
    static QList<WId> windows() { return QList<WId>(); }
    static QList<WId> stackingOrder() { return QList<WId>(); }
    static WId activeWindow() { return 0; }
    static QPixmap icon(WId, int, int, bool) { return QPixmap(); }
    static QPixmap icon(WId, int, int) { return QPixmap(); }
    static void minimizeWindow(WId) {}
    static void unminimizeWindow(WId) {}
    static bool compositingActive() { return true; }
    static bool hasWId(WId) { return false; }
    
    // Member functions to support KX11Extras::self()->...
    void activeWindowChanged(WId) {}
    void stackingOrderChanged() {}
    void currentDesktopChanged(int) {}
    void numberOfDesktopsChanged(int) {}
    void desktopNamesChanged() {}
    void compositingChanged() {}

    static KX11Extras *self() { return nullptr; }
};
#endif
#endif"""
                            content = content.replace("#include <KX11Extras>", stub_code)
                            modified = True
                            
                        if "#include <KStartupInfo>" in content:
                            startup_stub = """#include <config-X11.h>
#if HAVE_X11
#include <KStartupInfo>
#else
#ifndef SM_KSTARTUPINFO_STUB
#define SM_KSTARTUPINFO_STUB
#include <QByteArray>
#include <QWindow>
class KStartupInfoId {
public:
    void initId() {}
    QByteArray id() const { return QByteArray(); }
};
class KStartupInfo {
public:
    static void setNewStartupId(QWindow*, const QByteArray&) {}
};
#endif
#endif"""
                            content = content.replace("#include <KStartupInfo>", startup_stub)
                            modified = True
                            
                        if modified:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)
                    except Exception as e:
                        print(f"[-] Failed to patch file {file_path}: {e}")

        # Patch X11-dependent files in plasma-workspace for pure Wayland compilation
        try:
            # 1. logout-greeter/CMakeLists.txt
            lg_cmake = os.path.join(build_dir, "logout-greeter/CMakeLists.txt")
            if os.path.exists(lg_cmake):
                with open(lg_cmake, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("    X11::X11\n", "")
                with open(lg_cmake, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched logout-greeter/CMakeLists.txt (removed X11::X11 link)")

            # 2. logout-greeter/shutdowndlg.cpp
            lg_cpp = os.path.join(build_dir, "logout-greeter/shutdowndlg.cpp")
            if os.path.exists(lg_cpp):
                with open(lg_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                # Comment out X11 includes
                content = content.replace("#include <KX11Extras>", "//#include <KX11Extras>")
                content = content.replace("#include <X11/Xatom.h>", "//#include <X11/Xatom.h>")
                content = content.replace("#include <X11/Xutil.h>", "//#include <X11/Xutil.h>")
                content = content.replace("#include <fixx11h.h>", "//#include <fixx11h.h>")
                # Include missing QJsonDocument
                content = content.replace("#include <QJsonArray>", "#include <QJsonArray>\n#include <QJsonDocument>")
                # Wrap X11 specific platform block in #if 0
                x11_block_start = "    if (KWindowSystem::isPlatformX11()) {"
                if x11_block_start in content:
                    old_block = """    if (KWindowSystem::isPlatformX11()) {
        constexpr auto role = std::string_view("logoutdialog");
        constexpr std::size_t roleLength = role.length();

        auto x11App = qGuiApp->nativeInterface<QNativeInterface::QX11Application>();
        XChangeProperty(x11App->display(),
                        winId(),
                        XInternAtom(x11App->display(), "WM_WINDOW_ROLE", False),
                        XA_STRING,
                        8,
                        PropModeReplace,
                        reinterpret_cast<const unsigned char *>(role.data()),
                        roleLength);

        XClassHint classHint;
        classHint.res_name = const_cast<char *>("ksmserver-logout-greeter");
        classHint.res_class = const_cast<char *>("ksmserver-logout-greeter");
        XSetClassHint(x11App->display(), winId(), &classHint);
        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);
    }"""
                    new_block = """#if 0
    if (KWindowSystem::isPlatformX11()) {
        constexpr auto role = std::string_view("logoutdialog");
        constexpr std::size_t roleLength = role.length();

        auto x11App = qGuiApp->nativeInterface<QNativeInterface::QX11Application>();
        XChangeProperty(x11App->display(),
                        winId(),
                        XInternAtom(x11App->display(), "WM_WINDOW_ROLE", False),
                        XA_STRING,
                        8,
                        PropModeReplace,
                        reinterpret_cast<const unsigned char *>(role.data()),
                        roleLength);

        XClassHint classHint;
        classHint.res_name = const_cast<char *>("ksmserver-logout-greeter");
        classHint.res_class = const_cast<char *>("ksmserver-logout-greeter");
        XSetClassHint(x11App->display(), winId(), &classHint);
        KX11Extras::setState(winId(), NET::SkipTaskbar | NET::SkipPager | NET::SkipSwitcher);
    }
#endif"""
                    content = content.replace(old_block, new_block)
                
                # Replace KX11Extras check in resizeEvent
                content = content.replace("    if (KX11Extras::compositingActive()) {", "    if (true) { // Wayland compositing always active")
                with open(lg_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched logout-greeter/shutdowndlg.cpp (commented out X11 symbols)")

            # 3. kcms/krdb/CMakeLists.txt
            krdb_cmake = os.path.join(build_dir, "kcms/krdb/CMakeLists.txt")
            if os.path.exists(krdb_cmake):
                with open(krdb_cmake, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace(" X11::X11 ", " ")
                with open(krdb_cmake, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched kcms/krdb/CMakeLists.txt (removed X11::X11 link)")

            # 4. kcms/colors/CMakeLists.txt
            colors_cmake = os.path.join(build_dir, "kcms/colors/CMakeLists.txt")
            if os.path.exists(colors_cmake):
                with open(colors_cmake, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("    X11::X11\n", "")
                with open(colors_cmake, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched kcms/colors/CMakeLists.txt (removed X11::X11 links)")

            # 5. appmenu/menuimporter.cpp
            menu_cpp = os.path.join(build_dir, "appmenu/menuimporter.cpp")
            if os.path.exists(menu_cpp):
                with open(menu_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("#include <KWindowInfo>", "//#include <KWindowInfo>")
                # Wrap KWindowInfo block in #if 0
                old_reg = """    if (KWindowSystem::isPlatformX11()) {
        KWindowInfo info(id, NET::WMWindowType, NET::WM2WindowClass);
        NET::WindowTypes mask = NET::AllTypesMask;
        auto type = info.windowType(mask);

        // Menu can try to register, right click in gimp for example
        if (type != NET::Unknown && (type & (NET::Menu | NET::DropdownMenu | NET::PopupMenu))) {
            return;
        }
        m_windowClasses.insert(id, QString::fromLocal8Bit(info.windowClassClass()));
    }"""
                new_reg = """#if 0
    if (KWindowSystem::isPlatformX11()) {
        KWindowInfo info(id, NET::WMWindowType, NET::WM2WindowClass);
        NET::WindowTypes mask = NET::AllTypesMask;
        auto type = info.windowType(mask);

        // Menu can try to register, right click in gimp for example
        if (type != NET::Unknown && (type & (NET::Menu | NET::DropdownMenu | NET::PopupMenu))) {
            return;
        }
        m_windowClasses.insert(id, QString::fromLocal8Bit(info.windowClassClass()));
    }
#endif"""
                content = content.replace(old_reg, new_reg)
                with open(menu_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched appmenu/menuimporter.cpp (commented out KWindowInfo)")

            # 6. gmenu-dbusmenu-proxy/menuproxy.cpp
            proxy_cpp = os.path.join(build_dir, "gmenu-dbusmenu-proxy/menuproxy.cpp")
            if os.path.exists(proxy_cpp):
                with open(proxy_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("#include <KWindowInfo>", "//#include <KWindowInfo>")
                # Wrap KWindowInfo block in #if 0
                old_proxy_reg = """    if (KWindowSystem::isPlatformX11()) {
        KWindowInfo info(id, NET::WMWindowType);

        NET::WindowType wType = info.windowType(NET::NormalMask | NET::DesktopMask | NET::DockMask | NET::ToolbarMask | NET::MenuMask | NET::DialogMask
                                                | NET::OverrideMask | NET::TopMenuMask | NET::UtilityMask | NET::SplashMask);

        // Only top level windows typically have a menu bar, dialogs, such as settings don't
        if (wType != NET::Normal) {
            qCDebug(DBUSMENUPROXY) << "Ignoring window" << id << "of type" << wType;
            return;
        }
    }"""
                new_proxy_reg = """#if 0
    if (KWindowSystem::isPlatformX11()) {
        KWindowInfo info(id, NET::WMWindowType);

        NET::WindowType wType = info.windowType(NET::NormalMask | NET::DesktopMask | NET::DockMask | NET::ToolbarMask | NET::MenuMask | NET::DialogMask
                                                | NET::OverrideMask | NET::TopMenuMask | NET::UtilityMask | NET::SplashMask);

        // Only top level windows typically have a menu bar, dialogs, such as settings don't
        if (wType != NET::Normal) {
            qCDebug(DBUSMENUPROXY) << "Ignoring window" << id << "of type" << wType;
            return;
        }
    }
#endif"""
                content = content.replace(old_proxy_reg, new_proxy_reg)
                with open(proxy_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched gmenu-dbusmenu-proxy/menuproxy.cpp (commented out KWindowInfo)")

            # 7. libtaskmanager/virtualdesktopinfo.cpp
            vd_cpp = os.path.join(build_dir, "libtaskmanager/virtualdesktopinfo.cpp")
            if os.path.exists(vd_cpp):
                with open(vd_cpp, "r", encoding="utf-8") as f:
                    content = f.read()
                # Patch X11Info::connection()
                old_conn = """namespace X11Info
{
[[nodiscard]] inline auto connection()
{
    return qGuiApp->nativeInterface<QNativeInterface::QX11Application>()->connection();
}
}"""
                new_conn = """struct xcb_connection_t;
namespace X11Info
{
[[nodiscard]] inline auto connection()
{
#if HAVE_X11
    return qGuiApp->nativeInterface<QNativeInterface::QX11Application>()->connection();
#else
    return (xcb_connection_t*)nullptr;
#endif
}
}"""
                content = content.replace(old_conn, new_conn)
                with open(vd_cpp, "w", encoding="utf-8") as f:
                    f.write(content)
                print("[+] Patched libtaskmanager/virtualdesktopinfo.cpp (added X11Info::connection fallback)")
        except Exception as e:
            print(f"[-] Failed to apply X11 bypass patches: {e}")

        cmake_cmd.extend(["-DWITH_X11=OFF", "-DWITH_X11_SESSION=OFF", "-DBUILD_xembed-sni-proxy=OFF"])


    res = subprocess.run(cmake_cmd, cwd=build_dir, env=env)
    if res.returncode != 0:
        print(f"[-] Configure failed for {name}")
        sys.exit(1)
        
    # 4. Compile source (-j3 to protect WSL memory/prevent OOM)
    print(f"[+] Compiling {name}...")
    build_cmd = ["cmake", "--build", "build_dir", "-j3"]
    res = subprocess.run(build_cmd, cwd=build_dir, env=env)
    if res.returncode != 0:
        print(f"[-] Build failed for {name}")
        sys.exit(1)
        
    # 5. Install source
    print(f"[+] Installing {name}...")
    install_cmd = ["cmake", "--install", "build_dir"]
    # Run with sudo and preserve env paths
    sudo_install_cmd = ["sudo", f"PATH={env['PATH']}", f"LD_LIBRARY_PATH={env['LD_LIBRARY_PATH']}", f"HOME={env['HOME']}", f"DESTDIR={SMECH_TARGET}"] + install_cmd

    proc = subprocess.Popen(sudo_install_cmd, cwd=build_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    
    if proc.returncode != 0:
        print(f"[-] Installation failed for {name}")
        print("Stdout:", stdout)
        print("Stderr:", stderr)
        sys.exit(1)
        
    print(f"[+] {name} built and installed successfully!")

    # Post-process QCA absolute paths so CMake can find it on the host during compilation
    if name == "qca":
        print("[+] Post-processing QCA installation to fix absolute cmake target paths...")
        patch_script = f"""
import os
cmake_dir = "{SMECH_TARGET}/usr/lib/cmake/Qca-qt6"
if not os.path.exists(cmake_dir):
    cmake_dir = "{SMECH_TARGET}/usr/lib/x86_64-linux-gnu/cmake/Qca-qt6"
if os.path.exists(cmake_dir):
    for f in os.listdir(cmake_dir):
        if f.endswith(".cmake"):
            path = os.path.join(cmake_dir, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
            content = content.replace('\\"/usr', '\\"{SMECH_TARGET}/usr')
            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
"""
        proc_patch = subprocess.Popen(["sudo", "python3", "-c", patch_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc_patch.communicate()
        if proc_patch.returncode == 0:
            print("[+] QCA cmake target paths successfully patched!")
        else:
            print("[-] Failed to patch QCA cmake target paths:", err)

print("\n[+] === ALL KDE & CALAMARES COMPONENTS BUILT AND INSTALLED SUCCESSFULLY! ===")
