"""
hook-PyQt6.py
PyInstaller için PyQt6 bağımlılıklarını tanımlayan hook dosyası.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# PyQt6'nın tüm alt modüllerini dahil et
hiddenimports = collect_submodules('PyQt6')

# PyQt6 veri dosyalarını dahil et
datas = collect_data_files('PyQt6')
