@echo off
:: inventory.db dosyasını her çalıştırıldığında D:\yedek\stok klasörüne kopyalar.
:: /MIR  →  Kaynak klasörü hedefte ayna şeklinde eşler
:: /R:1  →  Hata olursa en fazla 1 kez yeniden dene
:: /W:5  →  Yeniden denemeler arasında 5 saniye bekle
robocopy "%~dp0" "D:\yedek\stok" inventory.db /MIR /R:1 /W:5
