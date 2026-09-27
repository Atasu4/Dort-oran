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


def team_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def side_line(row, played, win, draw, loss, goals_for, goals_against, points):
    return {
        "played": row[played],
        "w": row[win],
        "d": row[draw],
        "l": row[loss],
        "gf": row[goals_for],
        "ga": row[goals_against],
        "pts": row[points],
    }


def load_table(standing_id, cache):
    if standing_id in cache:
        return cache[standing_id]
    table = {}
    url = f"https://arsiv.mackolik.com/AjaxHandlers/StandingHandler.ashx?op=standing&id={standing_id}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://arsiv.mackolik.com/Standings/Default.aspx",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        home_goals = home_games = away_goals = away_games = 0
        for rank, row in enumerate(payload.get("s") or [], start=1):
            if not isinstance(row, list) or len(row) < 16:
                continue
            home = side_line(row, 2, 4, 6, 8, 10, 12, 14)
            away = side_line(row, 3, 5, 7, 9, 11, 13, 15)
            home_goals += home["gf"]
            home_games += home["played"]
            away_goals += away["gf"]
            away_games += away["played"]
            table[int(row[0])] = {
                "rank": rank,
                "pts": home["pts"] + away["pts"],
                "played": home["played"] + away["played"],
                "home": home,
                "away": away,
            }
        table["_lgH"] = round(home_goals / home_games, 3) if home_games else None
        table["_lgA"] = round(away_goals / away_games, 3) if away_games else None
    except Exception as error:
        print(f"puan {standing_id} alinmadi: {error}")
    cache[standing_id] = table
    return table


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
                    "homeId": team_id(row[2]),
                    "awayId": team_id(row[4]),
                    "standingId": team_id(row[49]) if len(row) > 49 else 0,
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
    cache = {}
    for match in matches:
        standing_id = match.pop("standingId", 0)
        table = load_table(standing_id, cache) if standing_id else {}
        match["lgH"] = table.get("_lgH")
        match["lgA"] = table.get("_lgA")
        match["homeTable"] = table.get(match.pop("homeId", 0))
        match["awayTable"] = table.get(match.pop("awayId", 0))
    filled = sum(1 for match in matches if match["homeTable"] or match["awayTable"])
    matches.sort(key=lambda match: (day_key(match["date"]), match["time"], match["home"]))
    out = {
        "updated": now.isoformat(timespec="minutes"),
        "matches": matches,
    }
    path = Path(__file__).resolve().parents[1] / "bulten.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(matches)} mac, {filled} puanli, {len(cache)} lig -> {path}")


if __name__ == "__main__":
    main()
