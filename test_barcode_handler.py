"""
barcode_test_suite.py
Farklı barkod alanlarını otomatik test eden uygulama.
"""

import pyautogui
import time
import sys

class BarcodeTestSuite:
    """Barkod tarama özelliklerini kapsamlı olarak test eder"""

    def __init__(self):
        self.test_barcodes = [
            "1234567890128",  # EAN-13 formatında geçerli barkod
            "5901234123457",  # Başka bir EAN-13 örneği
            "4007817525074",  # Gerçek bir ürün barkodu
            "TEST-BARCODE-123"  # Alfanumerik test barkodu
        ]

        # Test için hareket sürelerini azaltalım
        pyautogui.PAUSE = 0.1

    def simulate_barcode_scan(self, barcode):
        """Barkod tarama simülasyonu yapar"""
        # Çok kısa gecikme ile karakterleri gönder
        for char in barcode:
            pyautogui.write(char, interval=0.01)

        # Enter tuşu gönder
        time.sleep(0.1)
        pyautogui.press('enter')

    def run_tests(self):
        """Farklı sekmelerde barkod testlerini çalıştırır"""
        print("Stok Yönetim Sistemi Barkod Test Programı başlatılıyor...")
        time.sleep(1)

        # Uygulamayı başlat (yolu uygun şekilde değiştirin)
        print("Uygulama başlatılıyor...")
        pyautogui.hotkey('alt', 'tab')  # Uygulamaya geçiş yap
        time.sleep(1)

        # Test sekmeleri - sırasıyla test edeceğiz
        self.test_search_tab()
        self.test_add_product_tab()
        self.test_sales_tab()
        self.test_stock_in_tab()

        print("Tüm testler tamamlandı!")

    def test_search_tab(self):
        """Ürün Arama sekmesinde barkod taramayı test et"""
        print("Ürün Arama sekmesi testi başlıyor...")

        # Ürün Arama sekmesine geç
        pyautogui.hotkey('ctrl', 'tab')  # Bir sonraki sekmeye geç
        time.sleep(0.5)

        # Barkod alanını seç ve odakla
        pyautogui.click(x=300, y=100)  # Uygulama penceresine göre uygun koordinat belirleyin

        # Test barkoduyla tarama simülasyonu yap
        self.simulate_barcode_scan(self.test_barcodes[0])
        time.sleep(1)  # Sonucun görüntülenmesi için bekle

        print("Ürün Arama sekmesi testi tamamlandı.")

    def test_add_product_tab(self):
        """Ürün Ekle sekmesinde barkod taramayı test et"""
        print("Ürün Ekle sekmesi testi başlıyor...")

        # Ürün Ekle sekmesine geç
        for _ in range(2):  # İki sekme ileri
            pyautogui.hotkey('ctrl', 'tab')
        time.sleep(0.5)

        # Barkod alanını seç
        pyautogui.press('tab')  # Adı alanından sonra Tab ile barkod alanına geç

        # Test barkoduyla tarama simülasyonu yap
        self.simulate_barcode_scan(self.test_barcodes[1])
        time.sleep(1)

        print("Ürün Ekle sekmesi testi tamamlandı.")

    def test_sales_tab(self):
        """Satış sekmesinde barkod taramayı test et"""
        print("Satış sekmesi testi başlıyor...")

        # Satış sekmesine geç
        pyautogui.hotkey('ctrl', 'tab')
        time.sleep(0.5)

        # Barkod alanını seç
        pyautogui.click(x=300, y=100)  # Uygulama penceresine göre uygun koordinat belirleyin

        # Test barkoduyla tarama simülasyonu yap
        self.simulate_barcode_scan(self.test_barcodes[2])
        time.sleep(1)

        print("Satış sekmesi testi tamamlandı.")

    def test_stock_in_tab(self):
        """Stok Girişi sekmesinde barkod taramayı test et"""
        print("Stok Girişi sekmesi testi başlıyor...")

        # Stok Girişi sekmesine geç
        pyautogui.hotkey('ctrl', 'tab')
        time.sleep(0.5)

        # Barkod alanını seç
        pyautogui.click(x=300, y=100)  # Uygulama penceresine göre uygun koordinat belirleyin

        # Test barkoduyla tarama simülasyonu yap
        self.simulate_barcode_scan(self.test_barcodes[3])
        time.sleep(1)

        print("Stok Girişi sekmesi testi tamamlandı.")


if __name__ == "__main__":
    # Kullanıcıya hazırlık süresi ver
    print("Barkod tarama testleri 5 saniye içinde başlayacak...")
    print("Lütfen Stok Yönetim Sistemi uygulamasını açın.")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    # Testleri başlat
    test_suite = BarcodeTestSuite()
    test_suite.run_tests()