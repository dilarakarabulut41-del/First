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


def pdf_to_jpeg_b64(pdf_bytes: bytes) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_yolu = tmp.name
        sayfalar = convert_from_path(tmp_yolu, dpi=150, first_page=1, last_page=1)
        os.unlink(tmp_yolu)
        if not sayfalar:
            return None
        img = sayfalar[0]
        img.thumbnail((1024, 1024), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"PDF dönüştürme hatası: {e}")
        return None


def pdf_path_to_b64(pdf_yolu: Path) -> str | None:
    if not pdf_yolu.exists():
        return None
    return pdf_to_jpeg_b64(pdf_yolu.read_bytes())


def notu_cikart(metin: str) -> str:
    for pattern in [r"YENI_NOT:\s*(\d+)", r"NOT:\s*(\d+)"]:
        m = re.search(pattern, metin)
        if m:
            return m.group(1)
    return "—"


def bolum_cikart(metin: str, bolum: str) -> str:
    m = re.search(rf"{bolum}:\s*(.+?)(?=\n[A-Z_]+:|$)", metin, re.DOTALL)
    return m.group(1).strip() if m else ""


def degerlendirme_yap(img_b64: str, itiraz_metni: str | None = None) -> dict:
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
        max_tokens=900, temperature=0.2
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
    jsonl_yolu = ITIRAZ_KLASOR / "itirazlar.jsonl"
    with open(jsonl_yolu, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    excel_yolu = ITIRAZ_KLASOR / "itirazlar.xlsx"
    yeni_satir = {
        "Tarih": kayit["tarih"], "Öğrenci": kayit["ogrenci"], "Dosya": kayit["pdf_adi"],
        "Orijinal Not": kayit["orijinal_not"], "Yeni Not": kayit["yeni_not"],
        "İtiraz Kararı": kayit["itiraz_karari"], "İtiraz Gerekçesi": kayit["itiraz_nedeni"],
        "Karar Gerekçesi": kayit["karar_gerekce"], "Tam Değerlendirme": kayit["ham_cevap"]
    }
    df = pd.concat([pd.read_excel(excel_yolu), pd.DataFrame([yeni_satir])], ignore_index=True) \
        if excel_yolu.exists() else pd.DataFrame([yeni_satir])
    df.to_excel(excel_yolu, index=False)


@app.route("/")
def anasayfa():
    return render_template("index.html")


@app.route("/api/klasor-tara", methods=["POST"])
def klasor_tara():
    veri = request.get_json()
    klasor = Path(veri.get("yol", "").strip())
    if not klasor.exists():
        return jsonify({"hata": f"Klasör bulunamadı: {klasor}"}), 400
    pdfler = sorted(klasor.glob("**/*.pdf"))
    return jsonify({"dosyalar": [{"isim": p.name, "yol": str(p), "boyut_kb": round(p.stat().st_size/1024, 1)} for p in pdfler], "toplam": len(pdfler)})


@app.route("/api/analiz-et", methods=["POST"])
def analiz_et():
    pdf_yolu = Path(request.get_json().get("yol", "").strip())
    if not pdf_yolu.exists():
        return jsonify({"hata": f"Dosya bulunamadı"}), 400
    try:
        img_b64 = pdf_path_to_b64(pdf_yolu)
        if not img_b64:
            return jsonify({"hata": "PDF görüntüye çevrilemedi"}), 500
        s = degerlendirme_yap(img_b64)
        return jsonify({"dosya": pdf_yolu.name, "ogrenci": pdf_yolu.stem.replace("_", " ").title(),
                        "not": s["not"], "degerlendirme": s["ham_cevap"], "token": s["token"]})
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@app.route("/api/excel-indir", methods=["POST"])
def excel_indir():
    sonuclar = request.get_json().get("sonuclar", [])
    if not sonuclar:
        return jsonify({"hata": "Sonuç yok"}), 400
    df = pd.DataFrame(sonuclar).rename(columns={"dosya": "Dosya Adı", "ogrenci": "Öğrenci Adı", "not": "Not", "degerlendirme": "Değerlendirme"})
    for k, b in [("Genel Değerlendirme", "GENEL_DEGERLENDIRME"), ("Öğrenci Adı", None)]:
        if b: df[k] = df["Değerlendirme"].apply(lambda x: bolum_cikart(str(x), b))
    df["Güçlü Yönler"] = df["Değerlendirme"].apply(lambda x: bolum_cikart(str(x), "GUCLU_YONLER"))
    df["Geliştirilecek Yönler"] = df["Değerlendirme"].apply(lambda x: bolum_cikart(str(x), "GELISTIRILECEK_YONLER"))
    df["Tavsiyeler"] = df["Değerlendirme"].apply(lambda x: bolum_cikart(str(x), "TAVSIYELER"))
    kolonlar = ["Öğrenci Adı", "Not", "Genel Değerlendirme", "Güçlü Yönler", "Geliştirilecek Yönler", "Tavsiyeler", "Dosya Adı"]
    df = df[[k for k in kolonlar if k in df.columns]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Değerlendirmeler")
        ws = w.sheets["Değerlendirmeler"]
        for i, k in enumerate(df.columns, 1):
            ws.column_dimensions[chr(64+i)].width = {"Not": 8, "Öğrenci Adı": 25}.get(k, 40)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"degerlendirme_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/rapor", methods=["POST"])
def rapor():
    sonuclar = request.get_json().get("sonuclar", [])
    notlar = [float(s["not"]) for s in sonuclar if str(s.get("not", "")).replace(".","").isdigit()]
    if not notlar: return jsonify({"hata": "Not verisi yok"}), 400
    n = len(notlar)
    siralama = sorted(zip([s.get("ogrenci", "?") for s in sonuclar], notlar), key=lambda x: -x[1])
    dagilim = {"0-49": 0, "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for nt in notlar:
        k = "0-49" if nt<50 else "50-59" if nt<60 else "60-69" if nt<70 else "70-79" if nt<80 else "80-89" if nt<90 else "90-100"
        dagilim[k] += 1
    return jsonify({"toplam_ogrenci": n, "ortalama": round(sum(notlar)/n, 1),
                    "en_yuksek": max(notlar), "en_dusuk": min(notlar),
                    "gecme_orani": round(sum(1 for nt in notlar if nt>=50)/n*100, 1),
                    "dagilim": dagilim, "siralama": [{"ogrenci": a, "not": b} for a, b in siralama[:10]]})


@app.route("/api/tekli-analiz", methods=["POST"])
def tekli_analiz():
    if "dosya" not in request.files or not request.files["dosya"].filename.lower().endswith(".pdf"):
        return jsonify({"hata": "PDF dosyası seçilmedi"}), 400
    dosya = request.files["dosya"]
    try:
        img_b64 = pdf_to_jpeg_b64(dosya.read())
        if not img_b64: return jsonify({"hata": "PDF görüntüye çevrilemedi"}), 500
        s = degerlendirme_yap(img_b64)
        return jsonify({"ogrenci": Path(dosya.filename).stem.replace("_", " ").title(),
                        "dosya": dosya.filename, "not": s["not"], "genel": s["genel"],
                        "guclu": s["guclu"], "gelistir": s["gelistir"], "tavsiye": s["tavsiye"],
                        "gorsel": img_b64, "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"), "token": s["token"]})
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


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
    try:
        img_b64 = pdf_to_jpeg_b64(dosya.read())
        if not img_b64: return jsonify({"hata": "PDF görüntüye çevrilemedi"}), 500
        s = degerlendirme_yap(img_b64, itiraz_metni=f"Orijinal Not: {orijinal_not}\nİtiraz Gerekçesi: {itiraz_nedeni}")
        kayit = {"tarih": datetime.now().isoformat(), "ogrenci": ogrenci, "pdf_adi": dosya.filename,
                 "orijinal_not": orijinal_not, "itiraz_nedeni": itiraz_nedeni, "yeni_not": s["not"],
                 "itiraz_karari": s["itiraz_karari"] or "—", "karar_gerekce": s["karar_gerekce"] or "",
                 "ham_cevap": s["ham_cevap"]}
        itiraz_kaydet(kayit)
        return jsonify({**kayit, "guclu": s["guclu"], "gelistir": s["gelistir"], "tavsiye": s["tavsiye"],
                        "gorsel": img_b64, "tarih_goster": datetime.now().strftime("%d.%m.%Y %H:%M"), "token": s["token"]})
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@app.route("/api/itirazlar-listesi")
def itirazlar_listesi():
    jsonl = ITIRAZ_KLASOR / "itirazlar.jsonl"
    if not jsonl.exists(): return jsonify({"itirazlar": [], "toplam": 0})
    kayitlar = []
    for satir in open(jsonl, encoding="utf-8"):
        try:
            k = json.loads(satir)
            kayitlar.append({"tarih": k.get("tarih", "")[:10], "ogrenci": k.get("ogrenci", ""),
                             "orijinal_not": k.get("orijinal_not", ""), "yeni_not": k.get("yeni_not", ""),
                             "itiraz_karari": k.get("itiraz_karari", ""), "itiraz_nedeni": k.get("itiraz_nedeni", "")[:80]})
        except: pass
    return jsonify({"itirazlar": list(reversed(kayitlar)), "toplam": len(kayitlar)})


@app.route("/api/itiraz-excel-indir")
def itiraz_excel_indir():
    excel = ITIRAZ_KLASOR / "itirazlar.xlsx"
    if not excel.exists(): return jsonify({"hata": "Henüz itiraz kaydı yok"}), 404
    return send_file(excel, as_attachment=True, download_name="itirazlar.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    print(f"Model: {MODEL_ID}\nTarayıcıda aç: http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
