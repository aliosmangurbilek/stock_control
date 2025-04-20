"""
models.py
Veri katmanı: SQLite bağlantısı ve CRUD işlemleri.
"""

import sqlite3                    # Python yerleşik SQLite modülü :contentReference[oaicite:0]{index=0}
from datetime import datetime, date
from pathlib import Path
from typing import List, Tuple, Optional, Any

# ✓ Uygulama kök dizininde /data/inventory.db dosyası oluşturur
DB_PATH = Path(__file__).resolve().parent / "data" / "inventory.db"
DB_PATH.parent.mkdir(exist_ok=True)

class DatabaseManager:
    """SQLite tabanlı basit DAO (Data‑Access Object)."""

    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()     # tablo yoksa oluştur

    # ---------- Şema --------------------------------------------------
    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        # Ürün tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS Product (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                barcode     TEXT    UNIQUE,
                location    TEXT,
                unit_price  REAL    DEFAULT 0.0,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Stok hareketleri
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS StockMovement (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER REFERENCES Product (id),
                change      INTEGER,
                reason      TEXT    CHECK(reason IN ('SALE','PURCHASE','ADJUST')),
                timestamp   TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    # ---------- CRUD: Product ----------------------------------------
    def add_product(self, name: str, barcode: str,
                    location: str, unit_price: float) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO Product(name, barcode, location, unit_price)"
            " VALUES (?,?,?,?)",
            (name, barcode, location, unit_price),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_products(self) -> List[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM Product").fetchall()

    def find_product_by_barcode(self, code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM Product WHERE barcode=?", (code,)
        ).fetchone()
        
    def delete_product(self, product_id: int) -> bool:
        """
        Ürünü ve ilişkili tüm stok hareketlerini siler.
        Dönüş: İşlem başarılıysa True, değilse False
        """
        try:
            cur = self.conn.cursor()
            # Önce ilişkili stok hareketlerini sil (foreign key)
            cur.execute("DELETE FROM StockMovement WHERE product_id=?", (product_id,))
            # Sonra ürünü sil
            cur.execute("DELETE FROM Product WHERE id=?", (product_id,))
            self.conn.commit()
            return cur.rowcount > 0  # Silinen satır varsa True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    # ---------- Stok işlemleri ---------------------------------------
    def change_stock(self, product_id: int, qty: int,
                     reason: str = "SALE") -> None:
        self.conn.execute(
            "INSERT INTO StockMovement(product_id, change, reason)"
            " VALUES (?,?,?)",
            (product_id, qty, reason),
        )
        self.conn.commit()

    def get_stock_level(self, product_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(change),0) AS qty"
            " FROM StockMovement WHERE product_id=?",
            (product_id,),
        ).fetchone()
        return row["qty"] if row else 0

    # ---------- Günlük satış raporu ----------------------------------
    def daily_sales_report(self) -> List[Tuple[Any, ...]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT p.name,
                   SUM(CASE WHEN sm.change<0 THEN -sm.change ELSE 0 END)
                        AS sold_qty,
                   SUM(CASE WHEN sm.change<0
                            THEN -sm.change*p.unit_price ELSE 0 END)
                        AS revenue
            FROM StockMovement sm
            JOIN Product p ON p.id = sm.product_id
            WHERE DATE(sm.timestamp) = DATE('now', 'localtime')
            GROUP BY p.id
            ORDER BY sold_qty DESC;
            """
        )                         # sorgu örnekleri :contentReference[oaicite:1]{index=1}
        return cur.fetchall()

    # ---------- Kapat -------------------------------------------------
    def close(self):
        self.conn.close()
