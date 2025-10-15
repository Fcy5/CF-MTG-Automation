# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 1. 处理模板文件（templates）- 兼容空文件夹
templates_files = []
templates_dir = os.path.abspath('templates')
if os.path.exists(templates_dir):
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('templates', os.path.relpath(root, templates_dir))
            templates_files.append((src, dest))

# 2. 处理静态资源文件（statics）- 与实际文件夹名一致
statics_files = []
statics_dir = os.path.abspath('statics')
if os.path.exists(statics_dir):
    for root, dirs, files in os.walk(statics_dir):
        for file in files:
            src = os.path.join(root, file)
            dest = os.path.join('statics', os.path.relpath(root, statics_dir))
            statics_files.append((src, dest))

a = Analysis(
    ['app.py'],  # 入口文件，确保路径正确
    pathex=[os.path.abspath('.')],  # 项目根目录
    binaries=[],
    datas=templates_files + statics_files,  # 合并模板+静态资源
    hiddenimports=[
        # Flask/Web核心依赖
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3',
        # 文件上传依赖
        'werkzeug.formparser', 'werkzeug.datastructures',
        # Mac原生依赖（避免闪退）
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',
        # 系统基础依赖
        'tempfile', 'os', 'sys', 'io',
        'json', 'datetime', 'threading', 'socket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],  # 排除无用依赖
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
        name='Cf-Mtg广告克隆工具',  # EXE名称（与.app前缀一致）
        onefile=False,  # 关键：显式用onedir模式，兼容macOS .app
        debug=True,
        strip=False,
        upx=False,  # 关闭压缩，避免原生库损坏
        console=True,  # 保留控制台，方便调试
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch='arm64',  # 适配M芯片（Intel芯片改为x86_64）
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='Cf-Mtg广告克隆工具.app',  # 最终生成的.app名称（检查脚本需与此一致）
    bundle_identifier='com.qlapp.ClickFlareTool',  # 唯一标识（自定义）
    info_plist={
        'NSHighResolutionCapable': 'True',  # 支持高分屏
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},  # 允许HTTP请求
        # 文件访问权限（避免闪退）
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'LSMinimumSystemVersion': '10.15',  # 最低支持macOS 10.15
    },
)