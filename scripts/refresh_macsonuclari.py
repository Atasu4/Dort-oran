#!/usr/bin/env python3
"""MacSonuclari düşen oran + seri taraması."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Europe/Istanbul")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://www.macsonuclari1.net/"}
DUSEN = "https://f20.macsonuclari1.net/degisen26.asp?sportId=78&turId=1&marketId=1&type=dusen&order=degisim&drop=0.05&limit=50"
SERIES = "https://f20.macsonuclari1.net/series26.asp?sportId=78&seri=5&o=1.2&sira=seri"


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode("utf-8", "replace"))


def clock(ts):
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc).astimezone(IST).strftime("%H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def side_of(moid):
    return {2: "1", 1: "X", 3: "2"}.get(moid, "")


def drops(payload):
    out = []
    for item in payload.get("m") or []:
        match = item.get("m") or {}
        if match.get("p") != 78:
            continue
        home, away = match.get("h") or "", match.get("a") or ""
        when = clock(match.get("t"))
        for row in item.get("oranlar") or []:
            if row.get("type") != "fall":
                continue
            first, now = float(row.get("io") or 0), float(row.get("o") or 0)
            if first <= 1.01 or now <= 1.01:
                continue
            pct = round((first - now) / first * 100, 1)
            if pct < 5:
                continue
            out.append({
                "home": home,
                "away": away,
                "time": when,
                "side": side_of(row.get("moId")),
                "first": round(first, 2),
                "now": round(now, 2),
                "pct": pct,
            })
    out.sort(key=lambda r: (-r["pct"], r["time"], r["home"]))
    seen = set()
    uniq = []
    for row in out:
        key = (row["home"], row["away"], row["side"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
        if len(uniq) == 20:
            break
    return uniq


def series(payload):
    out = []
    for row in payload.get("data") or []:
        if int(row.get("seri") or 0) < 5:
            continue
        odd = float(row.get("o") or 0)
        if odd < 1.2:
            continue
        market = str(row.get("mrkt") or "").replace("<b>", "").replace("</b>", "")
        pick = str(row.get("oc") or "")
        out.append({
            "home": row.get("h") or "",
            "away": row.get("a") or "",
            "time": clock(row.get("t")),
            "who": row.get("rt") or "",
            "market": market,
            "pick": pick,
            "seri": int(row.get("seri") or 0),
            "odd": round(odd, 2),
        })
    out.sort(key=lambda r: (-r["seri"], r["odd"], r["home"]))
    return out[:20]


def main():
    now = datetime.now(IST)
    drop_rows = drops(get(DUSEN))
    seri_rows = series(get(SERIES))
    payload = {
        "updated": now.strftime("%Y-%m-%dT%H:%M%z"),
        "drops": drop_rows,
        "series": seri_rows,
    }
    root = Path(__file__).resolve().parent
    path = (root.parent if root.name == "scripts" else Path("/tmp")) / "macsonuclari.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"dusen {len(drop_rows)} seri {len(seri_rows)} -> {path}")


if __name__ == "__main__":
    main()
