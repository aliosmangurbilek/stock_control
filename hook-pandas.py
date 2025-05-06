"""
hook-pandas.py
PyInstaller için Pandas bağımlılıklarını tanımlayan hook dosyası.
Bu, Excel dosyalarını yazmak için openpyxl'i içermeyi sağlar.
"""

from PyInstaller.utils.hooks import collect_submodules

# Excel desteği için gerekli modülleri dahil et
hiddenimports = [
    'pandas.io.excel._openpyxl',
    'openpyxl',
    'openpyxl.cell',
    'openpyxl.workbook'
]
