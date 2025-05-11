"""
app.py ― Uygulamanın giriş noktası
• Tek bir QApplication yaratır
• Kullandığı işletim sistemine göre açık/koyu tema QSS yükler
• Controllers.MainWindow'u açar
"""

import sys
import logging
import platform
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

# Yerel modüller
from controllers import MainWindow
from models import DatabaseManager

# Windows'ta açık/koyu tercihine erişmek için
if platform.system() == "Windows":
    import winreg


# ------------------------------------------------------------------
# Tema yükleyici
# ------------------------------------------------------------------
def load_stylesheet(app: QApplication) -> None:
    """
    Çalıştığı platformun tercihine göre style_dark.qss
    veya style_light.qss dosyasını UYGULAR.
    """
    theme = "light"  # varsayılan

    # --- Windows: Registry'den oku --------------------------------
    if platform.system() == "Windows":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            light_flag, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            theme = "light" if light_flag == 1 else "dark"
        except Exception:
            pass

    # --- Linux / macOS: basit sezgi --------------------------------
    else:
        import os
        gtk_theme = os.environ.get("GTK_THEME", "").lower()
        desktop   = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "light" in gtk_theme or ("gnome" in desktop and "dark" not in gtk_theme):
            theme = "light"

    base_dir = Path(__file__).resolve().parent
    qss_path = base_dir / "resources" / f"style_{theme}.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    else:
        print(f"⚠ Stil dosyası bulunamadı: {qss_path}")


# ------------------------------------------------------------------
# Ana fonksiyon
# ------------------------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)          # PyQt6'da exec_() yerine exec()

    # Tema uygula
    load_stylesheet(app)

    # Veritabanı bağlantısını test et
    db = DatabaseManager()
    db.conn.execute("PRAGMA foreign_keys = ON")
    try:
        # Uygulama açılışında veritabanını diske yazalım
        db.conn.execute("PRAGMA wal_checkpoint(FULL)")
        db.conn.commit()
        logging.info("Veritabanı açılışta diske yazıldı")

        db.list_products()
        db.refresh_connection()
    except Exception as e:
        QMessageBox.critical(None, "Veritabanı Hatası",
                             f"Veritabanına bağlanırken hata:\n{e}")
        sys.exit(1)

    # Ana pencere
    win = MainWindow()
    win.resize(1300, 900)
    win.show()

    # Periyodik olarak veritabanını diske yazacak bir zamanlayıcı oluştur
    # Her 5 dakikada bir işletim sistemi çökmesi durumlarına karşı önlem
    checkpoint_timer = QTimer()
    checkpoint_timer.timeout.connect(lambda: db.conn.execute("PRAGMA wal_checkpoint(FULL)"))
    checkpoint_timer.start(5 * 60 * 1000)  # 5 dakika = 300,000 ms

    # QApplication kapatma sinyalini yakala
    app.aboutToQuit.connect(lambda: db.conn.execute("PRAGMA wal_checkpoint(FULL)"))

    sys.exit(app.exec())                   # Olay döngüsü


# ------------------------------------------------------------------
if __name__ == "__main__":
    main()

