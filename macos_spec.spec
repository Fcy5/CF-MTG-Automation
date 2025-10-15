# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 明确指定打包输出目录（避免默认路径歧义）
dist_dir = os.path.abspath('dist')  # 最终产物目录
work_dir = os.path.abspath('build')  # 临时工作目录

# 处理模板文件（templates）
templates_files = []
templates_dir = os.path.abspath('templates')
if os.path.exists(templates_dir):
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('templates', os.path.relpath(root, templates_dir))
            templates_files.append((src, dest))

# 处理静态资源文件夹（statics）
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

# 生成EXE（onedir模式，默认）
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='CF-MTG杀毒克隆工具',
    debug=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

# 生成.app捆绑包，显式指定输出目录
app = BUNDLE(
    exe,
    name='CF-MTG杀毒克隆工具.app',
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
    # 显式指定输出目录（与dist_dir一致）
    distpath=dist_dir,
)
