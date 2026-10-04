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
    if parsed < 1.00 or parsed >= 80:
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
tables = {}
try:
    bulletin = json.loads(Path("bulten.json").read_text(encoding="utf-8"))
    for match in bulletin.get("matches") or []:
        ht, at = match.get("homeTable") or {}, match.get("awayTable") or {}
        tables[(match.get("date"), match.get("home"), match.get("away"))] = {"hr": ht.get("rank") or 0, "ar": at.get("rank") or 0, "aw": (at.get("away") or {}).get("w") or 0, "al": (at.get("away") or {}).get("l") or 0}
except Exception:
    tables = {}
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
        if markets["kg"] == 1.52: tags.append("ters kg")
        if hit(markets["15ust"], 1.25, 1.29): tags.append("1.5 üst")
        if markets["25alt"] == 1.48: tags.append("2.5 alt")
        if hit(markets["25ust"], 1.16, 1.17): tags.append("2.5 üst")
        if hit(markets["iy15"], 1.55, 1.57): tags.append("İY 1.5")
        markets["ms1"] = odd(row[16]) if len(row) > 16 else None
        blue = []
        if hit(markets["kgyok"], 2.10, 2.19) and hit(markets["iy15alt"], 1.40, 1.49):
            blue.append("KG var")
        if hit(markets["kgyok"], 1.80, 1.89) and hit(markets["iy15alt"], 1.20, 1.29):
            blue.append("2.5 alt")
        if hit(markets["kgyok"], 1.50, 1.59) and hit(markets["25alt"], 1.30, 1.39):
            blue.append("ters alt")
        if hit(markets["kgyok"], 1.50, 1.59) and hit(markets["25alt"], 1.40, 1.49):
            blue.append("İY 1.5 alt")
        if hit(markets["ms1"], 1.20, 1.29) and hit(markets["kg"], 1.40, 1.49):
            blue.append("MS 1")
        if hit(markets["ms1"], 1.20, 1.29) and hit(markets["iy15alt"], 1.40, 1.49):
            blue.append("MS 1")
        orange = hit(markets["ms1"], 1.00, 1.09) and hit(markets["25ust"], 1.10, 1.19)
        home, away = str(row[1]).strip(), str(row[3]).strip()
        table = tables.get((date, home, away))
        gap = None
        if table and table["hr"] and table["ar"]:
            gap = table["ar"] - table["hr"]
            away_bad = table["aw"] <= table["al"]
            if "MS 1" in blue and not (gap >= 4 and away_bad):
                blue = [x for x in blue if x != "MS 1"]
            if orange and not (gap >= 4 and away_bad):
                orange = False
            if any(x == "2.5 alt" for x in tags + blue) and gap < 5:
                tags = [x for x in tags if x != "2.5 alt"]
                blue = [x for x in blue if x != "2.5 alt"]
        if not tags and not blue and not orange:
            continue
        rows.append({"date": date, "time": time, "home": home, "away": away, "league": str(row[26] or ""), "tags": tags, "blue": blue, "orange": orange, "gap": gap, **markets})
out = {"updated": now.strftime("%Y-%m-%dT%H:%M+03:00"), "count": len(rows), "matches": rows}
Path("oran_sayfa.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(rows))


def goals(value):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None

scored = []
for day in data["m"]:
    for row in day["m"]:
        fh, fa = goals(row[8]), goals(row[9])
        if fh is None or fa is None:
            continue
        markets = {
            "35alt": odd(row[46]) if len(row) > 46 else None,
            "kg": odd(row[39]) if len(row) > 39 else None,
            "15ust": odd(row[45]) if len(row) > 45 else None,
            "25alt": odd(row[22]) if len(row) > 22 else None,
            "25ust": odd(row[23]) if len(row) > 23 else None,
            "iy15": odd(row[43]) if len(row) > 43 else None,
            "kgyok": odd(row[40]) if len(row) > 40 else None,
            "iy15alt": odd(row[42]) if len(row) > 42 else None,
            "ms1": odd(row[16]) if len(row) > 16 else None,
        }
        calls = []
        if hit(markets["35alt"], 1.05, 1.07): calls.append(("3.5 alt", fh+fa < 4))
        if markets["kg"] == 1.52: calls.append(("ters kg", not (fh>0 and fa>0)))
        if hit(markets["15ust"], 1.25, 1.29): calls.append(("1.5 üst", fh+fa >= 2))
        if markets["25alt"] == 1.48: calls.append(("2.5 alt", fh+fa < 3))
        if hit(markets["25ust"], 1.16, 1.17): calls.append(("2.5 üst", fh+fa >= 3))
        if hit(markets["kgyok"], 1.80, 1.89) and hit(markets["iy15alt"], 1.20, 1.29): calls.append(("2.5 alt", fh+fa < 3))
        if hit(markets["kgyok"], 1.50, 1.59) and hit(markets["25alt"], 1.30, 1.39): calls.append(("ters alt", fh+fa < 3))
        if hit(markets["ms1"], 1.20, 1.29) and hit(markets["kg"], 1.40, 1.49): calls.append(("MS 1", fh>fa))
        if hit(markets["ms1"], 1.00, 1.09) and hit(markets["25ust"], 1.10, 1.19): calls.append(("MS 1", fh>fa))
        day, month, year = str(row[7]).split(".")
        if (year, month, day) < ("2026", "10", "04"):
            continue
        if not calls:
            continue
        ok = all(flag for _, flag in calls)
        scored.append({"date": str(row[7]), "time": str(row[6]), "home": str(row[1]).strip(), "away": str(row[3]).strip(), "skor": f"{fh}-{fa}", "calls": [name for name,_ in calls], "ok": ok})
Path("analiz_sonuc.json").write_text(json.dumps({"updated": now.strftime("%Y-%m-%dT%H:%M+03:00"), "count": len(scored), "hit": sum(1 for x in scored if x["ok"]), "matches": scored}, ensure_ascii=False, indent=2), encoding="utf-8")
print("analiz", len(scored))
