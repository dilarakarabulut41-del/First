# AutoCAD Çizim Değerlendirme Sistemi — Başlangıç Rehberi

## Gereksinimler
- Python 3.10+ (python.org)
- OpenAI hesabı (platform.openai.com)
- Google Drive verileri bilgisayara indirilmiş olmalı

---

## ADIM 0: Kurulum (Tek seferlik)

```bash
pip install -r requirements.txt
```

**Poppler kur (PDF→görsel için zorunlu):**
- Windows: https://github.com/oschwartz10612/poppler-windows/releases → indir, PATH'e ekle
- Mac: `brew install poppler`
- Linux: `sudo apt install poppler-utils`

**Ortam dosyası:**
```bash
cp .env.example .env
# .env dosyasını aç, OPENAI_API_KEY ve DRIVE_DATA_PATH alanlarını doldur
```

---

## ADIM 1: Veri Kontrolü

Drive klasör yapısı:
```
[Drive klasörü]/
├── cizimler/          ← öğrenci PDF'leri (ahmet_yilmaz.pdf)
├── notlar/            ← notlar.xlsx (kolonlar: ogrenci_adi | not | yorum | yil)
└── talimatlar/        ← puanlama.txt
```

```bash
python veri_hazirlama/adim1_veri_kontrol.py
```

---

## ADIM 2: Eğitim Verisi Oluştur (%70/%20/%10)

```bash
python veri_hazirlama/adim2_egitim_verisi_olustur.py
```

---

## ADIM 3: Modeli Eğit (2-4 saat, OpenAI sunucularında)

```bash
python model_egitimi/adim3_modeli_egit.py
# Bilgisayarı kapatsanız da devam eder

# Durumu kontrol için:
python model_egitimi/adim3b_durum_kontrol.py
```

---

## ADIM 4: Test Et

```bash
python model_egitimi/adim4_test_et.py
# Ortalama hata < 8 puan ise ✅
```

---

## ADIM 5: Web Uygulaması

```bash
python webapp/app.py
# Tarayıcıda aç: http://localhost:5000
```

**3 Sekme:**
- **Toplu Analiz:** Klasör seç → Tümünü analiz et → Excel + Sınıf Raporu
- **Tekli Analiz:** Tek PDF yükle → Çizimi gör + Bireysel Rapor → Yazdır
- **İtiraz:** Gerekçeli itiraz gönder → KABUL/KISMI_KABUL/RED kararı → İtirazlar saklanır (fine-tuning için)

---

## Tahmini Maliyetler

| İşlem | Maliyet |
|-------|----------|
| Fine-tuning 100 örnek | ~$3-5 |
| Fine-tuning 300 örnek | ~$10-15 |
| Tek değerlendirme | ~$0.01-0.03 |
| 50 öğrenci | ~$0.50-1.50 |

---

## Sık Sorulan Sorular

**"poppler not found" hatası:** Poppler kurulmamış (yukarıya bak)

**PDF eşleşmiyor:** Dosya adı ile Excel'deki isim benzer olmalı
(`ahmet_yilmaz.pdf` ↔ `Ahmet Yılmaz`)

**İtirazlar nerede saklanıyor?** `itirazlar/itirazlar.jsonl` ve `itirazlar/itirazlar.xlsx`
