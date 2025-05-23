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
        self.db_path = db_path
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
                initial_price REAL  DEFAULT 0.0,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Mevcut bir tablo varsa initial_price sütununu ekle
        try:
            cur.execute("SELECT initial_price FROM Product LIMIT 1")
        except sqlite3.OperationalError:
            # initial_price sütunu yoksa ekle
            cur.execute("ALTER TABLE Product ADD COLUMN initial_price REAL DEFAULT 0.0")
            # Varolan ürünler için initial_price'ı unit_price ile aynı yap
            cur.execute("UPDATE Product SET initial_price = unit_price WHERE initial_price = 0.0")

        # Stok hareketleri
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS StockMovement (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER REFERENCES Product (id),
                change      INTEGER,
                reason      TEXT    CHECK(reason IN ('SALE','PURCHASE','ADJUST')),
                purchase_price REAL DEFAULT NULL,
                timestamp   TEXT    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Mevcut bir tablo varsa purchase_price sütununu ekle
        try:
            cur.execute("SELECT purchase_price FROM StockMovement LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE StockMovement ADD COLUMN purchase_price REAL DEFAULT NULL")
        
        self.conn.commit()

    # ---------- Veritabanı Yönetimi -----------------------------------
    def refresh_connection(self):
        """Veritabanı bağlantısını yeniler"""
        try:
            # Mevcut bağlantıyı kapat
            self.conn.close()
            # Bağlantıyı yeniden aç
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            return True
        except sqlite3.Error:
            return False

    # ---------- CRUD: Product ----------------------------------------
    def add_product(self, name: str, barcode: str,
                    location: str, unit_price: float) -> int:
        cur = self.conn.cursor()
        # initial_price ile unit_price aynı değere sahip olacak ilk başta
        cur.execute(
            "INSERT INTO Product(name, barcode, location, unit_price, initial_price)"
            " VALUES (?,?,?,?,?)",
            (name, barcode, location, unit_price, unit_price),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_products(self) -> List[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM Product").fetchall()

    def get_product_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        """Ürünü ID ile getirir"""
        return self.conn.execute(
            "SELECT * FROM Product WHERE id=?", (product_id,)
        ).fetchone()

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
                     reason: str = "SALE", purchase_price: float = None) -> None:
        self.conn.execute(
            "INSERT INTO StockMovement(product_id, change, reason, purchase_price)"
            " VALUES (?,?,?,?)",
            (product_id, qty, reason, purchase_price),
        )
        self.conn.commit()
        
    def update_unit_price(self, product_id: int, new_price: float) -> bool:
        """
        Ürünün güncel birim fiyatını günceller
        
        Args:
            product_id: Güncellenecek ürünün ID'si
            new_price: Yeni birim fiyat
            
        Returns:
            bool: Güncelleme başarılı ise True, değilse False
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE Product SET unit_price = ? WHERE id = ?",
                (new_price, product_id)
            )
            self.conn.commit()
            # Değişikliklerin veritabanına yazıldığından emin olmak için bağlantıyı yeniliyoruz
            self.refresh_connection()
            # Güncellemeyi doğrula
            updated = self.get_product_by_id(product_id)
            return updated and abs(updated["unit_price"] - new_price) < 0.01
        except sqlite3.Error:
            self.conn.rollback()
            return False

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
            SELECT 
                p.name,
                SUM(CASE 
                    WHEN sm.change < 0 AND sm.reason = 'SALE' THEN -sm.change
                    WHEN sm.change > 0 AND sm.reason = 'ADJUST' THEN -sm.change
                    ELSE 0 
                END) AS sold_qty,
                SUM(CASE 
                    WHEN sm.change < 0 AND sm.reason = 'SALE' THEN -sm.change*p.unit_price
                    WHEN sm.change > 0 AND sm.reason = 'ADJUST' THEN -sm.change*p.unit_price
                    ELSE 0 
                END) AS revenue
            FROM StockMovement sm
            JOIN Product p ON p.id = sm.product_id
            WHERE DATE(sm.timestamp) = DATE('now', 'localtime')
            GROUP BY p.id
            HAVING sold_qty > 0
            ORDER BY sold_qty DESC;
            """
        )                         # sorgu örnekleri :contentReference[oaicite:1]{index=1}
        return cur.fetchall()

    # ---------- Fiyat Takibi -----------------------------------------
    def get_product_price_history(self, product_id: int) -> List[sqlite3.Row]:
        """
        Bir ürünün fiyat geçmişini getirir.
        Sadece alış hareketlerindeki (PURCHASE) fiyat değişimlerini içerir.
        """
        return self.conn.execute(
            """
            SELECT 
                sm.timestamp,
                sm.purchase_price,
                p.name as product_name
            FROM StockMovement sm
            JOIN Product p ON p.id = sm.product_id
            WHERE sm.product_id = ? 
              AND sm.reason = 'PURCHASE'
              AND sm.purchase_price IS NOT NULL
            ORDER BY sm.timestamp DESC
            """,
            (product_id,)
        ).fetchall()

    def search_products_for_price_history(self, query: str) -> List[sqlite3.Row]:
        """
        Ürünleri ada veya barkoda göre arar
        """
        query = f'%{query}%'
        return self.conn.execute(
            """
            SELECT 
                id, 
                name, 
                barcode, 
                unit_price,
                initial_price
            FROM Product 
            WHERE name LIKE ? OR barcode LIKE ?
            ORDER BY name
            """,
            (query, query)
        ).fetchall()

    # ---------- Kapat -------------------------------------------------
    def close(self):
        self.conn.close()

