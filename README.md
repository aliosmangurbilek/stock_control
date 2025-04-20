# Stock Management Application

A simple application for managing product inventory with barcode scanning support.

## Features

- Track product inventory (add, edit, delete products)
- Barcode scanning integration
- Search products by name
- View product details

## Barcode Scanning Setup

The application supports barcode scanning through the following methods:

1. **Hardware Barcode Scanner**: Connect a USB barcode scanner that functions as a keyboard input device. When you scan a barcode, it will automatically input the barcode value into the focused barcode field.

2. **Manual Input**: You can manually enter barcodes in the barcode field and press Enter to simulate a scan.

## How to Use Barcode Scanning

1. Open the product form by clicking "Yeni Ürün Ekle" or "Barkod ile Ürün Ara"
2. Place your cursor in the "Barkod" field
3. Scan a barcode using your hardware scanner or enter it manually
4. If the barcode exists in the database, the product details will automatically populate
5. If it's a new product, you can fill in the details and save it with the scanned barcode

## Further Enhancements

For more sophisticated barcode scanning:

- For mobile integration, consider using camera-based scanning libraries
- For continuous scanning, implement a listening mode for the scanner input
- For inventory operations, add batch scanning capabilities
