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


# 保留并修改BUNDLE部分：
app = BUNDLE(
    COLLECT(  # 使用COLLECT替代EXE
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='CF-MTG杀毒克隆工具',
        strip=False,
        upx=False,
    ),
    name='CF-MTG杀毒克隆工具.app',
    icon=None,  # 可添加图标路径如'icon.icns'
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹',
        'LSMinimumSystemVersion': '10.15',
        # 添加CFBundleExecutable
        'CFBundleExecutable': 'CF-MTG杀毒克隆工具',
    },
    distpath=dist_dir,
)