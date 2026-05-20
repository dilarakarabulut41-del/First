"""
ADIM 3b: Eğitim Durumu Kontrol
Çalıştır: python model_egitimi/adim3b_durum_kontrol.py [job_id]
"""
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def main():
    if len(sys.argv) > 1:
        job_id = sys.argv[1]
    else:
        isler = client.fine_tuning.jobs.list(limit=5)
        if not isler.data:
            print("Aktif iş bulunamadı."); return
        for i, is_ in enumerate(isler.data):
            print(f"  {i+1}. {is_.id} | {is_.status} | {is_.fine_tuned_model or 'devam ediyor'}")
        try:
            job_id = isler.data[int(input("\nHangi iş? (1-5): ").strip()) - 1].id
        except:
            job_id = isler.data[0].id
    is_ = client.fine_tuning.jobs.retrieve(job_id)
    print(f"\nJob: {is_.id}\nDurum: {is_.status}")
    if is_.fine_tuned_model:
        print(f"\n✅ Model: {is_.fine_tuned_model}")
        print(f"  → .env dosyasına ekle: FINETUNED_MODEL_ID={is_.fine_tuned_model}")

if __name__ == "__main__":
    main()
