"""
ADIM 4: Modeli Test Et
Çalıştır: python model_egitimi/adim4_test_et.py
Amaç: Modelin hiç görmediği %10 test verisiyle kaliteyi ölç.
"""
import os
import json
import re
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_ID = os.getenv("FINETUNED_MODEL_ID")
EGITIM_KLASOR = Path("./egitim_verisi")

def notu_cikart(metin):
    m = re.search(r"NOT:\s*(\d+(?:\.\d+)?)", metin)
    return float(m.group(1)) if m else None

def main():
    if not MODEL_ID:
        print("❌ FINETUNED_MODEL_ID tanımlı değil"); return
    test = EGITIM_KLASOR / "test.jsonl"
    if not test.exists():
        print("❌ test.jsonl bulunamadı"); return
    ornekler = [json.loads(l) for l in open(test, encoding="utf-8")]
    print(f"Test: {len(ornekler)} örnek | Model: {MODEL_ID}\n")
    sonuclar = []
    for i, o in enumerate(ornekler):
        print(f"[{i+1}/{len(ornekler)}]", end=" ", flush=True)
        gercek = notu_cikart(o["messages"][-1]["content"])
        try:
            r = client.chat.completions.create(
                model=MODEL_ID, messages=o["messages"][:-1], max_tokens=500, temperature=0.1)
            model_c = r.choices[0].message.content
            model_n = notu_cikart(model_c)
            hata = abs(gercek - model_n) if gercek and model_n else None
            print(f"Gerçek:{gercek} Model:{model_n} Fark:{hata:.1f}" if hata else "not çıkarılamadı")
            sonuclar.append({"gercek": gercek, "model": model_n, "hata": hata, "cevap": model_c[:150]})
        except Exception as e:
            print(f"HATA: {e}")
            sonuclar.append({"hata_mesaj": str(e)})
    df = pd.DataFrame(sonuclar)
    hatalar = df["hata"].dropna()
    print(f"\n{'='*50}\nMAE: {hatalar.mean():.2f} | Max: {hatalar.max():.2f}")
    print("✅ Başarılı!" if hatalar.mean() < 8 else "⚠️ Düşük başarı, daha fazla veri ekle")
    df.to_excel(EGITIM_KLASOR / "test_sonuclari.xlsx", index=False)
    print("Sonuçlar: egitim_verisi/test_sonuclari.xlsx")

if __name__ == "__main__":
    main()
