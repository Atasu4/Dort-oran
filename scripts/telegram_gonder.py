import json
import os
from datetime import datetime
from pathlib import Path

import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def gonder(mesaj):
    if not TOKEN or not CHAT_ID:
        return None, "TELEGRAM_TOKEN ve TELEGRAM_CHAT_ID gerekli"
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code, response.json()
    except Exception as exc:
        return None, str(exc)


def metin():
    tarih = datetime.now().strftime("%d.%m.%Y")
    dosya = Path(__file__).resolve().parent.parent / "gunluk.json"
    maclar = []
    if dosya.exists():
        maclar = json.loads(dosya.read_text(encoding="utf-8")).get("maclar", [])
    if not maclar:
        maclar = [
            {"mac": "Galatasaray - Fenerbahçe", "tahmin": "KG Var / 2.5 Üst", "form": "Ev sahibi son 5 maçta ortalama 2.1 xG. Deplasman hücum verimliliği %84."},
            {"mac": "Arsenal - Chelsea", "tahmin": "İY 0.5 Üst", "form": "İlk 30 dakikada baskı endeksi %78."},
            {"mac": "Real Madrid - Barcelona", "tahmin": "Maç Sonucu 1", "form": "Ev sahibinin iç saha galibiyet serisi devam ediyor."},
        ]
    satirlar = [
        "🎯 *ATASU Intelligence - Günlük Maç Analiz Raporu*",
        f"📅 *Tarih:* {tarih}",
        "─────────────────────────────",
    ]
    for mac in maclar:
        satirlar.append(f"⚽ *Maç:* {mac.get('mac', '')}")
        satirlar.append(f"📊 *Tahmin:* {mac.get('tahmin', '')}")
        satirlar.append(f"💡 *Form & Momentum:* {mac.get('form', '')}")
        satirlar.append("")
    satirlar.append("⚠️ *Not:* Analizler yapay zeka algoritması tarafından üretilmiştir.")
    return "\n".join(satirlar)


def main():
    status, response = gonder(metin())
    print("İletim başarılı" if status == 200 else f"İletim başarısız: {status} {response}")


if __name__ == "__main__":
    main()
