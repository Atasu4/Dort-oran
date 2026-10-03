#!/usr/bin/env python3
import json, re, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://arsiv.mackolik.com/AjaxHandlers/ProgramDataHandler.ashx?type=6&sortValue=DATE&day=-1&sort=-1&sortDir=-1&groupId=-1&np=0&sport=1"

def odd(value):
    if value in (None, "", "0,00", "0.00"):
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if parsed <= 1.01 or parsed >= 80:
        return None
    return round(parsed, 2)

def hit(value, low, high):
    return value is not None and low - 1e-9 <= value <= high + 1e-9

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://arsiv.mackolik.com/Genis-Iddaa-Programi"})
raw = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
text = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', raw).replace("'", '"')
data = json.loads(text)
now = datetime.now(ZoneInfo("Europe/Istanbul"))
today = now.strftime("%d.%m.%Y")
tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
rows = []
for day in data["m"]:
    for row in day["m"]:
        date, time = str(row[7]), str(row[6])
        if date != today and not (date == tomorrow and time <= "23:59"):
            continue
        markets = {
            "35alt": odd(row[46]) if len(row) > 46 else None,
            "kg": odd(row[39]) if len(row) > 39 else None,
            "15ust": odd(row[45]) if len(row) > 45 else None,
            "25alt": odd(row[22]) if len(row) > 22 else None,
            "25ust": odd(row[23]) if len(row) > 23 else None,
            "iy15": odd(row[43]) if len(row) > 43 else None,
        }
        markets["kgyok"] = odd(row[40]) if len(row) > 40 else None
        markets["iy15alt"] = odd(row[42]) if len(row) > 42 else None
        tags = []
        if hit(markets["35alt"], 1.05, 1.07): tags.append("3.5 alt")
        if markets["kg"] == 1.52: tags.append("KG")
        if hit(markets["15ust"], 1.25, 1.29): tags.append("1.5 üst")
        if markets["25alt"] == 1.48: tags.append("2.5 alt")
        if hit(markets["25ust"], 1.16, 1.17): tags.append("2.5 üst")
        if hit(markets["iy15"], 1.55, 1.57): tags.append("İY 1.5")
        blue = hit(markets["kgyok"], 2.10, 2.19) and hit(markets["iy15alt"], 1.40, 1.49)
        if not tags and not blue:
            continue
        rows.append({"date": date, "time": time, "home": str(row[1]).strip(), "away": str(row[3]).strip(), "league": str(row[26] or ""), "tags": tags, "blue": blue, **markets})
out = {"updated": now.strftime("%Y-%m-%dT%H:%M+03:00"), "count": len(rows), "matches": rows}
Path("oran_sayfa.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(rows))
