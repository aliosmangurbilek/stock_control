"""
reports.py
Günlük satış verilerini Excel dosyasına aktarır.
"""

from datetime import date                       # ISO format :contentReference[oaicite:0]{index=0}
import pandas as pd                             # DataFrame & to_excel :contentReference[oaicite:1]{index=1}
from models import DatabaseManager


def export_daily_sales(db: DatabaseManager,
                       path: str | None = None) -> str | None:
    """
    Günümüz satışlarını `path`'teki .xlsx dosyasına yazar.
    Parametre verilmezse dosya adı `satis_YYYY‑MM‑DD.xlsx` olur.
    Dönüş: kaydedilen dosyanın tam adı veya satış yoksa None.
    """
    rows = db.daily_sales_report()
    if not rows:
        return None

    # DataFrame oluştur → Excel'e yaz  (pandas+openpyxl) :contentReference[oaicite:2]{index=2}
    df = pd.DataFrame(rows, columns=["Ürün", "Satış Adedi", "Gelir"])
    filename = path or f"satis_{date.today().isoformat()}.xlsx"     # isoformat :contentReference[oaicite:3]{index=3}
    df.to_excel(filename, index=False)                              # to_excel :contentReference[oaicite:4]{index=4}
    return filename
