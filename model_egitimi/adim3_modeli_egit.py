"""
ADIM 3: Modeli Eğit (Fine-Tuning)
Çalıştır: python model_egitimi/adim3_modeli_egit.py
Amaç: JSONL dosyalarını OpenAI'ye yükler, eğitimi başlatır.
Not: Eğitim OpenAI sunucularında olur — bilgisayarın kapalı olsa da devam eder.
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EGITIM_KLASOR = Path("./egitim_verisi")


def dosya_yukle(yol: Path) -> str:
    print(f"Yükleniyor: {yol.name}...", end=" ", flush=True)
    with open(yol, "rb") as f:
        yanit = client.files.create(file=f, purpose="fine-tune")
    print(f"✓ {yanit.id}")
    return yanit.id


def durumu_takip_et(job_id: str):
    print(f"\nTakip ediliyor (Ctrl+C ile çıkabilirsin)...\n")
    while True:
        try:
            is_ = client.fine_tuning.jobs.retrieve(job_id)
            print(f"[{time.strftime('%H:%M:%S')}] {is_.status}", end="")
            if is_.status == "succeeded":
                mid = is_.fine_tuned_model
                print(f"\n\n✅ TAMAMLANDI! Model: {mid}")
                env = Path(".env")
                if env.exists():
                    lines = [f"FINETUNED_MODEL_ID={mid}" if l.startswith("FINETUNED_MODEL_ID=") else l
                             for l in env.read_text().splitlines()]
                    env.write_text("\n".join(lines))
                    print(".env otomatik güncellendi ✓")
                return mid
            elif is_.status in ("failed", "cancelled"):
                print(f"\n❌ BAŞARISIZ: {getattr(is_, 'error', '?')}")
                return None
            print(" (bekleniyor...)")
            time.sleep(60)
        except KeyboardInterrupt:
            print(f"\nDurduruldu. Job ID: {job_id}")
            return None


def main():
    print("=" * 60)
    print("AŞAMA 3: MODEL EĞİTİMİ")
    print("=" * 60)
    egitim = EGITIM_KLASOR / "egitim.jsonl"
    validasyon = EGITIM_KLASOR / "validasyon.jsonl"
    if not egitim.exists():
        print("❌ Önce adım 2'yi çalıştır.")
        return
    n = sum(1 for _ in open(egitim))
    print(f"\nEğitim örneği: {n}")
    print(f"Tahmini süre: {n*2//60+30}-{n*4//60+60} dakika")
    print(f"Tahmini maliyet: $2-8\n")
    if input("Devam? (evet/hayır): ").strip().lower() not in ("evet", "e", "y", "yes"):
        return
    eid = dosya_yukle(egitim)
    vid = dosya_yukle(validasyon)
    is_ = client.fine_tuning.jobs.create(
        training_file=eid, validation_file=vid,
        model="gpt-4o-mini-2024-07-18",
        hyperparameters={"n_epochs": "auto", "batch_size": "auto", "learning_rate_multiplier": "auto"},
        suffix="autocad-degerlendirme"
    )
    print(f"✓ Eğitim başladı! Job: {is_.id}")
    durumu_takip_et(is_.id)


if __name__ == "__main__":
    main()
