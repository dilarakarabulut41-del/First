@echo off
chcp 65001 >nul 2>&1
title AutoCAD Degerlendirme - Kurulum

echo.
echo ================================================
echo   AutoCAD Degerlendirme Sistemi - KURULUM
echo   Bu pencereyi kapatma! 10-15 dk sürebilir.
echo ================================================
echo.

:: ── Conda kontrolü ──────────────────────────────
where conda >nul 2>&1
if errorlevel 1 (
    echo [HATA] Conda bulunamadi!
    echo.
    echo Lutfen once Anaconda kurun:
    echo   https://www.anaconda.com/download
    echo.
    echo Kurulum sirasinda "Add Anaconda to PATH"
    echo kutucugunu isaretlemeyi unutma!
    echo.
    pause
    exit /b 1
)

echo [1/5] Conda bulundu:
conda --version
echo.

:: ── Ortam var mı kontrol et ──────────────────────
conda env list 2>nul | findstr /C:"autocad-degerlendirme" >nul 2>&1
if not errorlevel 1 (
    echo [2/5] Ortam zaten kurulu, guncelleniyor...
    call conda activate autocad-degerlendirme
    goto pip_kurulum
)

:: ── Yeni ortam oluştur ───────────────────────────
echo [2/5] Yeni conda ortami olusturuluyor...
echo      Python 3.11 + Poppler yukleniyor...
echo      (Bu adim ~5-10 dk surebilir, bekle)
echo.
conda env create -f environment.yml
if errorlevel 1 (
    echo.
    echo [HATA] Ortam olusturulamadi!
    echo Internet baglantini kontrol et ve tekrar calistir.
    echo.
    pause
    exit /b 1
)
echo.
echo [OK] Ortam olusturuldu!
echo.

:: ── Ortamı aktifleştir ───────────────────────────
echo [3/5] Ortam aktif ediliyor...
call conda activate autocad-degerlendirme
if errorlevel 1 (
    echo [HATA] Ortam aktif edilemedi.
    pause
    exit /b 1
)
echo [OK] autocad-degerlendirme aktif.
echo.

:pip_kurulum
:: ── Pip paketleri ────────────────────────────────
echo [4/5] Python kutuphaneleri yukleniyor...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [HATA] Kutuphaneler yuklenemedi.
    pause
    exit /b 1
)
echo [OK] Tum kutuphaneler yuklendi.
echo.

:: ── .env dosyası ─────────────────────────────────
echo [5/5] Yapilandirma dosyasi hazirlaniyor...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [OK] .env dosyasi olusturuldu.
) else (
    echo [OK] .env dosyasi zaten var.
)

:: ── Klasörleri oluştur ───────────────────────────
if not exist "itirazlar"     mkdir itirazlar
if not exist "egitim_verisi" mkdir egitim_verisi
echo [OK] Klasorler hazir.
echo.

:: ── Poppler testi ────────────────────────────────
python -c "from pdf2image import convert_from_bytes; print('[OK] PDF okuma hazir (Poppler)')" 2>nul
if errorlevel 1 (
    echo [UYARI] Poppler testi basarisiz, tekrar kuruluyor...
    conda install -c conda-forge poppler -y -q
    python -c "from pdf2image import convert_from_bytes; print('[OK] PDF okuma hazir')" 2>nul
)
echo.

echo ================================================
echo   KURULUM TAMAMLANDI!
echo ================================================
echo.
echo Simdi yapman gerekenler:
echo.
echo   1. Bu klasordeki .env dosyasini Notepad ile ac
echo      (Dosya gozukmuyorsa: Dosya Gezgini ^
      echo       Gorunum ^> Gizli ogeler kutusunu isaretle)
echo.
echo   2. Su satirlari doldur:
echo      OPENAI_API_KEY=sk-...anahtarin...
echo      DRIVE_DATA_PATH=C:\Users\adin\Desktop\klasor
echo.
echo   3. baslat_webapp.bat dosyasina cift tikla
echo.
pause
