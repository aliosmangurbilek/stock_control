"""
build_exe.py
PyInstaller kullanarak .exe dosyası oluşturur.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_windows_executable():
    """
    PyInstaller kullanarak Windows .exe dosyası oluşturmak için ana fonksiyon
    """
    print("Stok Yönetim Uygulaması EXE oluşturma aracı")
    print("=" * 50)
    
    # İşletim sistemini belirle ve doğru ayırıcıyı seç
    path_separator = ";" if sys.platform.startswith("win") else ":"
    print(f"İşletim Sistemi: {sys.platform}, Ayırıcı: '{path_separator}'")
    
    # Gerekli paketleri kontrol et ve yükle
    print("Gerekli paketler kontrol ediliyor...")
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller yükleniyor...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Projenin kök dizinini al
    project_root = Path(__file__).resolve().parent
    
    # Veri klasörü varsa, kopyalanacak verileri hazırla
    data_dir = project_root / "data"
    data_args = []
    
    if data_dir.exists():
        print(f"Veri dizini bulundu: {data_dir}")
        # SQLite veritabanı dosyasını kopyala (eğer varsa)
        data_args = [
            "--add-data", f"{data_dir}{path_separator}data"  # İşletim sistemine göre ayırıcı
        ]
    
    # QSS stil dosyası varsa ekle
    resources_dir = project_root / "resources"
    if resources_dir.exists():
        print(f"Resources dizini bulundu: {resources_dir}")
        data_args.extend([
            "--add-data", f"{resources_dir}{path_separator}resources"  # İşletim sistemine göre ayırıcı
        ])
    
    # İkon dosyası varsa ekle
    icon_path = resources_dir / "icon.ico"
    icon_args = []
    if icon_path.exists():
        print(f"İkon dosyası bulundu: {icon_path}")
        icon_args = ["--icon", str(icon_path)]
    
    # PyInstaller komut satırı argümanlarını oluştur
    pyinstaller_args = [
        "pyinstaller",
        "--name=StokYonetimi",
        "--onefile",  # Tek dosya olarak paketleme (alternatif: --onedir)
        "--windowed",  # Konsol penceresi gösterme
        *icon_args,
        *data_args,
        "--clean",  # Önceki derleme dosyalarını temizle
        "--noconfirm",  # Var olan dosyaların üzerine yaz
        # "--debug=all",  # Hata ayıklama için
        str(project_root / "app.py")  # Ana Python dosyası
    ]
    
    print("\nPyInstaller çalıştırılıyor...")
    print(f"Komut: {' '.join(pyinstaller_args)}")
    
    try:
        # PyInstaller'ı çalıştır
        subprocess.check_call(pyinstaller_args)
        
        print("\nEXE dosyası başarıyla oluşturuldu!")
        print(f"Dosya konumu: {project_root}/dist/StokYonetimi.exe")
        
    except subprocess.CalledProcessError as e:
        print(f"\nHata: PyInstaller çalışırken bir sorun oluştu: {e}")
        return False
    
    return True

if __name__ == "__main__":
    create_windows_executable()
