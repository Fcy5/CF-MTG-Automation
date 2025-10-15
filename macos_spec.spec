# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 设置输出目录
dist_dir = os.path.abspath('dist')
work_dir = os.path.abspath('build')

# 处理模板文件
templates_files = []
templates_dir = os.path.abspath('templates')
if os.path.exists(templates_dir):
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('templates', os.path.relpath(root, templates_dir))
            templates_files.append((src, dest))

# 处理静态资源
statics_files = []
statics_dir = os.path.abspath('statics')
if os.path.exists(statics_dir):
    for root, dirs, files in os.walk(statics_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('statics', os.path.relpath(root, statics_dir))
            statics_files.append((src, dest))

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=templates_files + statics_files,
    hiddenimports=[
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3',
        'werkzeug.formparser', 'werkzeug.datastructures',
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',
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

# 使用COLLECT收集文件（onedir模式）
coll = COLLECT(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='CF_MTG_Automation',  # 使用英文名称避免编码问题
    strip=False,
    upx=False,
)

# 生成.app应用包
app = BUNDLE(
    coll,
    name='CF-MTG Automation.app',  # 应用包名称
    icon=None,
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'CFBundleName': 'CF-MTG Automation',
        'CFBundleDisplayName': 'CF-MTG Automation',
        'CFBundleExecutable': 'CF_MTG_Automation',
        'CFBundleIdentifier': 'com.qlapp.ClickFlareTool',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'LSMinimumSystemVersion': '10.15',
    },
    distpath=dist_dir,
)