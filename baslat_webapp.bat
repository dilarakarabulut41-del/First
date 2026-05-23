@echo off
chcp 65001 >nul 2>&1
title AutoCAD Degerlendirme Sistemi

echo.
echo ================================================
echo       AutoCAD Degerlendirme Sistemi
echo ================================================
echo.

:: ── Conda kontrolü ──────────────────────────────
where conda >nul 2>&1
if errorlevel 1 (
    echo [HATA] Conda bulunamadi!
    echo Lutfen once setup_ortam.bat dosyasini calistirin.
    pause & exit /b 1
)

:: ── Ortam kontrolü ───────────────────────────────
conda env list 2>nul | findstr /C:"autocad-degerlendirme" >nul 2>&1
if errorlevel 1 (
    echo [HATA] autocad-degerlendirme ortami bulunamadi!
    echo Lutfen once setup_ortam.bat dosyasini calistirin.
    pause & exit /b 1
)

:: ── .env kontrolü ────────────────────────────────
if not exist ".env" (
    echo [HATA] .env dosyasi bulunamadi!
    echo setup_ortam.bat calistirip .env dosyasini doldurun.
    pause & exit /b 1
)

:: API key dolu mu?
findstr "sk-" ".env" >nul 2>&1
if errorlevel 1 (
    echo [UYARI] .env dosyasinda OpenAI API anahtari eksik!
    echo Notepad ile .env dosyasini ac ve OPENAI_API_KEY satirini doldur.
    echo.
    set /p devam="Yine de devam etmek istiyor musun? (e/h): "
    if /i not "%devam%"=="e" ( pause & exit /b 1 )
)

:: ── Ortamı aktifleştir ───────────────────────────
echo Ortam aktif ediliyor...
call conda activate autocad-degerlendirme

:: ── Port oku ─────────────────────────────────────
for /f "tokens=2 delims==" %%a in ('findstr /i "^PORT=" .env 2^>nul') do set PORT=%%a
if "%PORT%"=="" set PORT=5000

echo.
echo ================================================
echo   Uygulama baslatiliyor...
echo.
echo   Tarayicida su adresi ac:
echo   http://localhost:%PORT%
echo.
echo   Kapatmak icin: Ctrl+C
echo ================================================
echo.

:: Tarayıcıyı 2 sn sonra aç
start /b cmd /c "timeout /t 2 >nul && start http://localhost:%PORT%"

:: Flask'ı çalıştır
python webapp/app.py

echo.
echo Uygulama kapatildi.
pause
