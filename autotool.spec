# PyInstaller spec file for AutoTool
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = Path(__file__).parent
entry_script = project_root / 'core' / 'downloadTool' / 'mainGUI.py'

# Collect hidden imports (selenium sometimes dynamic)
hiddenimports = []
try:
    hiddenimports.extend(collect_submodules('selenium'))
except Exception:
    pass
for m in ['pywinauto', 'pyperclip', 'uiautomation']:
    try:
        hiddenimports.extend(collect_submodules(m))
    except Exception:
        pass

# Data files to bundle (text templates, json)
datas = []

def add_datas(pattern, target_subdir):
    for p in project_root.glob(pattern):
        if p.is_file():
            datas.append((str(p), str(Path(target_subdir))))

add_datas('core/downloadTool/*.txt', 'core/downloadTool')
add_datas('core/*.json', 'core')

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='AutoTool',
    debug=False,
    strip=False,
    upx=True,
    console=False,  # Change to True if you want a console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'icon.ico') if (project_root / 'icon.ico').exists() else None,
)
