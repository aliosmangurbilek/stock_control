"""
models.py
Veri katmanı: SQLite bağlantısı, CRUD işlemleri + otomatik yedek.
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

# ───────────────────────── YOL TANIMI ────────────────────────────
def _writable_dir() -> Path:
    """
    • Geliştirmede: dosyanın klasörü
    • PyInstaller'da: EXE'nin klasörü yazılabiliyorsa orası, değilse
      %LOCALAPPDATA%\StokKontrol
    """
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    try:
        (root / "__writetest__").touch(exist_ok=False)
        (root / "__writetest__").unlink()
        return root
    except Exception:
        return Path(os.getenv("LOCALAPPDATA", Path.home())) / "StokKontrol"

ROOT_DIR  = _writable_dir()
DATA_DIR  = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH   = DATA_DIR / "inventory.db"

BACKUP_DIR = Path(r"D:\yedek\stok")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ───────────────────────── LOG AYARLARI ──────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
# ────────────────────────── DAO SINIFI ──────────────────────────────
class DatabaseManager:
    """SQLite tabanlı basit DAO (Data Access Object)."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA synchronous = FULL")
        self.conn.execute("PRAGMA wal_checkpoint(FULL)")
        self._ensure_schema()

        self.transaction_count = 0
        self.checkpoint_threshold = 50

    # ─────────────── ŞEMA ───────────────────────────────────────────
    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()

        # Product
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS Product (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                barcode       TEXT UNIQUE,
                location      TEXT,
                unit_price    REAL DEFAULT 0.0,
                initial_price REAL DEFAULT 0.0,
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_product_barcode ON Product(barcode);")

        # StockMovement
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS StockMovement (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id     INTEGER,
                change         INTEGER NOT NULL,
                reason         TEXT CHECK(reason IN ('SALE','PURCHASE','ADJUST')) NOT NULL,
                purchase_price REAL DEFAULT NULL,
                timestamp      TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(product_id) REFERENCES Product(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_movement_timestamp ON StockMovement(timestamp);")

        self.conn.commit()
        logging.info("Veritabanı şeması oluşturuldu → %s", self.db_path)

    # ─────────────── Yardımcılar ────────────────────────────────────
    def _checkpoint_if_needed(self) -> None:
        self.transaction_count += 1
        if self.transaction_count >= self.checkpoint_threshold:
            try:
                self.conn.execute("PRAGMA wal_checkpoint(FULL)")
                self.conn.commit()
                logging.info("%s işlem sonrası veritabanı diske yazıldı", self.transaction_count)
            except sqlite3.Error as e:
                logging.error("Checkpoint hatası: %s", e)
            finally:
                self.transaction_count = 0

    def _backup_db(self) -> None:
        """inventory.db dosyasını yedek klasörüne kopyalar."""
        if DB_PATH.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = BACKUP_DIR / f"inventory_{ts}.db"
            try:
                shutil.copy2(DB_PATH, dst)
                logging.info("Yedek alındı → %s", dst)
            except Exception as e:
                logging.error("Yedekleme hatası: %s", e)

    # ─────────────── Bağlantı Yenileme ──────────────────────────────
    def refresh_connection(self) -> bool:
        try:
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            self.conn.close()

            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA synchronous = FULL")
            self.transaction_count = 0
            return True
        except sqlite3.Error as e:
            logging.error("Veritabanı yeniden bağlanamadı: %s", e)
            return False

    # ─────────────── CRUD: Product ─────────────────────────────────
    def add_product(self, name: str, barcode: str, location: str, unit_price: float) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO Product(name, barcode, location, unit_price, initial_price)"
            " VALUES (?,?,?,?,?)",
            (name, barcode, location, unit_price, unit_price),
        )
        self.conn.commit()
        self._checkpoint_if_needed()
        return cur.lastrowid

    def list_products(self):
        return self.conn.execute("SELECT * FROM Product ORDER BY name").fetchall()

    def get_product_by_id(self, product_id: int):
        return self.conn.execute("SELECT * FROM Product WHERE id = ?", (product_id,)).fetchone()

    def find_product_by_barcode(self, code: str):
        return self.conn.execute("SELECT * FROM Product WHERE barcode = ?", (code,)).fetchone()

    def delete_product(self, product_id: int) -> bool:
        try:
            self.conn.execute("BEGIN")
            self.conn.execute("DELETE FROM StockMovement WHERE product_id = ?", (product_id,))
            cur = self.conn.execute("DELETE FROM Product WHERE id = ?", (product_id,))
            self.conn.commit()
            self._checkpoint_if_needed()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            logging.error("Ürün silme hatası: %s", e)
            self.conn.rollback()
            return False

    # ─────────────── Stok İşlemleri ────────────────────────────────
    def change_stock(self, product_id: int, qty: int, reason: str = "SALE", purchase_price: float | None = None):
        try:
            self.conn.execute(
                "INSERT INTO StockMovement(product_id, change, reason, purchase_price)"
                " VALUES (?,?,?,?)",
                (product_id, qty, reason, purchase_price),
            )
            self.conn.commit()
            self._checkpoint_if_needed()
            return True
        except sqlite3.Error as e:
            logging.error("Stok değişikliği hatası: %s", e)
            self.conn.rollback()
            return False

    def update_unit_price(self, product_id: int, new_price: float) -> bool:
        try:
            self.conn.execute("UPDATE Product SET unit_price = ? WHERE id = ?", (new_price, product_id))
            self.conn.commit()
            self._checkpoint_if_needed()
            return True
        except sqlite3.Error as e:
            logging.error("Birim fiyat güncelleme hatası: %s", e)
            self.conn.rollback()
            return False

    def get_stock_level(self, product_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(change),0) AS qty FROM StockMovement WHERE product_id = ?", (product_id,)
        ).fetchone()
        return row["qty"] if row else 0

    # ─────────────── Raporlama ─────────────────────────────────────
    def daily_sales_report(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute(
            """
            SELECT p.name,
                   SUM(-sm.change) AS sold_qty,
                   SUM(-sm.change * p.unit_price) AS revenue
            FROM StockMovement sm
            JOIN Product p ON p.id = sm.product_id
            WHERE sm.reason = 'SALE' AND sm.timestamp LIKE ?
            GROUP BY p.id
            HAVING sold_qty > 0
            ORDER BY sold_qty DESC
            """,
            (f"{today}%",),
        ).fetchall()

    # ─────────────── Fiyat Geçmişi & Arama ─────────────────────────
    def get_product_price_history(self, product_id: int):
        return self.conn.execute(
            """
            SELECT timestamp, purchase_price
            FROM StockMovement
            WHERE product_id = ? AND reason = 'PURCHASE' AND purchase_price IS NOT NULL
            ORDER BY timestamp DESC
            """,
            (product_id,),
        ).fetchall()

    def search_products_for_price_history(self, query: str):
        term = f"%{query}%"
        return self.conn.execute(
            """
            SELECT id, name, barcode, unit_price, initial_price
            FROM Product
            WHERE name LIKE ? OR barcode LIKE ?
            ORDER BY name
            """,
            (term, term),
        ).fetchall()

    # ─────────────── Kapatma ───────────────────────────────────────
    def close(self) -> None:
        try:
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error("Veritabanı kapatma hatası: %s", e)
        finally:
            self.conn.close()
            self._backup_db()
