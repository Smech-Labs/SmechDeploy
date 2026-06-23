import os

h_path = "/mnt/smechos_build_root/usr/include/KF6/KCoreAddons/kpluginmetadata.h"
if not os.path.exists(h_path):
    print(f"Error: {h_path} does not exist.")
    exit(1)

with open(h_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    'QString value(const QString &key, const QString &defaultValue = QString()) const;': 
    'QString value(const QString &key, const QString &defaultValue = QString()) const;\\n    inline QString value(const char16_t *key, const QString &defaultValue = QString()) const { return value(QString::fromUtf16(key), defaultValue); }\\n    inline QString value(const char16_t *key, const char16_t *defaultValue) const { return value(QString::fromUtf16(key), QString::fromUtf16(defaultValue)); }',
    
    'bool value(const QString &key, bool defaultValue) const;':
    'bool value(const QString &key, bool defaultValue) const;\\n    inline bool value(const char16_t *key, bool defaultValue) const { return value(QString::fromUtf16(key), defaultValue); }',
    
    'int value(const QString &key, int defaultValue) const;':
    'int value(const QString &key, int defaultValue) const;\\n    inline int value(const char16_t *key, int defaultValue) const { return value(QString::fromUtf16(key), defaultValue); }',
    
    'QStringList value(const QString &key, const QStringList &defaultValue) const;':
    'QStringList value(const QString &key, const QStringList &defaultValue) const;\\n    inline QStringList value(const char16_t *key, const QStringList &defaultValue) const { return value(QString::fromUtf16(key), defaultValue); }'
}

for old, new_val in replacements.items():
    new = new_val.replace('\\\\n', '\\n').replace('\\n', '\n')
    if old in content:
        if new in content:
            print(f"Already patched: {old}")
        else:
            content = content.replace(old, new)
            print(f"Patched: {old}")
    else:
        print(f"Could not find: {old}")

with open(h_path, "w", encoding="utf-8") as f:
    f.write(content)
print("kpluginmetadata.h patching completed successfully!")
