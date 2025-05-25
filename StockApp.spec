# StockApp.spec  –  tüm proje içeriğini dahil eder
# -------------------------------------------------

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

APP_NAME   = "StockApp"
ENTRY_FILE = "app.py"
ICON_FILE  = "resources/app.ico"          # yoksa bu satırı silin

# 1) Qt platform plug-in'i     (qwindows.dll + ICU)
qt_datas = collect_data_files("PyQt6", subdir="Qt6/plugins/platforms")
qt_bins  = collect_dynamic_libs("PyQt6", "Qt6/plugins/platforms")

# 2) Proje kökündeki **HER ŞEY**
#    ( .venv , .git , __pycache__ , build , dist   hariç)
def project_datas():
    root = Path.cwd()
    skip = {".venv", ".git", "build", "dist", "__pycache__"}
    for p in root.rglob("*"):
        if p.is_dir() or any(tok in p.parts for tok in skip):
            continue
        rel = p.relative_to(root)                # projeye göre görece yol
        yield (str(p), str(rel.parent))           # (kaynak , hedef klasör)

extra_datas = list(project_datas())

# -------------------------------------------------
a = Analysis(
    [ENTRY_FILE],
    pathex=[str(Path.cwd())],
    binaries=qt_bins,
    datas=qt_datas + extra_datas,
    hiddenimports=[],                # standart hook'lar yeter
    excludes=[
        # dev/test paketleri
        "pytest", "pandas.tests",
        # ağır Qt modülleri (kullanmıyoruz)
        "PyQt6.Qt3DCore", "PyQt6.Qt3DRender", "PyQt6.Qt3DAnimation",
        "PyQt6.Qt3DExtras", "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineQuick",
        "PyQt6.QtWebView", "PyQt6.QtScxml", "PyQt6.QtSql",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name        = APP_NAME,
    icon        = ICON_FILE if Path(ICON_FILE).exists() else None,
    console     = False,     # GUI
    upx         = True,
    debug       = False,
)
