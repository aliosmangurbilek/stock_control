"""
app.py
Uygulamanın giriş noktası.
– Tek bir QApplication örneği yaratır :contentReference[oaicite:0]{index=0},
– Controllers.MainWindow'u açar,
– İsteğe bağlı koyu temayı yükler.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication              # QApplication ana olay döngüsünü yönetir :contentReference[oaicite:1]{index=1}
from controllers import MainWindow

def main() -> None:
    app = QApplication(sys.argv)                      # PyQt‑6'da exec_() yerine exec() kullanılır :contentReference[oaicite:2]{index=2}

    # Koyu tema (varsa)
    style_file = Path("resources/style.qss")
    if style_file.exists():
        app.setStyleSheet(style_file.read_text())

    win = MainWindow()                                # Ana pencere: sekmeli yapı :contentReference[oaicite:3]{index=3}
    win.resize(900, 600)
    win.show()                                        # Pencereyi gösterir; olay döngüsü tetiklenir

    sys.exit(app.exec())                              # exec(): döngü sonlandığında çıkış :contentReference[oaicite:4]{index=4}

if __name__ == "__main__":
    main()
