# models.py
# Veri katmanı: SQLite bağlantısı ve CRUD işlemleri.

import sqlite3                    # Python yerleşik SQLite modülü
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

# Uygulama kök dizininde /data/inventory.db dosyası oluşturur
DB_PATH = Path(__file__).resolve().parent / "data" / "inventory.db"
DB_PATH.parent.mkdir(exist_ok=True)

# Logging yapılandırması
logging.basicConfig(level=logging.INFO)

class DatabaseManager:
    """SQLite tabanlı basit DAO (Data Access Object).
    Veritabanı bağlantı yönetimi, şema oluşturma ve CRUD işlemleri.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Yabancı anahtar kısıtlamalarını etkinleştir
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Tabloları oluşturur ve gerekli sütun/index eklemelerini yapar."""
        cur = self.conn.cursor()
        # Ürün tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS Product (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                barcode        TEXT    UNIQUE,
                location       TEXT,
                unit_price     REAL    DEFAULT 0.0,
                initial_price  REAL    DEFAULT 0.0,
                created_at     TEXT    DEFAULT (datetime('now','localtime'))
            );
            """
        )
        # Barkod sütununa index
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_barcode ON Product(barcode);"
        )

        # Stok hareketleri tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS StockMovement (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id     INTEGER,
                change         INTEGER NOT NULL,
                reason         TEXT    CHECK(reason IN ('SALE','PURCHASE','ADJUST')) NOT NULL,
                purchase_price REAL    DEFAULT NULL,
                timestamp      TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(product_id) REFERENCES Product(id) ON DELETE CASCADE
            );
            """
        )
        # Zaman damgasına index
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_movement_timestamp ON StockMovement(timestamp);"
        )

        self.conn.commit()
        logging.info("Veritabanı şeması hazır. Path: %s", self.db_path)

    def refresh_connection(self) -> bool:
        """Mevcut bağlantıyı kapatıp, aynı ayarlarla yeniden açar."""
        try:
            self.conn.close()
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            return True
        except sqlite3.Error as e:
            logging.error("Veritabanı yeniden bağlanamadı: %s", e)
            return False

    # ---------- CRUD: Product ----------
    def add_product(self, name: str, barcode: str,
                    location: str, unit_price: float) -> int:
        """Yeni ürün ekler ve ID döner."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO Product(name, barcode, location, unit_price, initial_price)"
            " VALUES (?,?,?,?,?)",
            (name, barcode, location, unit_price, unit_price),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_products(self) -> List[sqlite3.Row]:
        """Tüm ürünleri getirir."""
        return self.conn.execute("SELECT * FROM Product ORDER BY name").fetchall()

    def get_product_by_id(self, product_id: int) -> Optional[sqlite3.Row]:
        """ID ile ürün getirir."""
        return self.conn.execute(
            "SELECT * FROM Product WHERE id = ?", (product_id,)
        ).fetchone()

    def find_product_by_barcode(self, code: str) -> Optional[sqlite3.Row]:
        """Barkoda göre ürün sorgular."""
        return self.conn.execute(
            "SELECT * FROM Product WHERE barcode = ?", (code,)
        ).fetchone()

    def delete_product(self, product_id: int) -> bool:
        """Ürünü ve ilişkili stok hareketlerini siler (CASCADE destekli)."""
        try:
            # First check if the product exists
            product = self.get_product_by_id(product_id)
            if not product:
                logging.error(f"Silinecek ürün bulunamadı: ID={product_id}")
                return False

            # Begin transaction
            self.conn.execute("BEGIN TRANSACTION")

            # Delete stock movements first (explicitly, in case CASCADE doesn't work)
            cur = self.conn.cursor()
            cur.execute("DELETE FROM StockMovement WHERE product_id = ?", (product_id,))

            # Then delete the product
            cur.execute("DELETE FROM Product WHERE id = ?", (product_id,))

            # Commit the changes
            self.conn.commit()

            logging.info(f"Ürün ve ilişkili stok hareketleri silindi: ID={product_id}")
            return cur.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Ürün silme hatası: {str(e)}")
            self.conn.rollback()
            return False

    # ---------- Stok işlemleri ----------
    def change_stock(self, product_id: int, qty: int,
                     reason: str = "SALE", purchase_price: float = None) -> bool:
        """Stok hareketi kaydeder."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO StockMovement(product_id, change, reason, purchase_price)"
                " VALUES (?,?,?,?)",
                (product_id, qty, reason, purchase_price),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error("Stok değişikliği hatası: %s", e)
            self.conn.rollback()
            return False

    def update_unit_price(self, product_id: int, new_price: float) -> bool:
        """Ürün birim fiyatını günceller."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE Product SET unit_price = ? WHERE id = ?",
                (new_price, product_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error("Birim fiyat güncelleme hatası: %s", e)
            self.conn.rollback()
            return False

    def get_stock_level(self, product_id: int) -> int:
        """Mevcut stok miktarını hesaplar."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(change),0) AS qty"
            " FROM StockMovement WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return row["qty"] if row else 0

    # ---------- Günlük satış raporu ----------
    def daily_sales_report(self) -> List[sqlite3.Row]:
        """Bugünün satış adedi ve gelir raporunu döner."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                p.name AS product_name,
                SUM(CASE WHEN sm.change < 0 AND sm.reason = 'SALE' THEN -sm.change ELSE 0 END) AS sold_qty,
                SUM(CASE WHEN sm.change < 0 AND sm.reason = 'SALE' THEN -sm.change * COALESCE(sm.purchase_price, p.unit_price) ELSE 0 END) AS revenue
            FROM StockMovement sm
            JOIN Product p ON p.id = sm.product_id
            WHERE DATE(sm.timestamp) = DATE('now', 'localtime')
            GROUP BY p.id
            HAVING sold_qty > 0
            ORDER BY sold_qty DESC;
            """
        )
        rows = cur.fetchall()
        return rows

    # ---------- Fiyat takibi ----------
    def get_product_price_history(self, product_id: int) -> List[sqlite3.Row]:
        """Bir ürünün alış fiyatı geçmişini (en yeni önce) getirir."""
        return self.conn.execute(
            """
            SELECT timestamp, purchase_price
            FROM StockMovement
            WHERE product_id = ? AND reason = 'PURCHASE' AND purchase_price IS NOT NULL
            ORDER BY timestamp DESC
            """,
            (product_id,)
        ).fetchall()

    def search_products_for_price_history(self, query: str) -> List[sqlite3.Row]:
        """Ada veya barkoda göre ürün arar."""
        term = f"%{query}%"
        return self.conn.execute(
            """
            SELECT id, name, barcode, unit_price, initial_price
            FROM Product
            WHERE name LIKE ? OR barcode LIKE ?
            ORDER BY name
            """,
            (term, term)
        ).fetchall()

    def close(self) -> None:
        """Bağlantıyı kapatır."""
        self.conn.close()
