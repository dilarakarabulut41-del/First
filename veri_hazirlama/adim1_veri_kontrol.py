"""
ADIM 1: Veri Kontrolü
Çalıştır: python veri_hazirlama/adim1_veri_kontrol.py
Amaç: Drive'dan indirdiğin verilerin düzgün olup olmadığını kontrol eder.
"""

import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DRIVE_PATH = Path(os.getenv("DRIVE_DATA_PATH", "./drive"))
CIZIMLER = DRIVE_PATH / "cizimler"
NOTLAR = DRIVE_PATH / "notlar"
TALIMATLAR = DRIVE_PATH / "talimatlar"


def kontrol_et():
    print("=" * 60)
    print("VERİ KONTROL RAPORU")
    print("=" * 60)
    hatalar = []

    for klasor in [CIZIMLER, NOTLAR, TALIMATLAR]:
        if klasor.exists():
            print(f"✓ Klasör bulundu: {klasor}")
        else:
            print(f"✗ Klasör YOK: {klasor}")
            hatalar.append(f"Klasör bulunamadı: {klasor}")

    print()

    if CIZIMLER.exists():
        pdfler = list(CIZIMLER.glob("**/*.pdf"))
        print(f"📄 Toplam PDF sayısı: {len(pdfler)}")
        for pdf in pdfler[:5]:
            print(f"   - {pdf.name}")
        if len(pdfler) > 5:
            print(f"   ... ve {len(pdfler) - 5} tane daha")

    print()

    if NOTLAR.exists():
        exceller = list(NOTLAR.glob("*.xlsx")) + list(NOTLAR.glob("*.xls"))
        print(f"📊 Toplam Excel dosyası: {len(exceller)}")
        for excel in exceller:
            print(f"\n   Dosya: {excel.name}")
            try:
                df = pd.read_excel(excel)
                print(f"   Kolonlar: {list(df.columns)}")
                print(f"   Satır sayısı: {len(df)}")
                print(df.head(3).to_string(index=False))
            except Exception as e:
                print(f"   HATA: {e}")
                hatalar.append(f"Excel okunamadı: {excel.name}: {e}")

    print()

    if TALIMATLAR.exists():
        txtler = list(TALIMATLAR.glob("*.txt"))
        print(f"📝 Talimat dosyası sayısı: {len(txtler)}")
        for txt in txtler:
            with open(txt, encoding="utf-8", errors="ignore") as f:
                icerik = f.read()
            print(f"   {txt.name}: {len(icerik)} karakter")

    print()
    print("=" * 60)
    if hatalar:
        print(f"⚠️  {len(hatalar)} sorun bulundu:")
        for h in hatalar:
            print(f"   - {h}")
    else:
        print("✅ Tüm veriler hazır! Adım 2'ye geçebilirsin.")
    print("=" * 60)


if __name__ == "__main__":
    kontrol_et()
