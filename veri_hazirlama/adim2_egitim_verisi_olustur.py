"""
ADIM 2: Eğitim Verisi Oluşturma
Çalıştır: python veri_hazirlama/adim2_egitim_verisi_olustur.py
Amaç: PDF çizimler + Excel notları birleştirip OpenAI'nin anlayacağı
      JSONL formatına çevirir. 70/20/10 olarak böler.
"""

import os
import json
import base64
import random
import re
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from pdf2image import convert_from_path
from PIL import Image
import io

load_dotenv()

DRIVE_PATH = Path(os.getenv("DRIVE_DATA_PATH", "./drive"))
CIZIMLER = DRIVE_PATH / "cizimler"
NOTLAR_KLASOR = DRIVE_PATH / "notlar"
TALIMATLAR = DRIVE_PATH / "talimatlar"
CIKTI_KLASOR = Path("./egitim_verisi")

SISTEM_MESAJI = """Sen deneyimli bir mimarlık eğitmenisin. Öğrencilerin AutoCAD çizimlerini değerlendiriyorsun.
Verilen değerlendirme talimatlarına göre çizimi analiz et.
Cevabını şu formatta ver:

NOT: [0-100 arası sayı]
GENEL_DEGERLENDIRME: [2-3 cümle genel değerlendirme]
GUCLU_YONLER: [güçlü yönleri listele]
GELISTIRILECEK_YONLER: [geliştirilmesi gereken yönleri listele]
TAVSIYELER: [öğrenciye somut tavsiyeler]"""


def isim_esles(pdf_isim: str, excel_isim: str) -> bool:
    def temizle(s):
        s = s.lower().strip().replace("_", " ").replace("-", " ")
        for t, l in {"ş":"s","ç":"c","ğ":"g","ü":"u","ö":"o","ı":"i","Ş":"s","Ç":"c","Ğ":"g","Ü":"u","Ö":"o","İ":"i"}.items():
            s = s.replace(t, l)
        return re.sub(r"\s+", " ", re.sub(r"\.pdf$", "", s))
    p, e = temizle(pdf_isim), temizle(excel_isim)
    return p == e or p in e or e in p


def pdf_to_base64(pdf_yolu: Path) -> str | None:
    try:
        sayfalar = convert_from_path(str(pdf_yolu), dpi=150, first_page=1, last_page=1)
        if not sayfalar:
            return None
        img = sayfalar[0]
        img.thumbnail((1024, 1024), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"  UYARI: {pdf_yolu.name}: {e}")
        return None


def talimat_oku() -> str:
    talimatlar = []
    for txt in TALIMATLAR.glob("*.txt"):
        with open(txt, encoding="utf-8", errors="ignore") as f:
            talimatlar.append(f"=== {txt.name} ===\n{f.read()}")
    return "\n\n".join(talimatlar) if talimatlar else "Değerlendirme talimatı bulunamadı."


def notlari_yukle() -> pd.DataFrame:
    tum_df = []
    for excel in list(NOTLAR_KLASOR.glob("*.xlsx")) + list(NOTLAR_KLASOR.glob("*.xls")):
        df = pd.read_excel(excel)
        df.columns = [str(c).strip().lower() for c in df.columns]
        tum_df.append(df)
    if not tum_df:
        raise FileNotFoundError(f"Excel bulunamadı: {NOTLAR_KLASOR}")
    df = pd.concat(tum_df, ignore_index=True)
    print(f"Toplam {len(df)} öğrenci kaydı. Kolonlar: {list(df.columns)}")
    return df


def kolon_bul(df, isimler):
    for isim in isimler:
        for k in df.columns:
            if isim.lower() in k.lower():
                return k
    return None


def ornekleri_olustur():
    CIKTI_KLASOR.mkdir(exist_ok=True)
    talimat = talimat_oku()
    df = notlari_yukle()

    isim_k = kolon_bul(df, ["ogrenci", "isim", "ad", "name", "student"])
    not_k = kolon_bul(df, ["not", "puan", "grade", "score", "note"])
    yorum_k = kolon_bul(df, ["yorum", "comment", "aciklama", "feedback"])

    if not isim_k or not not_k:
        print(f"⚠️ Kolon bulunamadı! Mevcut: {list(df.columns)}")
        return

    pdfler = list(CIZIMLER.glob("**/*.pdf"))
    print(f"{len(pdfler)} PDF işlenecek...")
    ornekler, eslesmeyen = [], []

    for i, pdf in enumerate(pdfler):
        print(f"[{i+1}/{len(pdfler)}] {pdf.name}", end=" ... ", flush=True)
        satir = next((r for _, r in df.iterrows() if isim_esles(pdf.stem, str(r[isim_k]))), None)
        if satir is None:
            print("eşleşme yok, atlanıyor")
            eslesmeyen.append(pdf.name)
            continue

        img_b64 = pdf_to_base64(pdf)
        if not img_b64:
            print("dönüştürme hatası, atlanıyor")
            continue

        not_val = satir[not_k]
        yorum = str(satir[yorum_k]) if yorum_k and pd.notna(satir.get(yorum_k)) else ""
        asistan = f"NOT: {not_val}\n"
        if yorum:
            asistan += f"GENEL_DEGERLENDIRME: {yorum}\n"
        asistan += "GUCLU_YONLER: [öğrenildi]\nGELISTIRILECEK_YONLER: [öğrenildi]\nTAVSIYELER: [öğrenildi]"

        ornekler.append({"messages": [
            {"role": "system", "content": SISTEM_MESAJI},
            {"role": "user", "content": [
                {"type": "text", "text": f"Değerlendirme Talimatları:\n{talimat}\n\nBu öğrenci çizimini değerlendir:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]},
            {"role": "assistant", "content": asistan}
        ]})
        print(f"✓ (not: {not_val})")

    if len(ornekler) < 10:
        print(f"⚠️ Sadece {len(ornekler)} örnek var, en az 10 gerekli.")
        return

    random.seed(42)
    random.shuffle(ornekler)
    n = len(ornekler)
    e, v = int(n*.7), int(n*.2)
    splits = {"egitim.jsonl": ornekler[:e], "validasyon.jsonl": ornekler[e:e+v], "test.jsonl": ornekler[e+v:]}
    for fname, data in splits.items():
        yol = CIKTI_KLASOR / fname
        with open(yol, "w", encoding="utf-8") as f:
            for o in data:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        print(f"✓ {fname}: {len(data)} örnek")
    print(f"\n✅ Hazır! Eğitim:{e} Validasyon:{v} Test:{n-e-v}")
    print("Sonraki: python model_egitimi/adim3_modeli_egit.py")


if __name__ == "__main__":
    ornekleri_olustur()
