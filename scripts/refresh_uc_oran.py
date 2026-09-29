#!/usr/bin/env python3
"""Nesine bülteninden üç oran penceresini çıkar."""
from __future__ import annotations

import gzip
import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://bulten.nesine.com/api/bulten/getprebultenfull"

TOL = 0.10
RULES = {
    "iki15": {"ad": "İki yarıda 1,5 üst", "min": 4.20, "max": 4.32},
    "iySkorDiger": {"ad": "1. yarı skoru Diğer", "min": 12.80, "max": 13.50},
    "iyKgVar": {"ad": "1. yarı KG var", "min": 3.55, "max": 3.65},
}


def odd(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 1.01 or parsed >= 80:
        return None
    return round(parsed, 2)


def in_range(value, low, high):
    return value is not None and low - 1e-9 <= value <= high + 1e-9


def market_odd(markets, mtid, index=0):
    for market in markets:
        if market.get("MTID") != mtid:
            continue
        outcomes = market.get("OCA") or []
        if index < 0:
            index = len(outcomes) + index
        if 0 <= index < len(outcomes):
            return odd(outcomes[index].get("O"))
    return None


def diger_odd(markets):
    found = []
    for market in markets:
        if market.get("MTID") != 5:
            continue
        for outcome in market.get("OCA") or []:
            price = odd(outcome.get("O"))
            if in_range(price, RULES["iySkorDiger"]["min"] - TOL, RULES["iySkorDiger"]["max"] + TOL):
                found.append(price)
    return found[0] if found else None


def main():
    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "")
    if "gzip" in encoding or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8", "replace"))
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    today = now.strftime("%d.%m.%Y")
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
    matches = []
    for event in payload.get("sg", {}).get("EA") or []:
        if event.get("TYPE") != 1:
            continue
        if not event.get("HN") or not event.get("AN"):
            continue
        date = event.get("D") or ""
        time = event.get("T") or ""
        if date == today:
            pass
        elif date == tomorrow and time <= "23:59":
            pass
        else:
            continue
        markets = event.get("MA") or []
        iki15 = market_odd(markets, 529, 0)
        iy_kg = market_odd(markets, 599, 0)
        iy_diger = diger_odd(markets)
        hits = {
            "iki15": iki15 if in_range(iki15, RULES["iki15"]["min"] - TOL, RULES["iki15"]["max"] + TOL) else None,
            "iySkorDiger": iy_diger if in_range(iy_diger, RULES["iySkorDiger"]["min"] - TOL, RULES["iySkorDiger"]["max"] + TOL) else None,
            "iyKgVar": iy_kg if in_range(iy_kg, RULES["iyKgVar"]["min"] - TOL, RULES["iyKgVar"]["max"] + TOL) else None,
        }
        count = sum(1 for value in hits.values() if value is not None)
        if count < 2:
            continue
        matches.append(
            {
                "id": event.get("C"),
                "home": str(event.get("HN")).strip(),
                "away": str(event.get("AN")).strip(),
                "date": date,
                "time": time,
                "iki15": hits["iki15"],
                "iySkorDiger": hits["iySkorDiger"],
                "iyKgVar": hits["iyKgVar"],
                "n": count,
            }
        )

    def sort_key(row):
        day, month, year = (row["date"] or "01.01.1970").split(".")
        return (year + month + day, row["time"] or "", -row["n"], row["home"])

    matches.sort(key=sort_key)
    counts = {
        "iki15": sum(1 for row in matches if row["iki15"] is not None),
        "iySkorDiger": sum(1 for row in matches if row["iySkorDiger"] is not None),
        "iyKgVar": sum(1 for row in matches if row["iyKgVar"] is not None),
        "cift": sum(1 for row in matches if row["n"] >= 2),
    }
    out = {
        "updated": now.strftime("%Y-%m-%dT%H:%M%z"),
        "tol": TOL,
        "rules": RULES,
        "counts": counts,
        "matches": matches,
    }
    root = Path(__file__).resolve().parent
    path = (root.parent if root.name == "scripts" else Path("/tmp")) / "uc_oran.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(matches)} mac ({counts}) -> {path}")


if __name__ == "__main__":
    main()
