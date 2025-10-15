# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

project_root = os.path.abspath('.')
dist_dir = os.path.join(project_root, 'dist')
work_dir = os.path.join(project_root, 'build')

# ========== 修复1：模板文件配置（dest仅为目标目录） ==========
templates_files = []
templates_dir = os.path.join(project_root, 'templates')
if os.path.exists(templates_dir):
    print(f"[INFO] 发现templates目录：{templates_dir}")
    # 遍历templates目录下所有文件（含子目录）
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src_file = os.path.join(root, file)  # 源：具体文件路径
            # 目标目录：保持原目录结构（如templates/subdir → 目标subdir）
            # 计算相对于templates_dir的子目录路径（无则为空）
            relative_dir = os.path.relpath(root, templates_dir)
            # 最终目标目录：templates/relative_dir（relative_dir为空时就是templates）
            dest_dir = os.path.join('templates', relative_dir) if relative_dir != '.' else 'templates'
            templates_files.append((src_file, dest_dir))  # 关键：dest是目录，不是文件
            print(f"[INFO] 模板资源映射：{src_file} → {dest_dir}/（自动保留文件名）")
else:
    print(f"[ERROR] 未找到templates目录：{templates_dir}")

# ========== 修复2：静态资源配置（同模板逻辑） ==========
statics_files = []
statics_dir = os.path.join(project_root, 'statics')
if os.path.exists(statics_dir):
    print(f"[INFO] 发现statics目录：{statics_dir}")
    for root, dirs, files in os.walk(statics_dir):
        for file in files:
            src_file = os.path.join(root, file)
            relative_dir = os.path.relpath(root, statics_dir)
            dest_dir = os.path.join('statics', relative_dir) if relative_dir != '.' else 'statics'
            statics_files.append((src_file, dest_dir))
            print(f"[INFO] 静态资源映射：{src_file} → {dest_dir}/（自动保留文件名）")
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
        'NSAppleEventsUsageDescription': '需要访问文件系统以加载模板资源',
        'LSMinimumSystemVersion': '10.15',
    },
    distpath=dist_dir,
)