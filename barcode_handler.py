# barcode_handler.py
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, QEvent
from PyQt6.QtWidgets import QLineEdit
from time import monotonic

class BarcodeHandler(QObject):
    barcode_detected = pyqtSignal(str)

    def __init__(self, input_timeout=100, min_length=3):
        super().__init__()
        self.buffer = ""
        self.last_key_time = 0
        self.input_timeout = input_timeout
        self.min_length = min_length
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process_buffer)
        self.enter_consumed = False

    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # ─────────────────────────────────────────────────────────────
            # 1) Silme tuşları gelmişse buffer ve timer'ı temizle, hiç emit yok
            if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self.buffer = ""
                self.timer.stop()
                return False   # QLineEdit normal silmeyi yapsın

            # ─────────────────────────────────────────────────────────────
            # 2) Enter gelmişse buffer'ı işle
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.buffer:
                    self.process_buffer()
                    self.enter_consumed = True
                    return True
                return False

            # ─────────────────────────────────────────────────────────────
            # 3) Yazdırılabilir karakter mi? (genellikle barkodlar rakamdır)
            char = event.text()
            if not char or not char.isprintable():
                # harici tuşlar (ok tuşları, fx tuşları vs.) buffer bozar ama emit etmez
                self.buffer = ""
                self.timer.stop()
                return False

            # ─────────────────────────────────────────────────────────────
            # 4) Buffer’a ekle ve timer’ı yeniden başlat
            self.buffer += char
            self.timer.start(self.input_timeout)
            self.last_key_time = int(monotonic() * 1000)
            return False  # QLineEdit’de de karakter görünsün

        # KeyRelease’da Enter’i yutmak için
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyRelease:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.enter_consumed:
                self.enter_consumed = False
                return True

        return super().eventFilter(obj, event)

    def process_buffer(self):
        """Timer süresi dolunca veya Enter’e basılınca buffer kontrolü."""
        self.timer.stop()
        if len(self.buffer) >= self.min_length:
            code = self.buffer.strip()
            self.barcode_detected.emit(code)
        # Her durumda temizle
        self.buffer = ""
        self.last_key_time = 0
        self.enter_consumed = False
