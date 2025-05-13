"""
controllers.py
GUI bileşenleri + iş mantığı köprüsü.
"""

from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QTableWidget, QTableWidgetItem, QMessageBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QMainWindow, QFileDialog,
    QCheckBox, QGroupBox, QHeaderView
)
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt
from models import DatabaseManager
from reports import export_daily_sales
from sqlite3 import IntegrityError
from barcode_handler import BarcodeHandler
# Fix the datetime import to properly access strptime
from datetime import datetime

def tune_table(table: QTableWidget) -> None:
    """Satır başlıklarını içeriğe göre genişletir ve ortalar."""
    vh = table.verticalHeader()
    vh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    vh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

# -------- Ürünler sekmesi -------------------------------------------
class ProductTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 7)  # 7 sütun (stok ekledik)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Ürün Adı", "Barkod", "Konum", "İlk Fiyat", "Güncel Fiyat", "Stok"]
        )
        layout.addWidget(self.table)
        tune_table(self.table)  # satır numaraları görünür
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for row in self.db.list_products():
            stock = self.db.get_stock_level(row["id"])
            values = [row["id"], row["name"], row["barcode"],
                      row["location"], row["initial_price"], row["unit_price"], stock]
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate(values):
                if c in (4, 5):
                    self.table.setItem(r, c, QTableWidgetItem(f"{val:.2f} TL"))
                else:
                    self.table.setItem(r, c, QTableWidgetItem(str(val)))

        self.table.resizeColumnsToContents()

# -------- Ürün Arama sekmesi ---------------------------------------
class SearchProductTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        # Arama alanı
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ürün adı veya barkod ile arama yapın...")
        self.search_edit.returnPressed.connect(self.search_products)
        search_layout.addWidget(self.search_edit)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.search_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        search_btn = QPushButton("Ara")
        search_btn.clicked.connect(self.search_products)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # Sonuçlar tablosu
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Ürün Adı", "Barkod", "Konum", "Stok"]
        )
        layout.addWidget(self.results_table)
        tune_table(self.results_table)

        # Bilgi etiketi
        self.info_label = QLabel("Arama yapmak için yukarıdaki kutuya ürün adı veya barkod girin.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değer ile otomatik arama yap"""
        self.search_edit.setText(barcode)
        self.search_products()

    def search_products(self):
        """Ürün adı veya barkodu ile ürün arama"""
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Bilgi", "Lütfen bir arama terimi girin.")
            return

        # Veritabanı sorgusunu gerçekleştir
        cur = self.db.conn.cursor()
        cur.execute(
            """
            SELECT id, name, barcode, location 
            FROM Product 
            WHERE name LIKE ? OR barcode LIKE ?
            ORDER BY name
            """,
            (f'%{query}%', f'%{query}%')
        )
        products = cur.fetchall()

        # Sonuçları tabloya doldur
        self.results_table.setRowCount(0)

        if not products:
            self.info_label.setText(f"'{query}' ile eşleşen ürün bulunamadı.")
            return

        for product in products:
            stock = self.db.get_stock_level(product["id"])
            values = [product["id"], product["name"],
                      product["barcode"], product["location"], stock]

            r = self.results_table.rowCount()
            self.results_table.insertRow(r)
            for c, val in enumerate(values):
                self.results_table.setItem(r, c, QTableWidgetItem(str(val)))

        self.info_label.setText(f"{len(products)} ürün bulundu.")
        self.results_table.resizeColumnsToContents()

# -------- Ürün Ekle sekmesi ----------------------------------------
class AddProductTab(QWidget):
    def __init__(self, db: DatabaseManager, refresh_callback):
        super().__init__()
        self.db = db
        self.refresh_callback = refresh_callback

        form = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.barcode_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.price_edit = QDoubleSpinBox()
        self.price_edit.setMaximum(1_000_000)
        self.quantity_edit = QSpinBox()
        self.quantity_edit.setRange(0, 9999)
        self.quantity_edit.setValue(0)

        # Barkod okuyucu
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        form.addRow("Ürün Adı", self.name_edit)
        form.addRow("Barkod", self.barcode_edit)
        form.addRow("Birim Fiyat", self.price_edit)
        form.addRow("Konum", self.location_edit)
        form.addRow("Miktar", self.quantity_edit)

        add_btn = QPushButton("Ürün Ekle")
        add_btn.clicked.connect(self.add_product)
        add_btn.setDefault(True)
        add_btn.setAutoDefault(True)
        form.addRow(add_btn)

        # Fiyat girimi bitince Konum’a geç
        self.price_edit.editingFinished.connect(self.move_to_location)

        # Mantıklı sekme sırası
        QWidget.setTabOrder(self.name_edit, self.barcode_edit)
        QWidget.setTabOrder(self.barcode_edit, self.price_edit)
        QWidget.setTabOrder(self.price_edit, self.location_edit)
        QWidget.setTabOrder(self.location_edit, self.quantity_edit)

    def handle_barcode(self, barcode):
        self.barcode_edit.setText(barcode)
        self.price_edit.setFocus()
        try:
            self.price_edit.lineEdit().selectAll()
        except AttributeError:
            pass

    def move_to_location(self):
        self.location_edit.setFocus()

    def add_product(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Hata", "Ürün adı gereklidir")
            return

        price = self.price_edit.value()
        if price <= 0.0:
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir birim fiyat girin")
            self.price_edit.setFocus()
            return

        barcode = self.barcode_edit.text().strip()
        location = self.location_edit.text().strip()
        quantity = self.quantity_edit.value()

        try:
            product_id = self.db.add_product(name, barcode, location, price)
            if quantity > 0:
                self.db.change_stock(product_id, quantity, "PURCHASE", price)

            QMessageBox.information(
                self, "Başarılı", f"'{name}' ürünü sisteme eklendi."
            )
            self.refresh_callback()

            # Alanları temizle ve yeniden Ürün Adı’na dön
            self.name_edit.clear()
            self.barcode_edit.clear()
            self.location_edit.clear()
            self.price_edit.setValue(0.0)
            self.quantity_edit.setValue(0)
            self.name_edit.setFocus()

        except IntegrityError:
            QMessageBox.information(
                self, "Ürün Var",
                "Bu barkod zaten kayıtlı. Stok artırmak için 'Stok Girişi' sekmesine geçin."
            )


# -------- Satış sekmesi ----------------------------------------------
class SalesTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.cart = {}

        v = QVBoxLayout(self)

        # ———————— Barkod girişi + buton ————————
        h = QHBoxLayout()
        h.addWidget(QLabel("Barkod okutun:"))

        self.barcode_edit = QLineEdit()
        # Klavyeden Enter’a basıldığında da scan() çağrısı için:
        self.barcode_edit.returnPressed.connect(self.scan)
        h.addWidget(self.barcode_edit)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        # Böylece okutulduğunda önce handle_barcode, sonra scan() çağrılacak
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        add_btn = QPushButton("Ekle")
        add_btn.clicked.connect(self.scan)
        h.addWidget(add_btn)

        v.addLayout(h)

        # ———————— Sepet tablosu ————————
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Ürün", "Adet", "Birim", "Toplam"])
        tune_table(self.table)
        v.addWidget(self.table)

        # Butonlar için layout
        buttons_layout = QHBoxLayout()

        # Ürün silme butonu
        remove_btn = QPushButton("Seçilen Ürünü Çıkar")
        remove_btn.setStyleSheet("background-color: #ff9800; color: white;")
        remove_btn.clicked.connect(self.remove_selected_item)
        buttons_layout.addWidget(remove_btn)

        v.addLayout(buttons_layout)

        # Toplam tutar etiketi
        self.total_lbl = QLabel("Toplam: 0.00")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        v.addWidget(self.total_lbl)

        # Satışı Tamamla butonu
        complete_btn = QPushButton("Satışı Tamamla")
        complete_btn.clicked.connect(self.complete_sale)
        v.addWidget(complete_btn)

    def handle_barcode(self, barcode):
        # Barkodu doğrudan satır editine yaz
        self.barcode_edit.setText(barcode)
        #  hemen ekle
        self.scan()
        # imleci tekrar barkod editte tut
        self.barcode_edit.setFocus()

    def scan(self):
        code = self.barcode_edit.text().strip()
        self.barcode_edit.clear()
        if not code:
            return

        product = self.db.find_product_by_barcode(code)
        if not product:
            QMessageBox.warning(self, "Barkod Yok",
                                "Bu barkod sisteme kayıtlı değil.")
            return

        pid, name, price = (product["id"], product["name"], product["unit_price"])
        # Veritabanındaki stok
        stok = self.db.get_stock_level(pid)
        # Sepette halihazırda kaç tane var?
        mevcut_adet = self.cart.get(pid, {}).get("qty", 0)

        # Yeni ekleme ile stok aşılıyorsa vazgeç
        if stok <= mevcut_adet:
            QMessageBox.warning(self, "Stok Yetersiz",
                                f"'{name}' için yeterli stok yok! (Mevcut stok: {stok}, Sepet: {mevcut_adet})")
            return

        # Sepete ekle
        self.cart.setdefault(pid, {"name": name, "price": price, "qty": 0})
        self.cart[pid]["qty"] += 1
        self.refresh()

    def remove_selected_item(self):
        """Seçilen ürünü sepetten çıkar ve stok durumunu güncelle"""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.information(self, "Seçim Yok", "Lütfen sepetten çıkarılacak bir ürün seçin.")
            return

        # Seçilen ürünün adını al
        product_name = self.table.item(selected_row, 0).text()

        # Ürün ID'sini bul
        product_id = None
        for pid, item in self.cart.items():
            if item["name"] == product_name:
                product_id = pid
                break

        if product_id is None:
            QMessageBox.warning(self, "Hata", "Seçilen ürün bulunamadı.")
            return

        # Sepetteki miktarı azalt
        self.cart[product_id]["qty"] -= 1

        # Eğer miktar 0'a düştüyse, ürünü tamamen sepetten çıkar
        if self.cart[product_id]["qty"] <= 0:
            del self.cart[product_id]

        # Tabloyu güncelle
        self.refresh()

        QMessageBox.information(self, "Başarılı", f"'{product_name}' ürünü sepetten çıkarıldı.")

    def refresh(self):
        self.table.setRowCount(0)
        total = 0.0
        for item in self.cart.values():
            r = self.table.rowCount()
            self.table.insertRow(r)
            subtotal = item["qty"] * item["price"]
            for c, val in enumerate(
                [item["name"], item["qty"],
                 f"{item['price']:.2f}", f"{subtotal:.2f}"]
            ):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
            total += subtotal
        self.total_lbl.setText(f"Toplam: {total:.2f}")

    def complete_sale(self):
        if not self.cart:
            QMessageBox.warning(self, "Boş Sepet", "Sepette ürün bulunmuyor.")
            return

        # Satışı kaydetmeden önce bir kere daha stok kontrolü
        for pid, item in self.cart.items():
            stok = self.db.get_stock_level(pid)
            if stok < item["qty"]:
                QMessageBox.warning(
                    self,
                    "Stok Yetersiz",
                    f"'{item['name']}' için stok yetersiz! Mevcut stok: {stok}, Sepette: {item['qty']}"
                )
                return  # Satışa devam etme

        try:
            total_amount = 0
            for product_id, item in self.cart.items():
                subtotal = item["qty"] * item["price"]
                total_amount += subtotal

                # Veritabanında stok değişikliği (-qty)
                self.db.change_stock(
                    product_id=product_id,
                    qty=-item["qty"],
                    reason="SALE"
                )

            # Sepeti temizle, UI güncelle
            self.cart.clear()
            self.refresh()
            QMessageBox.information(
                self,
                "Satış Tamamlandı",
                f"Toplam {total_amount:.2f} TL değerinde satış başarıyla kaydedildi."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Hata",
                f"Satış kaydedilirken bir hata oluştu: {str(e)}"
            )

# -------- Stok Girişi sekmesi --------------------------------------
class StockInTab(QWidget):
    def __init__(self, db: DatabaseManager, refresh_products):
        super().__init__()
        self.db = db
        self.refresh_products = refresh_products
        self.current_product = None

        form = QFormLayout(self)
        self.barcode_edit = QLineEdit()

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.product_info_label = QLabel("Ürün bilgisi: ")

        # Fiyat bilgileri grubu
        self.price_group = QGroupBox("Fiyat Bilgileri")
        price_layout = QFormLayout()
        self.initial_price_label = QLabel("0.00 TL")
        self.current_price_label = QLabel("0.00 TL")
        self.new_price_spin = QDoubleSpinBox()
        self.new_price_spin.setMaximum(1_000_000)
        self.update_price_check = QCheckBox("Birim fiyatı güncelle")
        price_layout.addRow("İlk Alış Fiyatı:", self.initial_price_label)
        price_layout.addRow("Güncel Birim Fiyat:", self.current_price_label)
        price_layout.addRow("Yeni Alış Fiyatı:", self.new_price_spin)
        price_layout.addRow(self.update_price_check)
        self.price_group.setLayout(price_layout)
        self.price_group.setEnabled(False)

        form.addRow("Barkod", self.barcode_edit)
        form.addRow("Miktar", self.qty_spin)
        form.addRow(self.product_info_label)
        form.addRow(self.price_group)

        # --- Stok Ekle butonu + default Enter davranışı ---
        add_btn = QPushButton("Stok Ekle")
        add_btn.clicked.connect(self.add_stock)
        add_btn.setDefault(True)
        add_btn.setAutoDefault(True)
        form.addRow(add_btn)

        # **Eski global QShortcut döngüsünü kaldırdık**,
        # böylece barkoddaki Enter stok eklemeyi tetiklemeyecek.

        # İsterseniz kullanıcı Tab ile de ilerleyebilir:
        QWidget.setTabOrder(self.barcode_edit, self.qty_spin)
        QWidget.setTabOrder(self.qty_spin, add_btn)

    def handle_barcode(self, barcode):
        """Barkod okutulduğunda sadece bilgileri doldur."""
        self.barcode_edit.setText(barcode)
        product = self.db.find_product_by_barcode(barcode)
        if product:
            self.current_product = product
            self.product_info_label.setText(f"Ürün: {product['name']}")
            self.initial_price_label.setText(f"{product['initial_price']:.2f} TL")
            self.current_price_label.setText(f"{product['unit_price']:.2f} TL")
            self.new_price_spin.setValue(product['unit_price'])
            self.price_group.setEnabled(True)
            # Miktar girimi için oraya geç:
            self.qty_spin.setFocus()
            self.qty_spin.selectAll()
        else:
            self.current_product = None
            self.product_info_label.setText("Ürün bulunamadı!")
            self.price_group.setEnabled(False)
            QMessageBox.warning(self, "Bulunamadı", "Barkod kayıtlı değil.")

    def add_stock(self):
          # Barkod girilmemişse uyar ve çık
        code = self.barcode_edit.text().strip()
        if not code:
            QMessageBox.warning(
                self,"Barkod Eksik","Lütfen önce bir barkod okutun veya girin."
                )
            self.barcode_edit.setFocus()
            return
        """Butona tıklayınca veya Enter’a basılınca stok ekle."""
        if not self.current_product:
            # kullanıcı doğrudan butona basmışsa barkodu kontrol et
            code = self.barcode_edit.text().strip()
            product = self.db.find_product_by_barcode(code)
            if not product:
                QMessageBox.warning(self, "Bulunamadı", "Barkod kayıtlı değil.")
                return
            self.current_product = product

        qty = self.qty_spin.value()
        new_price = self.new_price_spin.value()
        pid = self.current_product["id"]

        try:
            # stok güncellemesi
            self.db.change_stock(pid, qty, "PURCHASE", new_price)

            # fiyat güncelleme seçeneği
            if self.update_price_check.isChecked():
                self.db.update_unit_price(pid, new_price)

            QMessageBox.information(
                self, "Tamam",
                f"{qty} adet stok başarıyla eklendi."
            )
            self.force_ui_update()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"İşlem sırasında hata: {e}")
            return

        # alanları temizle
        self.barcode_edit.clear()
        self.qty_spin.setValue(1)
        self.product_info_label.setText("Ürün bilgisi: ")
        self.price_group.setEnabled(False)
        self.update_price_check.setChecked(False)
        self.current_product = None

    def force_ui_update(self):
        # tüm ilgili sekmeleri yenile
        main = self.window()
        if hasattr(main, 'product_tab'):
            main.product_tab.refresh()
        self.db.refresh_connection()
        self.refresh_products()
        if hasattr(main, 'search_tab') and main.search_tab.search_edit.text():
            main.search_tab.search_products()


# -------- Ürün Silme sekmesi --------------------------------------
class DeleteProductTab(QWidget):
    def __init__(self, db: DatabaseManager, refresh_products):
        super().__init__()
        self.db = db
        self.refresh_products = refresh_products
        self.current_product = None  # Silme için seçilen ürünü tutacak değişken

        layout = QVBoxLayout(self)

        # Arama alanı
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ürün adı veya barkod ile arama yapın...")
        self.search_edit.returnPressed.connect(self.search_product)
        search_layout.addWidget(self.search_edit)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.search_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        search_btn = QPushButton("Ara")
        search_btn.clicked.connect(self.search_product)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # Ürün bilgisi etiketi
        self.product_info = QLabel("Silmek için bir ürün arayın")
        self.product_info.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(self.product_info)

        # Silme butonu - başlangıçta devre dışı
        self.delete_btn = QPushButton("Ürünü Sil")
        self.delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_btn.clicked.connect(self.delete_product)
        self.delete_btn.setEnabled(False)  # Ürün seçilene kadar devre dışı
        layout.addWidget(self.delete_btn)

        # Uyarı etiketi
        warning_label = QLabel(
            "DİKKAT: Silme işlemi geri alınamaz!\n"
            "Ürünle ilgili tüm stok hareketleri de silinecektir.")
        warning_label.setStyleSheet("color: red;")
        layout.addWidget(warning_label)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri işle"""
        self.search_edit.setText(barcode)
        self.search_product()

    def search_product(self):
        """Ürün adı veya barkod ile ürün ara"""
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Bilgi", "Lütfen bir arama terimi girin.")
            return

        # Önce barkod ile birebir eşleşme ara (tam eşleşme)
        product = self.db.find_product_by_barcode(query)

        if not product:
            # Barkod eşleşmesi bulunamadıysa, ad ile ara (içinde geçen)
            cur = self.db.conn.cursor()
            cur.execute(
                """
                SELECT id, name, barcode, location
                FROM Product 
                WHERE name LIKE ? OR barcode LIKE ?
                LIMIT 1  -- Sadece ilk eşleşmeyi al
                """,
                (f'%{query}%', f'%{query}%')
            )
            product = cur.fetchone()

        if not product:
            self.product_info.setText(f"'{query}' ile eşleşen ürün bulunamadı.")
            self.delete_btn.setEnabled(False)
            self.current_product = None
            return

        # Ürün stok bilgisini al
        stock = self.db.get_stock_level(product["id"])

        # Ürün bilgisini göster
        self.product_info.setText(
            f"ÜRÜN BİLGİSİ:\n"
            f"Ad: {product['name']}\n"
            f"Barkod: {product['barcode']}\n"
            f"Konum: {product['location']}\n"
            f"Stok: {stock}"
        )

        # Silme butonunu etkinleştir
        self.delete_btn.setEnabled(True)
        self.current_product = product

    def delete_product(self):
        """Bulunan ürünü sil"""
        if not self.current_product:
            QMessageBox.warning(self, "Seçim Yapın", "Silmek için bir ürün seçmelisiniz.")
            return

        product_id = self.current_product["id"]
        product_name = self.current_product["name"]

        # Silme onayı al
        confirm = QMessageBox.question(
            self,
            "Silme Onayı",
            f"'{product_name}' ürününü silmek istediğinizden emin misiniz?\n"
            "Bu işlem geri alınamaz!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            success = self.db.delete_product(product_id)
            if success:
                QMessageBox.information(self, "Başarılı", f"{product_name} ürünü başarıyla silindi.")
                self.search_edit.clear()
                self.product_info.setText("Silmek için bir ürün arayın")
                self.delete_btn.setEnabled(False)
                self.current_product = None
                self.refresh_products()  # Ana ürün listesini güncelle
            else:
                QMessageBox.critical(self, "Hata", "Ürün silinirken bir hata oluştu.")

# -------- Rapor Sekmesi -----------------------------------------
class ReportTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)

          # Başlık
        layout.addWidget(QLabel("Günlük Satış Raporu"))

          # Tablo oluştur ve layout'a ekle
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ürün", "Satış Adedi", "Gelir"])
        tune_table(self.table)
        layout.addWidget(self.table)  # ← Bunu ekledik

          # Excel butonu
        export_btn = QPushButton("Excel'e Aktar")
        export_btn.clicked.connect(self.export_to_excel)
        layout.addWidget(export_btn)

          # Veriyi yükle
        self.refresh_report()

    def showEvent(self, event):
        """Sekme gösterildiğinde otomatik yenile."""
        super().showEvent(event)
        self.refresh_report()
        # Sütun genişliklerini de güncellemek iyi olur
        self.table.resizeColumnsToContents()

    def refresh_report(self):
        """Tabloyu günlük satış verileriyle doldur."""
        self.table.setRowCount(0)
        sales = self.db.daily_sales_report()

        if not sales:
            self.table.setRowCount(1)
            self.table.setSpan(0, 0, 1, 3)
            item = QTableWidgetItem("Bugün için satış kaydı bulunmuyor.")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, 0, item)
            return

        for r, row_data in enumerate(sales):
            self.table.insertRow(r)
            for c, value in enumerate(row_data):
                if c == 2:
                    text = f"{value:.2f} TL"
                else:
                    text = str(value)
                self.table.setItem(r, c, QTableWidgetItem(text))

    def export_to_excel(self):
        """Günlük satış raporunu Excel dosyasına aktar"""
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel'e Kaydet", "", "Excel Dosyaları (*.xlsx)"
        )

        if not path:
            return  # Kullanıcı iptal etti

        if not path.endswith(".xlsx"):
            path += ".xlsx"

        filename = export_daily_sales(self.db, path)
        if filename:
            QMessageBox.information(
                self, "Başarılı", f"Rapor başarıyla kaydedildi:\n{filename}"
            )
        else:
            QMessageBox.warning(
                self, "Veri Yok", "Bugün için satış kaydı bulunmuyor."
            )


# -------- Fiyat Takibi sekmesi -------------------------------------
class PriceHistoryTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.current_product_id = None

        layout = QVBoxLayout(self)

        # Arama alanı
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ürün adı veya barkod ile arama yapın...")
        self.search_edit.returnPressed.connect(self.search_products)
        search_layout.addWidget(self.search_edit)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.search_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        search_btn = QPushButton("Ara")
        search_btn.clicked.connect(self.search_products)
        search_layout.addWidget(search_btn)
        search_btn.setDefault(True)
        search_btn.setAutoDefault(True)

        layout.addLayout(search_layout)

        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QShortcut(QKeySequence(key), self, activated=self.search_products)

        # Ürün seçme listesi
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(300)
        self.product_combo.currentIndexChanged.connect(self.product_selected)
        layout.addWidget(QLabel("Ürün Seçin:"))
        layout.addWidget(self.product_combo)

        # Ürün bilgisi
        self.product_info = QLabel("Lütfen bir ürün seçin")
        layout.addWidget(self.product_info)

        # Fiyat geçmişi tablosu
        layout.addWidget(QLabel("Fiyat Geçmişi:"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tarih", "Alış Fiyatı", "Değişim"])
        tune_table(self.table)

        # Tablo ayarları
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # Add the table to the layout - this was missing
        layout.addWidget(self.table)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri işle"""
        self.search_edit.setText(barcode)
        self.search_products()

    def search_products(self):
        """Ürün ara ve combo box'a doldur"""
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Bilgi", "Lütfen bir arama terimi girin.")
            return

        products = self.db.search_products_for_price_history(query)

        self.product_combo.clear()
        if not products:
            self.product_combo.addItem("Sonuç bulunamadı", -1)
            self.product_info.setText(f"'{query}' ile eşleşen ürün bulunamadı.")
            return

        for product in products:
            self.product_combo.addItem(
                f"{product['name']} (Barkod: {product['barcode']})",
                product['id']
            )

        self.product_combo.setCurrentIndex(0)  # İlk ürünü seç

    def product_selected(self, index):
        """Seçilen ürünün fiyat geçmişini göster"""
        if index < 0 or self.product_combo.count() == 0:
            return

        product_id = self.product_combo.currentData()
        if product_id == -1:  # "Sonuç bulunamadı" durumu
            return

        self.current_product_id = product_id

        # Ürün bilgisini getir
        product = self.db.get_product_by_id(product_id)
        if not product:
            return

        # Ürün bilgisini görüntüle
        self.product_info.setText(
            f"<b>{product['name']}</b><br>"
            f"İlk Alış Fiyatı: <b>{product['initial_price']:.2f} TL</b><br>"
            f"Güncel Birim Fiyat: <b>{product['unit_price']:.2f} TL</b>"
        )

        # Fiyat geçmişini getir
        self.show_price_history()

    def show_price_history(self):
        """Seçilen ürünün fiyat geçmişini tabloda göster"""
        self.table.setRowCount(0)

        if not self.current_product_id:
            return

        price_history = self.db.get_product_price_history(self.current_product_id)

        if not price_history:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Bu ürün için fiyat geçmişi bulunamadı."))
            self.table.setSpan(0, 0, 1, 3)
            return

        # Fiyat değişimlerini hesapla ve sırala
        previous_price = price_history[-1]['purchase_price'] if len(price_history) > 0 else None

        for row_idx, item in enumerate(price_history):
            self.table.insertRow(row_idx)

            # Tarih formatla
            date_str = datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))

            # Fiyat
            price_item = QTableWidgetItem(f"{item['purchase_price']:.2f} TL")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 1, price_item)

            # Değişim
            if row_idx < len(price_history) - 1:
                next_price = price_history[row_idx + 1]['purchase_price']
                if next_price > 0:
                    price_diff = item['purchase_price'] - next_price
                    percent_change = (price_diff / next_price) * 100

                    # Değişim miktarı ve yüzde
                    change_text = f"{price_diff:+.2f} TL ({percent_change:+.2f}%)"
                    change_item = QTableWidgetItem(change_text)

                    # Artış veya azalış rengini ayarla
                    if price_diff > 0:
                        change_item.setForeground(Qt.GlobalColor.darkGreen)
                    elif price_diff < 0:
                        change_item.setForeground(Qt.GlobalColor.red)

                    change_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(row_idx, 2, change_item)

            # İlk satırsa değişim bilgisi olmaz
            if row_idx == len(price_history) - 1:
                self.table.setItem(row_idx, 2, QTableWidgetItem("İlk alım"))


# -------- Ana Pencere ----------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stok Yönetim Sistemi")

        # Veri katmanı - tek bir bağlantı için
        self.db = DatabaseManager()

        # Merkez widget olarak tab widget oluştur
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Ürünler sekmesi
        self.product_tab = ProductTab(self.db)
        self.tabs.addTab(self.product_tab, "Ürünler")

        # Ürün Arama sekmesi
        self.search_tab = SearchProductTab(self.db)
        self.tabs.addTab(self.search_tab, "Ürün Ara")

        # Ürün Ekleme sekmesi
        self.add_tab = AddProductTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.add_tab, "Ürün Ekle")

        # Satış sekmesi
        self.sales_tab = SalesTab(self.db)
        self.tabs.addTab(self.sales_tab, "Satış")

        # Stok Girişi sekmesi
        self.stock_in_tab = StockInTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.stock_in_tab, "Stok Girişi")

        # Ürün Silme sekmesi
        self.delete_tab = DeleteProductTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.delete_tab, "Ürün Sil")

        # Fiyat Takibi sekmesi (yeni eklenen sekme)
        self.price_history_tab = PriceHistoryTab(self.db)
        self.tabs.addTab(self.price_history_tab, "Fiyat Takibi")

        # Rapor sekmesi
        self.report_tab = ReportTab(self.db)
        self.tabs.addTab(self.report_tab, "Raporlar")

        # Sekme değişikliklerini takip et
        self.tabs.currentChanged.connect(self.tab_changed)

    def tab_changed(self, index):
        """Sekme değiştiğinde gerekli yenilemeleri yap"""
        if index == 0:  # Ürünler sekmesi
            self.product_tab.refresh()
        elif index == 7:  # Rapor sekmesi (index 7 oldu çünkü yeni sekme eklendi)
            self.report_tab.refresh_report()

    def closeEvent(self, event):
        """Pencere kapatıldığında veritabanı bağlantısını kapat"""
        self.db.close()
        event.accept()

