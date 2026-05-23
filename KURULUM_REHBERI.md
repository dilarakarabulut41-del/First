# AutoCAD Değerlendirme Sistemi — Windows 10 Kurulum Rehberi

---

## ADIM 1 — Anaconda Kur (tek seferlik, ~10 dk)

**1.** Tarayıcıda şu adrese git:
> https://www.anaconda.com/download

**2.** **"Download"** butonuna tıkla → büyük bir `.exe` dosyası indirilir (~1 GB)

**3.** İndirilen dosyaya çift tıkla. Kurulum ekranlarında:
- **"Just Me"** seç
- **"Add Anaconda3 to PATH"** kutucuğunu ✅ **işaretle** ← ÇOK ÖNEMLİ
- **"Install"** bas, bitene kadar bekle

**4.** Kurulum bitince bilgisayarı **yeniden başlat**

**5.** Başlat menüsünde **"Anaconda Prompt"** yaz ve aç. Şunu yaz:
```
conda --version
```
`conda 24.x.x` gibi bir çıktı görüyorsan ✅ kurulum tamam

---

## ADIM 2 — Git Kur (tek seferlik, ~5 dk)

**1.** Şu adrese git:
> https://git-scm.com/download/win

**2.** İndir → çift tıkla → hep **"Next"** de → **"Install"** bas

---

## ADIM 3 — Projeyi İndir (tek seferlik)

**Anaconda Prompt** aç. Şu komutları sırayla yaz, her birinden sonra Enter:

```
cd Desktop
git clone https://github.com/dilarakarabulut41-del/First.git
cd First
git checkout claude/finetune-autocad-llm-6UZtM
```

Masaüstünde **First** klasörü oluştu ✅

---

## ADIM 4 — Ortamı Kur (tek seferlik, ~10-15 dk)

**First** klasörünün içinde `setup_ortam.bat` dosyasını gör.
Üzerine **çift tıkla** → siyah ekran açılır, bekle.

Ekranda **"KURULUM TAMAMLANDI"** yazınca bitti ✅

---

## ADIM 5 — .env Dosyasını Doldur (tek seferlik)

**First** klasöründe `.env` dosyasını **Notepad** ile aç.
*(Dosyayı göremiyorsan: Dosya Gezgini → Görünüm → "Gizli öğeler" kutusunu işaretle)*

Şu iki satırı doldur:

```
OPENAI_API_KEY=sk-...OpenAI_API_anahtarın...
DRIVE_DATA_PATH=C:\Users\KULLANICI_ADIN\Desktop\autocad_drive
```

**OpenAI API anahtarı nereden alınır?**
- https://platform.openai.com adresine git
- Sağ üstten hesabına gir
- Sol menüden **"API Keys"** tıkla
- **"Create new secret key"** bas → çıkan anahtarı kopyala

---

## ADIM 6 — Uygulamayı Çalıştır

**First** klasöründe `baslat_webapp.bat` dosyasına **çift tıkla**.

Siyah ekranda şunu görünce hazır:
```
* Running on http://localhost:5000
```
Tarayıcı otomatik açılır. Açılmazsa kendin git: **http://localhost:5000**

Kapatmak için: siyah ekranda **Ctrl + C**

---

## Günlük Kullanım (Kısa Özet)

| Ne yapacaksın | Nasıl |
|---|---|
| İlk kurulum | `setup_ortam.bat` çift tıkla (sadece 1 kez) |
| Her gün açmak | `baslat_webapp.bat` çift tıkla |
| Kapatmak | Siyah ekranda Ctrl+C |

---

## Sık Karşılaşılan Sorunlar

**❌ "conda tanınmıyor" hatası**
→ Anaconda kurulumunda "Add to PATH" kutusunu işaretlemedin.
→ Anaconda'yı kaldır, tekrar kur, bu sefer işaretle.

**❌ "Port 5000 kullanımda" hatası**
→ `.env` dosyasına şu satırı ekle: `PORT=5001`
→ Tarayıcıda http://localhost:5001 kullan.

**❌ "PDF okunamıyor" hatası**
→ `setup_ortam.bat`'ı tekrar çalıştır (poppler yeniden kurulur).

**❌ "API key geçersiz" hatası**
→ `.env` dosyasındaki `OPENAI_API_KEY` satırını kontrol et.
→ platform.openai.com'da hesabında bakiye olduğundan emin ol.
