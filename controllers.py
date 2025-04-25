"""
controllers.py
GUI bileşenleri + iş mantığı köprüsü.
"""

from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QTableWidget, QTableWidgetItem, QMessageBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QMainWindow, QFileDialog,
    QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt
from models import DatabaseManager
from reports import export_daily_sales
from sqlite3 import IntegrityError
from barcode_handler import BarcodeHandler

# -------- Ürünler sekmesi -------------------------------------------
class ProductTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 7)  # 7 sütun olarak değiştirdik (stok ekledik)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Ürün Adı", "Barkod", "Konum", "İlk Fiyat", "Güncel Fiyat", "Stok"]
        )
        layout.addWidget(self.table)

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
                if c in (4, 5):  # İlk ve güncel fiyatları biçimlendir
                    self.table.setItem(r, c, QTableWidgetItem(f"{val:.2f} TL"))
                else:
                    self.table.setItem(r, c, QTableWidgetItem(str(val)))

        # Sütunları içeriğe göre boyutlandır
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

        # Barkod okuyucu desteği ekle
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        self.location_edit = QLineEdit()
        self.price_edit = QDoubleSpinBox()
        self.price_edit.setMaximum(1_000_000)
        self.quantity_edit = QSpinBox()
        self.quantity_edit.setRange(0, 9999)
        self.quantity_edit.setValue(0)

        form.addRow("Ürün Adı", self.name_edit)
        form.addRow("Barkod", self.barcode_edit)
        form.addRow("Konum", self.location_edit)
        form.addRow("Birim Fiyat", self.price_edit)
        form.addRow("Miktar", self.quantity_edit)

        add_btn = QPushButton("Ürün Ekle")
        add_btn.clicked.connect(self.add_product)
        form.addRow(add_btn)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri otomatik doldur"""
        self.barcode_edit.setText(barcode)
        # Imleç sonraki alana hareket etsin
        self.location_edit.setFocus()

    def add_product(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Hata", "Ürün adı gereklidir")
            return

        barcode = self.barcode_edit.text().strip()
        location = self.location_edit.text().strip()
        price = self.price_edit.value()
        quantity = self.quantity_edit.value()

        try:
            product_id = self.db.add_product(name, barcode, location, price)

            # İlk stok eklemesi
            if quantity > 0:
                self.db.change_stock(product_id, quantity, "PURCHASE", price)

            self.refresh_callback()
            # Temizle
            self.name_edit.clear()
            self.barcode_edit.clear()
            self.location_edit.clear()
            self.price_edit.setValue(0.0)
            self.quantity_edit.setValue(0)
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

        # Barkod giriş satırı
        h = QHBoxLayout()
        h.addWidget(QLabel("Barkod okutun:"))
        self.barcode_edit = QLineEdit()
        self.barcode_edit.returnPressed.connect(self.scan)
        h.addWidget(self.barcode_edit)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        # Add button for users who prefer clicking
        add_btn = QPushButton("Ekle")
        add_btn.clicked.connect(self.scan)
        h.addWidget(add_btn)

        v.addLayout(h)

        # Sepet tablosu
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Ürün", "Adet", "Birim", "Toplam"]
        )
        v.addWidget(self.table)

        # Toplam tutar etiketi
        self.total_lbl = QLabel("Toplam: 0.00")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        v.addWidget(self.total_lbl)

        # Satışı Tamamla butonu
        complete_btn = QPushButton("Satışı Tamamla")
        complete_btn.clicked.connect(self.complete_sale)
        v.addWidget(complete_btn)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri hemen işle"""
        self.barcode_edit.setText(barcode)
        self.scan()
        self.barcode_edit.setFocus()  # İmleci tekrar barkod alanına getir

    def scan(self):
        code = self.barcode_edit.text().strip()
        self.barcode_edit.clear()

        product = self.db.find_product_by_barcode(code)
        if not product:
            QMessageBox.warning(self, "Barkod Yok",
                                "Bu barkod sisteme kayıtlı değil.")
            return

        pid, name, price = product["id"], product["name"], product["unit_price"]
        mevcut_stok = self.db.get_stock_level(pid)
        if mevcut_stok <= 0:
            QMessageBox.warning(
                self, "Stok Yetersiz",
                f"'{name}' için stok kalmamış!\n"
                "Önce stok girişi yapmalısınız."
            )
            return

        # Stok var → satış kaydet
        self.db.change_stock(pid, -1, "SALE")
        self.cart.setdefault(pid, {"name": name, "price": price, "qty": 0})
        self.cart[pid]["qty"] += 1
        self.refresh()

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

        self.cart.clear()
        self.refresh()
        QMessageBox.information(self, "Satış Tamamlandı", "Satış başarıyla tamamlandı.")

# -------- Stok Girişi sekmesi -----------------------------
class StockInTab(QWidget):
    def __init__(self, db: DatabaseManager, refresh_products):
        super().__init__()
        self.db = db
        self.refresh_products = refresh_products
        self.current_product = None

        form = QFormLayout(self)
        self.barcode_edit = QLineEdit()

        # Barkod okuyucu desteği ekle
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

        self.qty_spin = QSpinBox(); self.qty_spin.setRange(1, 9999)
        self.product_info_label = QLabel("Ürün bilgisi: ")

        # Fiyat bilgileri ve güncelleme seçeneği
        self.price_group = QGroupBox("Fiyat Bilgileri")
        price_layout = QFormLayout()

        self.current_price_label = QLabel("0.00 TL")
        self.initial_price_label = QLabel("0.00 TL")

        # Yeni fiyat güncelleme alanı
        self.new_price_spin = QDoubleSpinBox()
        self.new_price_spin.setMaximum(1_000_000)
        self.update_price_check = QCheckBox("Birim fiyatı güncelle")

        price_layout.addRow("İlk Alış Fiyatı:", self.initial_price_label)
        price_layout.addRow("Güncel Birim Fiyat:", self.current_price_label)
        price_layout.addRow("Yeni Alış Fiyatı:", self.new_price_spin)
        price_layout.addRow(self.update_price_check)

        self.price_group.setLayout(price_layout)
        self.price_group.setEnabled(False)  # Başlangıçta devre dışı

        form.addRow("Barkod", self.barcode_edit)
        form.addRow("Miktar", self.qty_spin)
        form.addRow(self.product_info_label)
        form.addRow(self.price_group)

        add_btn = QPushButton("Stok Ekle")
        add_btn.clicked.connect(self.add_stock)
        form.addRow(add_btn)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri otomatik doldur"""
        self.barcode_edit.setText(barcode)

        # Otomatik ürün bilgilerini getir
        product = self.db.find_product_by_barcode(barcode)
        if product:
            # Ürün bulunduğunda bilgileri göster
            self.current_product = product
            self.product_info_label.setText(f"Ürün: {product['name']}")
            self.initial_price_label.setText(f"{product['initial_price']:.2f} TL")
            self.current_price_label.setText(f"{product['unit_price']:.2f} TL")

            # Yeni fiyat için mevcut fiyatı öner
            self.new_price_spin.setValue(product['unit_price'])

            # Fiyat güncelleme alanlarını etkinleştir
            self.price_group.setEnabled(True)

            # Miktar alanına odaklan
            self.qty_spin.setFocus()
            self.qty_spin.selectAll()
        else:
            self.current_product = None
            self.product_info_label.setText("Ürün bulunamadı!")
            self.price_group.setEnabled(False)
            QMessageBox.warning(self, "Bulunamadı", "Barkod kayıtlı değil.")

    def add_stock(self):
        if not self.current_product:
            code = self.barcode_edit.text().strip()
            row = self.db.find_product_by_barcode(code)
            if not row:
                QMessageBox.warning(self, "Bulunamadı", "Barkod kayıtlı değil.")
                return
            self.current_product = row

        qty = self.qty_spin.value()
        new_price = self.new_price_spin.value()
        product_id = self.current_product["id"]
        
        # Stok girişini yap ve yeni fiyatı kaydet
        try:
            # Önce stok girişini yap
            self.db.change_stock(
                product_id,
                qty,
                "PURCHASE",
                new_price
            )
            
            # Birim fiyatı güncelleme onaylandıysa
            price_updated = False
            if self.update_price_check.isChecked():
                # Fiyat güncelle ve sonucu kontrol et
                if self.db.update_unit_price(product_id, new_price):
                    price_updated = True
                else:
                    # Veritabanı bağlantısını yenilemeyi dene
                    self.db.refresh_connection()
                    
                    # Tekrar güncelleme işlemini dene
                    if self.db.update_unit_price(product_id, new_price):
                        price_updated = True
                    else:
                        QMessageBox.warning(
                            self, 
                            "Uyarı", 
                            "Fiyat güncelleme işlemi başarısız oldu. Veri kaydedildi ancak fiyat güncellenmedi."
                        )
            
            # İşlem başarılı mesajı
            message = f"{qty} adet stok eklendi."
            if price_updated:
                message += f"\nBirim fiyat {new_price:.2f} TL olarak güncellendi."
                
            QMessageBox.information(self, "Tamam", message)
            
            # Tüm UI bileşenlerini güncelle
            self.force_ui_update()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"İşlem sırasında bir hata oluştu: {str(e)}")
            return

        # İşlem başarılı, alanları temizle
        self.barcode_edit.clear()
        self.qty_spin.setValue(1)
        self.product_info_label.setText("Ürün bilgisi: ")
        self.price_group.setEnabled(False)
        self.update_price_check.setChecked(False)
        self.current_product = None

    def force_ui_update(self):
        """UI'daki tüm ilgili bileşenleri günceller"""
        # Ana pencereye referans al
        main_window = self.window()
        
        # Ürünler sekmesini güncelle
        if hasattr(main_window, 'product_tab'):
            main_window.product_tab.refresh()
        
        # Veritabanı bağlantısını yenile ve diğer sekmeleri güncelle
        self.db.refresh_connection()
        self.refresh_products()
        
        # Arama sekmesini de güncelle
        if hasattr(main_window, 'search_tab') and main_window.search_tab.search_edit.text():
            main_window.search_tab.search_products()


# -------- Ürün Silme sekmesi --------------------------------------
class DeleteProductTab(QWidget):
    def __init__(self, db: DatabaseManager, refresh_products):
        super().__init__()
        self.db = db
        self.refresh_products = refresh_products
        self.products = []

        layout = QVBoxLayout(self)
        
        # Ürün seçme combobox'ı
        form = QFormLayout()
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(300)
        form.addRow("Silinecek Ürün:", self.product_combo)
        layout.addLayout(form)
        
        # Silme butonu
        delete_btn = QPushButton("Ürünü Sil")
        delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        delete_btn.clicked.connect(self.delete_product)
        layout.addWidget(delete_btn)
        
        # Uyarı etiketi
        warning_label = QLabel(
            "DİKKAT: Silme işlemi geri alınamaz!\n"
            "Ürünle ilgili tüm stok hareketleri de silinecektir.")
        warning_label.setStyleSheet("color: red;")
        layout.addWidget(warning_label)

        self.update_product_list()

    def update_product_list(self):
        """Combobox'a ürünleri doldur"""
        self.product_combo.clear()
        self.products = self.db.list_products()
        for product in self.products:
            self.product_combo.addItem(f"{product['name']} (Barkod: {product['barcode']})", product['id'])

    def delete_product(self):
        """Seçilen ürünü sil"""
        if self.product_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Seçim Yapın", "Silmek için bir ürün seçmelisiniz.")
            return

        product_id = self.product_combo.currentData()
        product_name = self.product_combo.currentText().split(" (Barkod:")[0]

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
                self.update_product_list()
                self.refresh_products()  # Ana ürün listesini güncelle
            else:
                QMessageBox.critical(self, "Hata", "Ürün silinirken bir hata oluştu.")


# -------- Rapor Sekmesi -----------------------------------------
class ReportTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)

        # Günlük satış raporu tablosu
        layout.addWidget(QLabel("Günlük Satış Raporu"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ürün", "Satış Adedi", "Gelir"])
        layout.addWidget(self.table)

        # Excel butonu
        export_btn = QPushButton("Excel'e Aktar")
        export_btn.clicked.connect(self.export_to_excel)
        layout.addWidget(export_btn)

        # Tabloyu doldur
        self.refresh_report()

    def refresh_report(self):
        """Tabloyu günlük satış verileriyle doldur"""
        self.table.setRowCount(0)
        sales = self.db.daily_sales_report()

        if not sales:
            self.table.setRowCount(1)
            self.table.setSpan(0, 0, 1, 3)
            self.table.setItem(0, 0, QTableWidgetItem("Bugün için satış kaydı bulunmuyor."))
            self.table.item(0, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return

        # Verileri göster
        for r, row_data in enumerate(sales):
            self.table.insertRow(r)
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                if c == 2:  # Para birimi formatı
                    item = QTableWidgetItem(f"{value:.2f} TL")
                self.table.setItem(r, c, item)

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

        # Rapor sekmesi
        self.report_tab = ReportTab(self.db)
        self.tabs.addTab(self.report_tab, "Raporlar")

        # Sekme değişikliklerini takip et
        self.tabs.currentChanged.connect(self.tab_changed)

    def tab_changed(self, index):
        """Sekme değiştiğinde gerekli yenilemeleri yap"""
        if index == 0:  # Ürünler sekmesi
            self.product_tab.refresh()
        elif index == 6:  # Rapor sekmesi
            self.report_tab.refresh_report()

    def closeEvent(self, event):
        """Pencere kapatıldığında veritabanı bağlantısını kapat"""
        self.db.close()
        event.accept()

