# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 处理模板文件（templates）
templates_files = []
templates_dir = os.path.abspath('templates')
if os.path.exists(templates_dir):
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            # 保持相对路径结构，打包后放在templates目录下
            dest = os.path.join('templates', os.path.relpath(root, templates_dir))
            templates_files.append((src, dest))

# 新增：处理静态资源文件夹（static）
static_files = []
static_dir = os.path.abspath('static')  # 假设静态资源放在static文件夹
if os.path.exists(static_dir):
    for root, dirs, files in os.walk(static_dir):
        for file in files:
            src = os.path.join(root, file)
            # 保持相对路径结构，打包后放在static目录下
            dest = os.path.join('static', os.path.relpath(root, static_dir))
            static_files.append((src, dest))

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    # 合并模板文件和静态资源文件
    datas=templates_files + static_files,
    hiddenimports=[
        # Flask/Web核心依赖
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3',

        # 文件上传相关依赖
        'werkzeug.formparser', 'werkzeug.datastructures',

        # Mac原生依赖
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',

        # 系统基础依赖
        'tempfile', 'os', 'sys', 'io',
        'json', 'datetime', 'threading', 'socket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

app = BUNDLE(
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='ClickFlare工具',
        debug=False,
        strip=False,
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch='arm64',
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='ClickFlare工具.app',
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'LSMinimumSystemVersion': '10.15',
    },
)
