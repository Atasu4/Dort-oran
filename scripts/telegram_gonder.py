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
        response = requests.post(url, json=payload, timeout=15)
        return response.status_code, response.json()
    except Exception as exc:
        return None, str(exc)


def edge_metin():
    root = Path(__file__).resolve().parent.parent
    bulten_path = root / "bulten.json"
    if not bulten_path.exists():
        return "Bülten bulunamadı."
    data = json.loads(bulten_path.read_text(encoding="utf-8"))
    edge = data.get("edgeHigh", [])[:12]
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = [
        "🎯 *ATASU / Dört Oran - Edge Analizi*",
        f"📅 *{now}*",
        "Power De-vig + Monte Carlo",
        "─────────────────────────────",
    ]
    if not edge:
        lines.append("Şu an yüksek edge (≥%4) yok.")
    else:
        for i, m in enumerate(edge, 1):
            lines.append(
                f"{i}. *{m.get('home','')} - {m.get('away','')}*\n"
                f"   Lig: {m.get('league','')} | Saat: {m.get('time','')}\n"
                f"   Edge: *%{m.get('max_edge','')}* | Model Fav: {m.get('opta_fav','')}"
            )
    lines.append("\n⚠️ Model edge ≥%4, power de-vig ile karşılaştırıldı.")
    return "\n".join(lines)


def main():
    status, response = gonder(edge_metin())
    print("İletim başarılı" if status == 200 else f"İletim başarısız: {status} {response}")


if __name__ == "__main__":
    main()
