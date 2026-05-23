"""
Web Uygulaması — 3 sekme:
  1. Toplu Analiz  : klasör seç → tümünü analiz et → Excel + rapor
  2. Tekli Analiz  : PDF yükle → görsel + detaylı bireysel rapor
  3. İtiraz        : öğrenci itiraz eder → yeniden değerlendirme → JSONL/Excel'e kaydedilir
Çalıştır: python webapp/app.py
"""

import os
import re
import base64
import io
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def find_poppler_path() -> str | None:
    """Windows conda ortamında poppler binary yolunu otomatik bul."""
    # 1. Conda aktif ortamından bul (en güvenilir yol)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        p = Path(conda_prefix) / "Library" / "bin"
        if (p / "pdftoppm.exe").exists():
            return str(p)

    # 2. Sistem PATH'inde ara
    pdftoppm = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
    if pdftoppm:
        return str(Path(pdftoppm).parent)

    # 3. Yaygın anaconda/miniconda kurulum yerleri
    home = Path.home()
    env_adi = "autocad-degerlendirme"
    adaylar = [
        home / "anaconda3" / "envs" / env_adi / "Library" / "bin",
        home / "miniconda3" / "envs" / env_adi / "Library" / "bin",
        home / "AppData" / "Local" / "anaconda3" / "envs" / env_adi / "Library" / "bin",
        home / "AppData" / "Local" / "miniconda3" / "envs" / env_adi / "Library" / "bin",
        Path("C:/ProgramData/anaconda3/envs") / env_adi / "Library" / "bin",
    ]
    for aday in adaylar:
        if (aday / "pdftoppm.exe").exists():
            return str(aday)

    return None  # Linux/Mac'te None → PATH'den otomatik alır


POPPLER_PATH = find_poppler_path()
if POPPLER_PATH:
    print(f"[OK] Poppler bulundu: {POPPLER_PATH}")
else:
    print("[INFO] Poppler PATH'den alınacak (Linux/Mac veya conda PATH'i aktif)")
MODEL_ID = os.getenv("FINETUNED_MODEL_ID", "gpt-4o-mini-2024-07-18")
TALIMATLAR_YOLU = Path(os.getenv("DRIVE_DATA_PATH", "./drive")) / "talimatlar"
ITIRAZ_KLASOR = Path("./itirazlar")
ITIRAZ_KLASOR.mkdir(exist_ok=True)

_talimat_cache = None

SISTEM_MESAJI = (
    "Sen deneyimli bir mimarlık eğitmenisin. Öğrencilerin AutoCAD çizimlerini değerlendiriyorsun. "
    "Cevabını SADECE şu formatta ver, başka hiçbir şey ekleme:\n\n"
    "NOT: [0-100 arası tam sayı]\n"
    "GENEL_DEGERLENDIRME: [2-3 cümle genel değerlendirme]\n"
    "GUCLU_YONLER:\n- [madde]\n- [madde]\n"
    "GELISTIRILECEK_YONLER:\n- [madde]\n- [madde]\n"
    "TAVSIYELER:\n- [madde]\n- [madde]"
)

ITIRAZ_SISTEM_MESAJI = (
    "Sen deneyimli bir mimarlık eğitmenisin. Bir öğrenci verdiğin nota itiraz etti. "
    "Çizimi ve itiraz gerekçesini dikkatlice değerlendir. "
    "Adil ve objektif ol — haklı itirazlarda notu revize et, haksız itirazları gerekçeyle reddet.\n"
    "Cevabını SADECE şu formatta ver:\n\n"
    "ITIRAZ_KARARI: [KABUL / KISMI_KABUL / RED]\n"
    "YENI_NOT: [0-100 arası tam sayı]\n"
    "KARAR_GEREKCE: [2-3 cümle karar gerekçesi]\n"
    "GUCLU_YONLER:\n- [madde]\n- [madde]\n"
    "GELISTIRILECEK_YONLER:\n- [madde]\n- [madde]\n"
    "TAVSIYELER:\n- [madde]\n- [madde]"
)


# ── Yardımcı fonksiyonlar ─────────────────────────────────

def talimat_yukle() -> str:
    global _talimat_cache
    if _talimat_cache:
        return _talimat_cache
    talimatlar = []
    if TALIMATLAR_YOLU.exists():
        for txt in TALIMATLAR_YOLU.glob("*.txt"):
            with open(txt, encoding="utf-8", errors="ignore") as f:
                talimatlar.append(f.read())
    _talimat_cache = "\n\n".join(talimatlar) if talimatlar else "Standart mimari çizim değerlendirmesi yap."
    return _talimat_cache


def pdf_to_jpeg_b64(pdf_bytes: bytes) -> str:
    """PDF bytes → base64 JPEG (ilk sayfa, max 1024px).

    Windows'ta NamedTemporaryFile dosyayı kilitler; mkstemp kullanıyoruz.
    Hata oluşursa açıklayıcı mesajla exception fırlatır.
    """
    fd, tmp_yolu = tempfile.mkstemp(suffix=".pdf")
    try:
        os.write(fd, pdf_bytes)
        os.close(fd)          # Windows: dosyayı kapat, sonra poppler okuyabilsin
        kwargs: dict = {"dpi": 150, "first_page": 1, "last_page": 1}
        if POPPLER_PATH:
            kwargs["poppler_path"] = POPPLER_PATH
        sayfalar = convert_from_path(tmp_yolu, **kwargs)
    except Exception as e:
        raise RuntimeError(f"PDF→JPEG dönüşüm hatası: {e}") from e
    finally:
        try:
            os.unlink(tmp_yolu)
        except OSError:
            pass

    if not sayfalar:
        raise RuntimeError("PDF'den sayfa okunamadı (dosya boş veya bozuk olabilir).")
    img = sayfalar[0]
    img.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def pdf_path_to_b64(pdf_yolu: Path) -> str:
    if not pdf_yolu.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {pdf_yolu}")
    return pdf_to_jpeg_b64(pdf_yolu.read_bytes())


def notu_cikart(metin: str) -> str:
    """NOT: veya YENI_NOT: satırından sayıyı çeker."""
    for pattern in [r"YENI_NOT:\s*(\d+)", r"NOT:\s*(\d+)"]:
        m = re.search(pattern, metin)
        if m:
            return m.group(1)
    return "—"


def bolum_cikart(metin: str, bolum: str) -> str:
    """Belirtilen bölüm başlığından sonraki içeriği çeker."""
    m = re.search(rf"{bolum}:\s*(.+?)(?=\n[A-Z_]+:|$)", metin, re.DOTALL)
    return m.group(1).strip() if m else ""


def degerlendirme_yap(img_b64: str, itiraz_metni: str | None = None) -> dict:
    """Tek bir çizimi analiz eder. itiraz_metni varsa itiraz değerlendirmesi yapar."""
    talimat = talimat_yukle()
    sistem = ITIRAZ_SISTEM_MESAJI if itiraz_metni else SISTEM_MESAJI

    kullanici_metin = f"Değerlendirme Talimatları:\n{talimat}\n\n"
    if itiraz_metni:
        kullanici_metin += f"Öğrencinin İtiraz Gerekçesi:\n{itiraz_metni}\n\n"
    kullanici_metin += "Bu öğrenci çizimini değerlendir:"

    yanit = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": sistem},
            {"role": "user", "content": [
                {"type": "text", "text": kullanici_metin},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]}
        ],
        max_tokens=900,
        temperature=0.2
    )
    cevap = yanit.choices[0].message.content
    return {
        "ham_cevap": cevap,
        "not": notu_cikart(cevap),
        "genel": bolum_cikart(cevap, "GENEL_DEGERLENDIRME"),
        "guclu": bolum_cikart(cevap, "GUCLU_YONLER"),
        "gelistir": bolum_cikart(cevap, "GELISTIRILECEK_YONLER"),
        "tavsiye": bolum_cikart(cevap, "TAVSIYELER"),
        "itiraz_karari": bolum_cikart(cevap, "ITIRAZ_KARARI") if itiraz_metni else None,
        "karar_gerekce": bolum_cikart(cevap, "KARAR_GEREKCE") if itiraz_metni else None,
        "token": yanit.usage.total_tokens
    }


def itiraz_kaydet(kayit: dict):
    """İtirazı JSONL ve Excel'e kaydeder."""
    jsonl_yolu = ITIRAZ_KLASOR / "itirazlar.jsonl"
    with open(jsonl_yolu, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")

    # Excel güncelle
    excel_yolu = ITIRAZ_KLASOR / "itirazlar.xlsx"
    yeni_satir = {
        "Tarih": kayit["tarih"],
        "Öğrenci": kayit["ogrenci"],
        "Dosya": kayit["pdf_adi"],
        "Orijinal Not": kayit["orijinal_not"],
        "Yeni Not": kayit["yeni_not"],
        "İtiraz Kararı": kayit["itiraz_karari"],
        "İtiraz Gerekçesi": kayit["itiraz_nedeni"],
        "Karar Gerekçesi": kayit["karar_gerekce"],
        "Tam Değerlendirme": kayit["ham_cevap"]
    }
    if excel_yolu.exists():
        df = pd.read_excel(excel_yolu)
        df = pd.concat([df, pd.DataFrame([yeni_satir])], ignore_index=True)
    else:
        df = pd.DataFrame([yeni_satir])
    df.to_excel(excel_yolu, index=False)


# ── Rotalar ──────────────────────────────────────────────

@app.route("/")
def anasayfa():
    return render_template("index.html")


# --- Toplu Analiz ---

@app.route("/api/klasor-tara", methods=["POST"])
def klasor_tara():
    veri = request.get_json()
    klasor_yolu = veri.get("yol", "").strip()
    if not klasor_yolu:
        return jsonify({"hata": "Klasör yolu boş"}), 400
    klasor = Path(klasor_yolu)
    if not klasor.exists():
        return jsonify({"hata": f"Klasör bulunamadı: {klasor_yolu}"}), 400
    pdfler = sorted(klasor.glob("**/*.pdf"))
    dosyalar = [{"isim": p.name, "yol": str(p), "boyut_kb": round(p.stat().st_size / 1024, 1)} for p in pdfler]
    return jsonify({"dosyalar": dosyalar, "toplam": len(dosyalar)})


@app.route("/api/analiz-et", methods=["POST"])
def analiz_et():
    veri = request.get_json()
    pdf_yolu = Path(veri.get("yol", "").strip())
    if not pdf_yolu.exists():
        return jsonify({"hata": f"Dosya bulunamadı: {pdf_yolu}"}), 400
    try:
        img_b64 = pdf_path_to_b64(pdf_yolu)
        sonuc = degerlendirme_yap(img_b64)
        return jsonify({
            "dosya": pdf_yolu.name,
            "ogrenci": pdf_yolu.stem.replace("_", " ").title(),
            "not": sonuc["not"],
            "degerlendirme": sonuc["ham_cevap"],
            "token": sonuc["token"]
        })
    except Exception as e:
        print(f"[HATA] {pdf_yolu.name}: {e}")
        return jsonify({"hata": str(e)}), 500


@app.route("/api/excel-indir", methods=["POST"])
def excel_indir():
    veri = request.get_json()
    sonuclar = veri.get("sonuclar", [])
    if not sonuclar:
        return jsonify({"hata": "Sonuç yok"}), 400

    df = pd.DataFrame(sonuclar)
    df = df.rename(columns={"dosya": "Dosya Adı", "ogrenci": "Öğrenci Adı",
                             "not": "Not", "degerlendirme": "Değerlendirme"})

    def b(metin, k): return bolum_cikart(str(metin), k)
    df["Genel Değerlendirme"] = df["Değerlendirme"].apply(lambda x: b(x, "GENEL_DEGERLENDIRME"))
    df["Güçlü Yönler"] = df["Değerlendirme"].apply(lambda x: b(x, "GUCLU_YONLER"))
    df["Geliştirilecek Yönler"] = df["Değerlendirme"].apply(lambda x: b(x, "GELISTIRILECEK_YONLER"))
    df["Tavsiyeler"] = df["Değerlendirme"].apply(lambda x: b(x, "TAVSIYELER"))

    kolonlar = ["Öğrenci Adı", "Not", "Genel Değerlendirme", "Güçlü Yönler",
                "Geliştirilecek Yönler", "Tavsiyeler", "Dosya Adı"]
    df = df[[k for k in kolonlar if k in df.columns]]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Değerlendirmeler")
        ws = writer.sheets["Değerlendirmeler"]
        genis = {"Öğrenci Adı": 25, "Not": 8, "Genel Değerlendirme": 50,
                 "Güçlü Yönler": 40, "Geliştirilecek Yönler": 40, "Tavsiyeler": 40, "Dosya Adı": 30}
        for i, k in enumerate(df.columns, 1):
            ws.column_dimensions[chr(64 + i)].width = genis.get(k, 20)
    buf.seek(0)
    tarih = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(buf, as_attachment=True,
                     download_name=f"degerlendirme_{tarih}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/rapor", methods=["POST"])
def rapor():
    veri = request.get_json()
    sonuclar = veri.get("sonuclar", [])
    notlar = []
    for s in sonuclar:
        try:
            notlar.append(float(s.get("not", 0)))
        except (ValueError, TypeError):
            pass
    if not notlar:
        return jsonify({"hata": "Not verisi yok"}), 400

    n = len(notlar)
    siralama = sorted(zip([s.get("ogrenci", "?") for s in sonuclar], notlar), key=lambda x: -x[1])
    dagilim = {"0-49": 0, "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for nt in notlar:
        if nt < 50: dagilim["0-49"] += 1
        elif nt < 60: dagilim["50-59"] += 1
        elif nt < 70: dagilim["60-69"] += 1
        elif nt < 80: dagilim["70-79"] += 1
        elif nt < 90: dagilim["80-89"] += 1
        else: dagilim["90-100"] += 1

    return jsonify({
        "toplam_ogrenci": n,
        "ortalama": round(sum(notlar) / n, 1),
        "en_yuksek": max(notlar),
        "en_dusuk": min(notlar),
        "gecme_orani": round(sum(1 for nt in notlar if nt >= 50) / n * 100, 1),
        "dagilim": dagilim,
        "siralama": [{"ogrenci": a, "not": b} for a, b in siralama[:10]]
    })


# --- Tekli Analiz (PDF Yükle) ---

@app.route("/api/tekli-analiz", methods=["POST"])
def tekli_analiz():
    if "dosya" not in request.files:
        return jsonify({"hata": "PDF dosyası seçilmedi"}), 400

    dosya = request.files["dosya"]
    if not dosya.filename.lower().endswith(".pdf"):
        return jsonify({"hata": "Sadece PDF dosyası yüklenebilir"}), 400

    pdf_bytes = dosya.read()
    try:
        img_b64 = pdf_to_jpeg_b64(pdf_bytes)
        sonuc = degerlendirme_yap(img_b64)
        ogrenci = Path(dosya.filename).stem.replace("_", " ").title()

        return jsonify({
            "ogrenci": ogrenci,
            "dosya": dosya.filename,
            "not": sonuc["not"],
            "genel": sonuc["genel"],
            "guclu": sonuc["guclu"],
            "gelistir": sonuc["gelistir"],
            "tavsiye": sonuc["tavsiye"],
            "gorsel": img_b64,         # Frontend'de <img> olarak gösterilir
            "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "token": sonuc["token"]
        })
    except Exception as e:
        print(f"[HATA] tekli-analiz {dosya.filename}: {e}")
        return jsonify({"hata": str(e)}), 500


# --- İtiraz ---

@app.route("/api/itiraz", methods=["POST"])
def itiraz():
    ogrenci = request.form.get("ogrenci", "").strip()
    orijinal_not = request.form.get("orijinal_not", "").strip()
    itiraz_nedeni = request.form.get("itiraz_nedeni", "").strip()

    if not ogrenci or not itiraz_nedeni:
        return jsonify({"hata": "Öğrenci adı ve itiraz gerekçesi zorunlu"}), 400
    if "dosya" not in request.files:
        return jsonify({"hata": "Çizim PDF'i seçilmedi"}), 400

    dosya = request.files["dosya"]
    pdf_bytes = dosya.read()

    try:
        img_b64 = pdf_to_jpeg_b64(pdf_bytes)
        itiraz_tam = f"Orijinal Not: {orijinal_not}\nİtiraz Gerekçesi: {itiraz_nedeni}"
        sonuc = degerlendirme_yap(img_b64, itiraz_metni=itiraz_tam)

        kayit = {
            "tarih": datetime.now().isoformat(),
            "ogrenci": ogrenci,
            "pdf_adi": dosya.filename,
            "orijinal_not": orijinal_not,
            "itiraz_nedeni": itiraz_nedeni,
            "yeni_not": sonuc["not"],
            "itiraz_karari": sonuc["itiraz_karari"] or "—",
            "karar_gerekce": sonuc["karar_gerekce"] or "",
            "ham_cevap": sonuc["ham_cevap"]
        }
        itiraz_kaydet(kayit)

        return jsonify({
            **kayit,
            "guclu": sonuc["guclu"],
            "gelistir": sonuc["gelistir"],
            "tavsiye": sonuc["tavsiye"],
            "gorsel": img_b64,
            "tarih_goster": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "token": sonuc["token"]
        })
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@app.route("/api/itirazlar-listesi", methods=["GET"])
def itirazlar_listesi():
    jsonl_yolu = ITIRAZ_KLASOR / "itirazlar.jsonl"
    if not jsonl_yolu.exists():
        return jsonify({"itirazlar": [], "toplam": 0})
    kayitlar = []
    with open(jsonl_yolu, encoding="utf-8") as f:
        for satir in f:
            try:
                k = json.loads(satir)
                kayitlar.append({
                    "tarih": k.get("tarih", "")[:10],
                    "ogrenci": k.get("ogrenci", ""),
                    "orijinal_not": k.get("orijinal_not", ""),
                    "yeni_not": k.get("yeni_not", ""),
                    "itiraz_karari": k.get("itiraz_karari", ""),
                    "itiraz_nedeni": k.get("itiraz_nedeni", "")[:80]
                })
            except Exception:
                pass
    return jsonify({"itirazlar": list(reversed(kayitlar)), "toplam": len(kayitlar)})


@app.route("/api/itiraz-excel-indir", methods=["GET"])
def itiraz_excel_indir():
    excel_yolu = ITIRAZ_KLASOR / "itirazlar.xlsx"
    if not excel_yolu.exists():
        return jsonify({"hata": "Henüz itiraz kaydı yok"}), 404
    return send_file(excel_yolu, as_attachment=True,
                     download_name="itirazlar.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- Sistem Bilgisi & Tanılama ---

@app.route("/api/sistem-bilgi", methods=["GET"])
def sistem_bilgi():
    """Sistem durumunu kontrol et — konsol paneli için."""
    import sys
    import platform

    # Poppler kontrolü
    if POPPLER_PATH:
        exe = Path(POPPLER_PATH) / "pdftoppm.exe"
        if not exe.exists():
            exe = Path(POPPLER_PATH) / "pdftoppm"   # Linux/Mac
        poppler_ok = exe.exists()
        poppler_mesaj = str(POPPLER_PATH)
    else:
        pdftoppm = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
        poppler_ok = pdftoppm is not None
        poppler_mesaj = pdftoppm or "Bulunamadı — poppler kurulu değil veya PATH'de yok"

    # API key kontrolü
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_ok = api_key.startswith("sk-") and len(api_key) > 20
    api_mesaj = "Ayarlı (sk-...)" if api_ok else ("Boş veya .env yüklenmedi" if not api_key else "Geçersiz format (sk- ile başlamalı)")

    # Talimatlar
    tal_var = TALIMATLAR_YOLU.exists()
    tal_mesaj = str(TALIMATLAR_YOLU) + (" ✓" if tal_var else " — klasör bulunamadı")

    return jsonify({
        "python_surum": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "isletim_sistemi": platform.system() + " " + platform.release(),
        "model": MODEL_ID,
        "poppler_ok": poppler_ok,
        "poppler_mesaj": poppler_mesaj,
        "conda_prefix": os.environ.get("CONDA_PREFIX", "Yok — conda aktif değil"),
        "api_ok": api_ok,
        "api_mesaj": api_mesaj,
        "talimatlar_ok": tal_var,
        "talimatlar_mesaj": tal_mesaj,
        "itiraz_klasor": str(ITIRAZ_KLASOR.resolve()),
    })


@app.route("/api/poppler-test", methods=["POST"])
def poppler_test():
    """Küçük bir test PDF'i dönüştürerek poppler'ı doğrula."""
    # 1x1 piksel beyaz PDF (base64)
    MINIMAL_PDF_B64 = (
        "JVBERi0xLjEKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIg"
        "MCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBv"
        "YmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCAxIDFdID4+CmVuZG9i"
        "agp4cmVmCjAgNAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA2"
        "MiAwMDAwMCBuIAowMDAwMDAwMTE1IDAwMDAwIG4gCnRyYWlsZXIKPDwgL1NpemUgNCAvUm9vdCAxIDAg"
        "UiA+PgpzdGFydHhyZWYKMTkxCiUlRU9G"
    )
    try:
        pdf_bytes = base64.b64decode(MINIMAL_PDF_B64)
        img_b64 = pdf_to_jpeg_b64(pdf_bytes)
        return jsonify({"basarili": True, "mesaj": "Poppler çalışıyor ✓", "poppler_yolu": str(POPPLER_PATH)})
    except Exception as e:
        return jsonify({"basarili": False, "mesaj": str(e), "poppler_yolu": str(POPPLER_PATH)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("=" * 50)
    print("AutoCAD Değerlendirme Uygulaması")
    print(f"Model: {MODEL_ID}")
    print(f"Tarayıcıda aç: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=port)
