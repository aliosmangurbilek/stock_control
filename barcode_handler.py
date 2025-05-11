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
            now = int(monotonic() * 1000)
            key = event.key()

            # Enter geldiğinde buffer'ı işle
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.buffer:
                    self.process_buffer()
                    self.enter_consumed = True
                    return True
                return False

            char = event.text()
            if not char:
                return False

            # Her tuşta buffer güncelle ve timer başlat
            self.buffer += char
            self.timer.start(self.input_timeout)

            self.last_key_time = now
            return False

        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyRelease:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.enter_consumed:
                self.enter_consumed = False
                return True

        return super().eventFilter(obj, event)

    def process_buffer(self):
        self.timer.stop()
        if len(self.buffer) >= self.min_length:
            code = self.buffer.strip()
            self.barcode_detected.emit(code)
        self.buffer = ""
        self.last_key_time = 0
        self.enter_consumed = False
