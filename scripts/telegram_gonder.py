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
    satirlar = [
        "🎯 *GÖKÇEN ANALİZ - Günlük*",
        f"📅 *Tarih:* {tarih}",
        "─────────────────────────────",
    ]
    if not maclar:
        satirlar.append("Liste boş. gunluk.json ekle.")
    for mac in maclar:
        satirlar.append(f"⚽ *Maç:* {mac.get('mac', '')}")
        satirlar.append(f"📊 *Tahmin:* {mac.get('tahmin', '')}")
        if mac.get("not"):
            satirlar.append(f"💡 {mac['not']}")
        satirlar.append("")
    return "\n".join(satirlar)


def main():
    status, response = gonder(metin())
    if status == 200:
        print("İletim başarılı")
    else:
        print(f"İletim başarısız: {status} {response}")


if __name__ == "__main__":
    main()
