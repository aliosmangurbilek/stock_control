"""
barcode_handler.py
Barkod okuyucudan gelen girdileri yönetmeye yarayan sınıf.
"""

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLineEdit


class BarcodeHandler(QObject):
    """
    Barkod okuyucu girdisini yöneten sınıf.
    
    Barkod okuyucuların çoğu, çok hızlı bir şekilde ardışık karakterleri gönderen
    klavye cihazları gibi davranır ve genellikle sonunda Enter tuşu gönderirler.
    Bu sınıf, hızlı girdi ve Enter ile bitirme karakteristiğini kullanarak
    normal klavye girişinden barkod tarayıcı girişini ayırt eder.
    """
    barcode_detected = pyqtSignal(str)  # Barkod tespit edildiğinde sinyal gönderir
    
    def __init__(self, input_timeout=100):  # Timeout değerini biraz artırdık
        """
        Args:
            input_timeout (int): Milisaniye cinsinden ardışık girişler arasındaki maksimum gecikme
        """
        super().__init__()
        self.buffer = ""  # Giriş arabelleği
        self.last_key_time = 0  # Son tuş basımının zamanı
        self.input_timeout = input_timeout
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process_buffer)
        self.enter_consumed = False  # Enter tuşunun tüketilip tüketilmediğini izlemek için
        
    def eventFilter(self, obj, event):
        """QLineEdit bileşenine bağlanan olay filtresi"""
        if isinstance(obj, QLineEdit) and event.type() == event.Type.KeyPress:
            current_time = event.timestamp()
            
            # Enter tuşu basıldığında işlem yap
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.buffer:
                    self.process_buffer()
                    self.enter_consumed = True  # Enter tuşunu tüket
                    return True  # Olayı tüket
                else:
                    # Buffer boşsa, normal Enter davranışına izin ver
                    self.enter_consumed = False
                    return False
                    
            # Ardışık tuşlar arasındaki zaman farkını kontrol et 
            if self.last_key_time > 0:
                time_diff = current_time - self.last_key_time
                
                # Eğer normal klavye kullanımından daha hızlıysa, barkod tarayıcıdır
                if time_diff < self.input_timeout:
                    self.buffer += event.text()
                    self.timer.start(self.input_timeout * 3)  # Bir süre sonra işlem yap
                else:
                    self.buffer = event.text()  # Yeni bir buffer başlat
            else:
                self.buffer = event.text()
                
            self.last_key_time = current_time
            
        elif isinstance(obj, QLineEdit) and event.type() == event.Type.KeyRelease:
            # Enter tuşu bırakıldığında ve tüketildiyse, bu olayı da tüket
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.enter_consumed:
                self.enter_consumed = False
                return True
            
        return super().eventFilter(obj, event)
    
    def process_buffer(self):
        """Arabellekteki veriyi işle ve sinyal gönder"""
        if self.buffer:
            barcode = self.buffer.strip()
            if len(barcode) >= 3:  # Minimum barkod uzunluğunu 3'e düşürdük, bazı ürün kodları kısa olabilir
                self.barcode_detected.emit(barcode)
            self.buffer = ""
            self.last_key_time = 0
