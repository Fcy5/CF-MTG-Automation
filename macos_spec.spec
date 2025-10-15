# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

project_root = os.path.abspath('.')
dist_dir = os.path.join(project_root, 'dist')
work_dir = os.path.join(project_root, 'build')

# 处理模板文件（保持原逻辑，确保dest正确）
templates_files = []
templates_dir = os.path.join(project_root, 'templates')
if os.path.exists(templates_dir):
    print(f"[INFO] 发现templates目录：{templates_dir}")
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            # dest格式：打包后放在 "templates/文件名"，与代码预期一致
            dest = os.path.join('templates', os.path.relpath(src, templates_dir))
            templates_files.append((src, dest))
            print(f"[INFO] 加入模板资源：{src} → {dest}")
else:
    print(f"[ERROR] 未找到templates目录：{templates_dir}")

# 处理静态资源（同上）
statics_files = []
statics_dir = os.path.join(project_root, 'statics')
if os.path.exists(statics_dir):
    print(f"[INFO] 发现statics目录：{statics_dir}")
    for root, dirs, files in os.walk(statics_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('statics', os.path.relpath(src, statics_dir))
            statics_files.append((src, dest))
            print(f"[INFO] 加入静态资源：{src} → {dest}")
else:
    print(f"[ERROR] 未找到statics目录：{statics_dir}")

a = Analysis(
    ['app.py'],
    pathex=[project_root],
    binaries=[],
    datas=templates_files + statics_files,  # 资源已正确配置
    hiddenimports=[
        # 保留原有隐藏导入，但删除不存在的模块（避免报错）
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3',  # 替换掉错误的requests.packages.urllib3.util
        'werkzeug.formparser', 'werkzeug.datastructures',
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',  # 保留webview核心模块，删除不存在的util/js
        'proxy_tools', 'bottle',
        'hashlib', 're', 'csv', 'urllib3.util',  # 补充urllib3.util
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 关键1：改为Onedir模式（exclude_binaries=True，不把资源打包进EXE）
exe = EXE(
    pyz,
    a.scripts,
    [],  # 空列表，排除binaries
    exclude_binaries=True,  # 核心：二进制和资源单独存放
    name='CF_MTG_Automation',
    debug=True,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

# 关键2：BUNDLE中包含exe、binaries和datas，形成完整目录结构
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CF_MTG_Automation_Collect',
)

app = BUNDLE(
    coll,  # 用COLLECT的结果，包含所有资源
    name='CF-MTG Automation.app',
    icon=None,
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'CFBundleName': 'CF-MTG Automation',
        'CFBundleDisplayName': 'CF-MTG Automation',
        'CFBundleExecutable': 'CF_MTG_Automation',  # 与EXE名称一致
        'CFBundleIdentifier': 'com.qlapp.ClickFlareTool',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'NSFileSystemUsageDescription': '需要访问文件系统以加载模板资源',
        'NSAppleEventsUsageDescription': '需要访问文件系统以加载模板资源'
        'LSMinimumSystemVersion': '10.15',
    },
    distpath=dist_dir,
)