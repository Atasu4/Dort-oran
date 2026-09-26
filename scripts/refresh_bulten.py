import json
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://arsiv.mackolik.com/AjaxHandlers/ProgramDataHandler.ashx?type=6&sortValue=DATE&day=-1&sort=-1&sortDir=-1&groupId=-1&np=0&sport=1"


def odd(value):
    if value is None or value == "" or value in ("0,00", "0.00"):
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if parsed <= 1.01 or parsed >= 80:
        return None
    return round(parsed, 2)


def day_key(value):
    day, month, year = str(value).split(".")
    return year + month + day


def main():
    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://arsiv.mackolik.com/Genis-Iddaa-Programi",
        },
    )
    raw = urllib.request.urlopen(request, timeout=40).read().decode("utf-8", "replace")
    text = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', raw).replace("'", '"')
    data = json.loads(text)
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    today = now.strftime("%d.%m.%Y")
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    matches = []
    for day in data["m"]:
        for row in day["m"]:
            date = str(row[7])
            time = str(row[6])
            if date == today:
                pass
            elif date == tomorrow and time <= "11:59":
                pass
            else:
                continue
            o1, ox, o2 = odd(row[16]), odd(row[17]), odd(row[18])
            if o1 is None or ox is None or o2 is None:
                continue
            matches.append(
                {
                    "id": int(row[0]),
                    "home": str(row[1]).strip(),
                    "away": str(row[3]).strip(),
                    "time": time,
                    "date": date,
                    "league": str(row[26] or ""),
                    "o1": o1,
                    "ox": ox,
                    "o2": o2,
                    "alt": odd(row[22]),
                    "ust": odd(row[23]),
                }
            )
    matches.sort(key=lambda match: (day_key(match["date"]), match["time"], match["home"]))
    out = {
        "updated": now.isoformat(timespec="minutes"),
        "matches": matches,
    }
    path = Path(__file__).resolve().parents[1] / "bulten.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(matches)} mac -> {path}")


if __name__ == "__main__":
    main()
