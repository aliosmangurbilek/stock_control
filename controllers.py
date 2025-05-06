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
from PyQt6.QtCore import Qt, QSize
from models import DatabaseManager
from reports import export_daily_sales
from sqlite3 import IntegrityError
from barcode_handler import BarcodeHandler
from datetime import datetime
from PyQt6.QtGui import QIcon, QPixmap
from pathlib import Path

def get_icon(name):
    """Load an icon from resources folder"""
    icon_path = Path(__file__).resolve().parent / "resources" / "icons" / f"{name}.png"
    if icon_path.exists():
        return QIcon(str(icon_path))
    return QIcon()

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
        self.last_scan_time = 0
        self.scan_cooldown = 500

        # Main layout with proper spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Barcode scanning section with styled frame
        scan_frame = QGroupBox("Ürün Tarama")
        scan_layout = QVBoxLayout(scan_frame)

        # Barcode input with icon
        barcode_layout = QHBoxLayout()
        barcode_icon = QLabel()
        barcode_icon.setPixmap(QPixmap(str(Path(__file__).parent / "resources" / "icons" / "barcode.png")).scaled(24, 24))
        barcode_layout.addWidget(barcode_icon)

        self.barcode_edit = QLineEdit()
        self.barcode_edit.setPlaceholderText("Barkod okutun veya girin...")
        self.barcode_edit.textChanged.connect(self.on_barcode_changed)
        barcode_layout.addWidget(self.barcode_edit)

        add_btn = QPushButton("Ekle")
        add_btn.clicked.connect(self.scan)
        add_btn.setProperty("class", "success")
        barcode_layout.addWidget(add_btn)

        scan_layout.addLayout(barcode_layout)
        main_layout.addWidget(scan_frame)

        # Latest scanned item display
        self.latest_item_label = QLabel("Son eklenen ürün: -")
        self.latest_item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.latest_item_label.setStyleSheet("font-size: 14px; padding: 5px;")
        main_layout.addWidget(self.latest_item_label)

        # Cart table with improved styling
        cart_frame = QGroupBox("Sepet")
        cart_layout = QVBoxLayout(cart_frame)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Ürün", "Adet", "Birim Fiyat", "Toplam", "İşlem"]
        )

        # Set table properties for better appearance
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        cart_layout.addWidget(self.table)
        main_layout.addWidget(cart_frame, 1)  # Give table more space with stretch factor

        # Bottom panel with total and checkout button
        bottom_panel = QWidget()
        bottom_layout = QHBoxLayout(bottom_panel)

        # Total display with large, bold font
        self.total_lbl = QLabel("Toplam: 0.00 TL")
        self.total_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_layout.addWidget(self.total_lbl, 1)

        # Checkout button with icon
        complete_btn = QPushButton(" Satışı Tamamla")
        complete_btn.setIcon(get_icon("checkout"))
        complete_btn.setIconSize(QSize(24, 24))
        complete_btn.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        complete_btn.setProperty("class", "success")
        complete_btn.clicked.connect(self.complete_sale)
        complete_btn.setMinimumWidth(200)
        bottom_layout.addWidget(complete_btn)

        main_layout.addWidget(bottom_panel)

        # Barkod okuyucu entegrasyonu
        self.barcode_handler = BarcodeHandler()
        self.barcode_edit.installEventFilter(self.barcode_handler)
        self.barcode_handler.barcode_detected.connect(self.handle_barcode)

    def display_scanned_animation(self, name):
        """Show animation when item is scanned"""
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

        # Save original stylesheet
        original_style = self.latest_item_label.styleSheet()

        # Update text and show highlight
        self.latest_item_label.setText(f"Eklendi: {name}")
        self.latest_item_label.setStyleSheet(
            "background-color: #007ACC; color: white; border-radius: 5px; padding: 8px; font-weight: bold;")

        # Create fade animation
        animation = QPropertyAnimation(self.latest_item_label, b"styleSheet")
        animation.setDuration(1500)
        animation.setStartValue(
            "background-color: #007ACC; color: white; border-radius: 5px; padding: 8px; font-weight: bold;")
        animation.setEndValue(original_style)
        animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        animation.start()

    def on_barcode_changed(self):
        """Barkod alanındaki metin değiştiğinde kontrol et, Enter tuşuna basıldığında işlem yapma"""
        # Bu metod boş kalacak, böylece Enter tuşu ile tetiklenmeyecek
        pass

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri hemen işle"""
        self.barcode_edit.setText(barcode)
        self.scan()
        self.barcode_edit.setFocus()  # İmleci tekrar barkod alanına getir

    def scan(self):
        import time
        current_time = int(time.time() * 1000)  # Şu anki zaman (milisaniye)
        
        # Çift işlemeyi önle - son tarama ile şimdiki arasında yeterince zaman geçti mi?
        if current_time - self.last_scan_time < self.scan_cooldown:
            return
            
        self.last_scan_time = current_time
        
        code = self.barcode_edit.text().strip()
        self.barcode_edit.clear()

        if not code:
            return

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
        for pid, item in self.cart.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            subtotal = item["qty"] * item["price"]
            
            # İlk 4 sütun için mevcut verileri ekle
            for c, val in enumerate(
                [item["name"], item["qty"],
                 f"{item['price']:.2f}", f"{subtotal:.2f}"]
            ):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
                
            # 5. sütun için silme butonu
            delete_btn = QPushButton("Sil")
            delete_btn.setStyleSheet("background-color: #ff6b6b;")
            delete_btn.clicked.connect(lambda checked, pid=pid: self.remove_item(pid))
            self.table.setCellWidget(r, 4, delete_btn)
            
            total += subtotal
            
        self.total_lbl.setText(f"Toplam: {total:.2f}")
        
        # Sütun genişliklerini ayarla
        self.table.setColumnWidth(4, 80)  # Silme butonu için sabit genişlik
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Ürün adı esnek olsun
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    
    def remove_item(self, product_id):
        """Sepetten bir ürünü kaldır"""
        if product_id in self.cart:
            # Stoku geri iade et
            self.db.change_stock(product_id, self.cart[product_id]["qty"], "ADJUST")
            
            # Sepetten kaldır
            del self.cart[product_id]
            
            # Tabloyu güncelle
            self.refresh()

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
        self.barcode_field_has_focus = False  # Focus durumunu takip etmek için

        form = QFormLayout(self)
        self.barcode_edit = QLineEdit()

        # Focus olaylarını izlemek için
        self.barcode_edit.focusInEvent = self.barcode_focus_in
        self.barcode_edit.focusOutEvent = self.barcode_focus_out

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

    def barcode_focus_in(self, event):
        """Barkod alanı odak kazandığında"""
        self.barcode_field_has_focus = True
        # Orijinal fonksiyonu çağır
        QLineEdit.focusInEvent(self.barcode_edit, event)

    def barcode_focus_out(self, event):
        """Barkod alanı odak kaybettiğinde"""
        self.barcode_field_has_focus = False
        # Orijinal fonksiyonu çağır
        QLineEdit.focusOutEvent(self.barcode_edit, event)

    def handle_barcode(self, barcode):
        """Barkod tarayıcıdan gelen değeri otomatik doldur"""
        # Eğer barkod alanında odak yoksa, barkodu işleme
        if not self.barcode_field_has_focus:
            return
            
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
        self.selected_product = None

        layout = QVBoxLayout(self)
        
        # Arama alanı
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ürün adı veya barkod ile arayın...")
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
        
        # Arama sonuçları tablosu
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Ürün Adı", "Barkod", "Konum", "Stok"])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.itemSelectionChanged.connect(self.product_selected)
        layout.addWidget(self.results_table)
        
        # Seçilen ürün bilgisi
        self.product_info = QLabel("Silinecek ürünü seçin")
        self.product_info.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.product_info)
        
        # Silme butonu
        delete_btn = QPushButton("Seçilen Ürünü Sil")
        delete_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px;")
        delete_btn.clicked.connect(self.delete_product)
        layout.addWidget(delete_btn)
        
        # Uyarı etiketi
        warning_label = QLabel(
            "DİKKAT: Silme işlemi geri alınamaz!\n"
            "Ürünle ilgili tüm stok hareketleri de silinecektir.")
        warning_label.setStyleSheet("color: red; margin-top: 10px;")
        layout.addWidget(warning_label)

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
        self.selected_product = None
        self.product_info.setText("Silinecek ürünü seçin")
        
        if not products:
            QMessageBox.information(self, "Sonuç Yok", f"'{query}' ile eşleşen ürün bulunamadı.")
            return
            
        for product in products:
            stock = self.db.get_stock_level(product["id"])
            r = self.results_table.rowCount()
            self.results_table.insertRow(r)
            self.results_table.setItem(r, 0, QTableWidgetItem(product["name"]))
            self.results_table.setItem(r, 1, QTableWidgetItem(product["barcode"]))
            self.results_table.setItem(r, 2, QTableWidgetItem(product["location"]))
            self.results_table.setItem(r, 3, QTableWidgetItem(str(stock)))
            
            # İlk sütunda ürün ID'sini sakla
            self.results_table.item(r, 0).setData(Qt.ItemDataRole.UserRole, product["id"])
        
        self.results_table.resizeColumnsToContents()
        
        # Tek sonuç varsa otomatik seç
        if self.results_table.rowCount() == 1:
            self.results_table.selectRow(0)

    def product_selected(self):
        """Tablodan ürün seçildiğinde"""
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            self.selected_product = None
            self.product_info.setText("Silinecek ürünü seçin")
            return
        
        # İlk sütundan ürün ID'sini al
        selected_row = selected_items[0].row()
        product_id = self.results_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        product_name = self.results_table.item(selected_row, 0).text()
        product_barcode = self.results_table.item(selected_row, 1).text()
        stock = self.results_table.item(selected_row, 3).text()
        
        self.selected_product = {
            "id": product_id,
            "name": product_name,
            "barcode": product_barcode
        }
        
        # Seçilen ürün bilgisini göster
        self.product_info.setText(f"Seçilen Ürün: {product_name} (Barkod: {product_barcode}, Stok: {stock})")

    def delete_product(self):
        """Seçilen ürünü sil"""
        if not self.selected_product:
            QMessageBox.warning(self, "Seçim Yapın", "Silmek için bir ürün seçmelisiniz.")
            return

        product_id = self.selected_product["id"]
        product_name = self.selected_product["name"]

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
                self.results_table.setRowCount(0)
                self.selected_product = None
                self.product_info.setText("Silinecek ürünü seçin")
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

        layout.addLayout(search_layout)

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
        layout.addWidget(self.table)

        # Tablo ayarları
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

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
        self.setWindowIcon(get_icon("store"))

        # Set minimum size for better appearance
        self.setMinimumSize(1000, 700)

        # Veri katmanı - tek bir bağlantı için
        self.db = DatabaseManager()

        # Create status bar
        self.statusBar().showMessage("Hazır")

        # Create toolbar
        self.toolbar = self.addToolBar("Main")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(24, 24))

        # Add quick access buttons to toolbar
        self.add_toolbar_actions()

        # Merkez widget olarak tab widget oluştur
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Add tabs with icons
        self.product_tab = ProductTab(self.db)
        self.tabs.addTab(self.product_tab, get_icon("product"), "Ürünler")

        self.search_tab = SearchProductTab(self.db)
        self.tabs.addTab(self.search_tab, get_icon("search"), "Ürün Ara")

        self.add_tab = AddProductTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.add_tab, get_icon("add"), "Ürün Ekle")

        self.sales_tab = SalesTab(self.db)
        self.tabs.addTab(self.sales_tab, get_icon("sales"), "Satış")

        self.stock_in_tab = StockInTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.stock_in_tab, get_icon("inventory"), "Stok Girişi")

        self.delete_tab = DeleteProductTab(self.db, self.product_tab.refresh)
        self.tabs.addTab(self.delete_tab, get_icon("delete"), "Ürün Sil")

        self.price_history_tab = PriceHistoryTab(self.db)
        self.tabs.addTab(self.price_history_tab, get_icon("price"), "Fiyat Takibi")

        self.report_tab = ReportTab(self.db)
        self.tabs.addTab(self.report_tab, get_icon("report"), "Raporlar")

        # Sekme değişikliklerini takip et
        self.tabs.currentChanged.connect(self.tab_changed)

        # Apply consistent padding to main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def add_toolbar_actions(self):
        """Add quick access buttons to toolbar"""
        # Scan button for quick barcode scanning
        scan_action = self.toolbar.addAction(get_icon("barcode"), "Barkod Tara")
        scan_action.triggered.connect(self.quick_scan)

        self.toolbar.addSeparator()

        # Quick add product
        add_product = self.toolbar.addAction(get_icon("add"), "Yeni Ürün")
        add_product.triggered.connect(lambda: self.tabs.setCurrentIndex(2))

        # Quick sale
        sale_action = self.toolbar.addAction(get_icon("sales"), "Satış")
        sale_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))

        # Stock action
        stock_action = self.toolbar.addAction(get_icon("inventory"), "Stok Girişi")
        stock_action.triggered.connect(lambda: self.tabs.setCurrentIndex(4))

        self.toolbar.addSeparator()

        # Report action
        report_action = self.toolbar.addAction(get_icon("report"), "Rapor")
        report_action.triggered.connect(lambda: self.tabs.setCurrentIndex(7))

    def tab_changed(self, index):
        """Handle tab change events"""
        # Get the tab name for status bar
        tab_text = self.tabs.tabText(index)
        self.statusBar().showMessage(f"'{tab_text}' sekmesine geçildi")

        # Refresh content as needed
        if index == 0:  # Product tab
            self.product_tab.refresh()
        elif index == 7:  # Reports tab
            self.report_tab.refresh_report()

    def quick_scan(self):
        """Open quick scan dialog"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Hızlı Barkod Tarama")
        layout = QVBoxLayout(dialog)

        instruction = QLabel("Barkod tarayın veya girin:")
        layout.addWidget(instruction)

        barcode_input = QLineEdit()
        barcode_input.setFocus()
        layout.addWidget(barcode_input)

        result_label = QLabel("Sonuç bekleniyor...")
        layout.addWidget(result_label)

        # Add barcode handler
        handler = BarcodeHandler()
        barcode_input.installEventFilter(handler)

        def process_barcode(code):
            product = self.db.find_product_by_barcode(code)
            if product:
                result_label.setText(f"<b>{product['name']}</b> - Fiyat: <b>{product['unit_price']:.2f} TL</b>")
                result_label.setProperty("class", "success")
                result_label.style().unpolish(result_label)
                result_label.style().polish(result_label)
            else:
                result_label.setText("Ürün bulunamadı!")
                result_label.setProperty("class", "error")
                result_label.style().unpolish(result_label)
                result_label.style().polish(result_label)

        handler.barcode_detected.connect(process_barcode)
        barcode_input.returnPressed.connect(
            lambda: process_barcode(barcode_input.text().strip())
        )

        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setMinimumWidth(400)
        dialog.exec()
