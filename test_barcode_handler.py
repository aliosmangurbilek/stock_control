"""
test_barcode_handler.py
BarcodeHandler sınıfını test etmek için kullanılan test uygulaması.
"""

import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QLineEdit, QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from barcode_handler import BarcodeHandler


class BarcodeSimulator:
    """Barkod tarayıcısını simüle eden sınıf"""
    
    @staticmethod
    def simulate_barcode_scan(target_widget, barcode_text):
        """
        Verilen widget'a barkod tarayıcı gibi hızlı karakter gönderir
        
        Args:
            target_widget: Girdinin gönderileceği widget (QLineEdit)
            barcode_text: Simüle edilecek barkod metni
        """
        target_widget.clear()
        target_widget.setFocus()
        
        # Barkod metnini hızlıca karakterler halinde gönder
        for char in barcode_text:
            # Her karakter için bir klavye olayı oluştur
            event = QKeyEvent(
                QEvent.Type.KeyPress,
                ord(char),
                Qt.KeyboardModifier.NoModifier,
                char
            )
            # Widget'a olayı gönder
            QApplication.sendEvent(target_widget, event)
            # Çok kısa bir gecikme - gerçek tarayıcıyı simüle etmek için
            QApplication.processEvents()
            time.sleep(0.01)  # 10ms delay
        
        # Son olarak Enter tuşu gönder (çoğu barkod okuyucu sonunda Enter gönderir)
        enter_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(target_widget, enter_event)


class BarcodeTestWindow(QMainWindow):
    """BarcodeHandler test penceresi"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Barkod Okuyucu Test Uygulaması")
        self.setGeometry(100, 100, 600, 400)
        
        # Ana widget ve düzen
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Test açıklama etiketi
        layout.addWidget(QLabel(
            "Bu uygulama, barkod okuyucu olmadan BarcodeHandler sınıfını test etmenizi sağlar.\n"
            "Normal klavye girişi ile barkod tarayıcı girişi arasındaki farkı gösterir."
        ))
        
        # Normal giriş alanı
        layout.addWidget(QLabel("Normal Giriş (BarcodeHandler'sız):"))
        self.normal_input = QLineEdit()
        layout.addWidget(self.normal_input)
        
        # Barkod giriş alanı
        layout.addWidget(QLabel("Barkod Giriş (BarcodeHandler'lı):"))
        self.barcode_input = QLineEdit()
        layout.addWidget(self.barcode_input)
        
        # Barkod handler'ı bağla
        self.barcode_handler = BarcodeHandler()
        self.barcode_input.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.on_barcode_detected)
        
        # Test barkodları
        test_barcode_layout = QHBoxLayout()
        test_barcode_layout.addWidget(QLabel("Test Barkodları:"))
        
        # Test barkodlarını oluştur
        test_barcodes = ["1234567890128", "5901234123457", "4007817525074"]
        for barcode in test_barcodes:
            btn = QPushButton(barcode)
            btn.clicked.connect(lambda checked=False, code=barcode: 
                               BarcodeSimulator.simulate_barcode_scan(self.barcode_input, code))
            test_barcode_layout.addWidget(btn)
        
        layout.addLayout(test_barcode_layout)
        
        # Özel barkod test alanı
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Özel Barkod:"))
        self.custom_barcode = QLineEdit()
        custom_layout.addWidget(self.custom_barcode)
        
        test_btn = QPushButton("Test Et")
        test_btn.clicked.connect(self.test_custom_barcode)
        custom_layout.addWidget(test_btn)
        
        layout.addLayout(custom_layout)
        
        # Log alanı
        layout.addWidget(QLabel("Tespit Edilen Barkodlar:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Manuel ve otomatik giriş arasındaki farkı göstermek için
        layout.addWidget(QLabel(
            "Not: Normal giriş yaptığınızda bir sinyal oluşmaz. "
            "Barkod simülasyonu yaptığınızda BarcodeHandler sinyali yakalar."
        ))
        
        self.setCentralWidget(main_widget)
    
    def test_custom_barcode(self):
        """Özel barkod test butonu için işleyici"""
        barcode = self.custom_barcode.text().strip()
        if barcode:
            BarcodeSimulator.simulate_barcode_scan(self.barcode_input, barcode)
    
    def on_barcode_detected(self, barcode):
        """Barkod algılandığında çağrılan fonksiyon"""
        self.log_text.append(f"Barkod tespit edildi: {barcode}")
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BarcodeTestWindow()
    window.show()
    sys.exit(app.exec())
