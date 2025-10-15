# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 修复1：明确项目根目录，避免路径计算错误
project_root = os.path.abspath('.')
dist_dir = os.path.join(project_root, 'dist')
work_dir = os.path.join(project_root, 'build')

# 处理模板文件（保持原逻辑，新增日志打印）
templates_files = []
templates_dir = os.path.join(project_root, 'templates')
if os.path.exists(templates_dir):
    print(f"[INFO] 发现templates目录：{templates_dir}")
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            src = os.path.join(root, file)
            # 修复2：确保目标路径与代码中get_base_path的预期一致
            # 代码中打包后资源路径是 sys._MEIPASS/statics，此处dest需保持“statics/文件名”格式
            dest = os.path.join('templates', os.path.relpath(src, templates_dir))
            templates_files.append((src, dest))
            print(f"[INFO] 加入模板资源：{src} → {dest}")
else:
    print(f"[WARNING] 未找到templates目录：{templates_dir}")

# 处理静态资源（同上，新增日志打印）
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
    print(f"[WARNING] 未找到statics目录：{statics_dir}")

a = Analysis(
    ['app.py'],  # 确保入口文件路径正确（若app.py在子目录需调整）
    pathex=[project_root],  # 修复3：添加项目根目录到路径
    binaries=[],
    datas=templates_files + statics_files,
    hiddenimports=[
        # 原有依赖（保持不变）
        'flask', 'flask.json', 'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.middleware.dispatcher',
        'requests', 'urllib3', 'werkzeug.formparser', 'werkzeug.datastructures',
        'objc', 'Foundation', 'Cocoa', 'WebKit',
        'webview', 'webview.platforms.cocoa',
        'proxy_tools', 'bottle',
        'requests.adapters', 'requests.packages.urllib3.util',
        'hashlib', 're', 'csv',
        # 新增：打包后可能缺失的PyWebView依赖
        'webview.platforms.cocoa.util',
        'webview.platforms.cocoa.js',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],  # 排除无用依赖，减小包体积
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
        name='CF_MTG_Automation',  # 与info_plist中的CFBundleExecutable一致
        debug=True,  # 打包后保留调试日志（发布时可改为False）
        strip=False,  # 不剥离符号表，方便调试
        upx=False,  # 禁用UPX压缩，避免部分依赖压缩后报错
        console=True,  # 显示控制台窗口（调试用，发布时可改为False）
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch='arm64',  # 匹配GitHub Actions的macos-latest架构
        codesign_identity=None,
        entitlements_file=None,
    ),
    name='CF-MTG Automation.app',  # 应用名称（与workflow中一致）
    bundle_identifier='com.qlapp.ClickFlareTool',
    info_plist={
        'CFBundleName': 'CF-MTG Automation',
        'CFBundleDisplayName': 'CF-MTG Automation',
        'CFBundleExecutable': 'CF_MTG_Automation',  # 与EXE的name一致
        'CFBundleIdentifier': 'com.qlapp.ClickFlareTool',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,  # 修复4：用布尔值而非字符串
        'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},  # 允许HTTP请求
        'NSPhotoLibraryUsageDescription': '需要访问照片库以上传素材',
        'NSDocumentsFolderUsageDescription': '需要处理上传的文件',
        'NSDesktopFolderUsageDescription': '需要访问桌面文件',
        'NSDownloadsFolderUsageDescription': '需要访问下载文件夹以保存日志和CSV',
        'LSMinimumSystemVersion': '10.15',  # 最低支持macOS Catalina
    },
    distpath=dist_dir,
)