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



YARI12_GAP = 0.20


def triple(markets, mtid):
    for market in markets:
        if market.get("MTID") != mtid:
            continue
        outcomes = market.get("OCA") or []
        if len(outcomes) >= 3:
            return odd(outcomes[0].get("O")), odd(outcomes[1].get("O")), odd(outcomes[2].get("O"))
    return None, None, None


def close_pair(a, b, gap=YARI12_GAP):
    return a is not None and b is not None and abs(a - b) <= gap + 1e-9


def yari12_row(event, markets):
    ms1, msx, ms2 = triple(markets, 1)
    iy1, iyx, iy2 = triple(markets, 9)
    cs1x, cs12, csx2 = triple(markets, 8)
    if not close_pair(ms1, ms2) or not close_pair(iy1, iy2):
        return None
    if cs1x is None or cs12 is None or csx2 is None:
        return None
    if not close_pair(cs1x, csx2):
        return None
    return {
        "id": event.get("C"),
        "home": str(event.get("HN")).strip(),
        "away": str(event.get("AN")).strip(),
        "date": event.get("D") or "",
        "time": event.get("T") or "",
        "ms1": ms1,
        "msx": msx,
        "ms2": ms2,
        "iy1": iy1,
        "iyx": iyx,
        "iy2": iy2,
        "cs1x": cs1x,
        "cs12": cs12,
        "csx2": csx2,
        "msGap": round(abs(ms1 - ms2), 2),
        "iyGap": round(abs(iy1 - iy2), 2),
        "csGap": round(abs(cs1x - csx2), 2),
    }


UST45 = {
    "ust45": {"ad": "4,5 üst", "min": 4.20, "max": 5.10},
    "iy1ust": {"ad": "1. yarı 1 ve üst", "min": 5.40, "max": 6.20},
    "gol45": {"ad": "Toplam gol 4-5", "min": 2.80, "max": 3.10},
}


def ust45_row(event, markets):
    ust = market_odd(markets, 155, 1)
    iy1 = market_odd(markets, 342, 0)
    gol = market_odd(markets, 43, 2)
    hits = {
        "ust45": ust if in_range(ust, UST45["ust45"]["min"], UST45["ust45"]["max"]) else None,
        "iy1ust": iy1 if in_range(iy1, UST45["iy1ust"]["min"], UST45["iy1ust"]["max"]) else None,
        "gol45": gol if in_range(gol, UST45["gol45"]["min"], UST45["gol45"]["max"]) else None,
    }
    count = sum(1 for value in hits.values() if value is not None)
    if count < 2:
        return None
    return {
        "id": event.get("C"),
        "home": str(event.get("HN")).strip(),
        "away": str(event.get("AN")).strip(),
        "date": event.get("D") or "",
        "time": event.get("T") or "",
        "ust45": hits["ust45"],
        "iy1ust": hits["iy1ust"],
        "gol45": hits["gol45"],
        "n": count,
    }


IY21 = {
    "iy21": {"ad": "İY skor 2-1", "min": 17.90, "max": 18.90},
    "plus4": {"ad": "İY/MS 4+/4+", "min": 14.80, "max": 16.20},
    "gol23": {"ad": "Toplam gol 2-3", "min": 1.82, "max": 1.90},
}


def labeled_odd(markets, mtid, label):
    for market in markets:
        if market.get("MTID") != mtid:
            continue
        for outcome in market.get("OCA") or []:
            if str(outcome.get("ON") or "") == label:
                return odd(outcome.get("O"))
    return None


def iy21_row(event, markets):
    iy21 = labeled_odd(markets, 779, "2:1")
    plus4 = market_odd(markets, 571, -1)
    gol23 = market_odd(markets, 43, 1)
    hits = {
        "iy21": iy21 if in_range(iy21, IY21["iy21"]["min"], IY21["iy21"]["max"]) else None,
        "plus4": plus4 if in_range(plus4, IY21["plus4"]["min"], IY21["plus4"]["max"]) else None,
        "gol23": gol23 if in_range(gol23, IY21["gol23"]["min"], IY21["gol23"]["max"]) else None,
    }
    count = sum(1 for value in hits.values() if value is not None)
    if count < 2:
        return None
    return {
        "id": event.get("C"),
        "home": str(event.get("HN")).strip(),
        "away": str(event.get("AN")).strip(),
        "date": event.get("D") or "",
        "time": event.get("T") or "",
        "iy21": hits["iy21"],
        "plus4": hits["plus4"],
        "gol23": hits["gol23"],
        "n": count,
    }

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
    yari12 = []
    ust45 = []
    iy21 = []
    for event in payload.get("sg", {}).get("EA") or []:
        if event.get("TYPE") != 1:
            continue
        if not event.get("HN") or not event.get("AN"):
            continue
        date = event.get("D") or ""
        time = event.get("T") or ""
        markets = event.get("MA") or []
        row12 = yari12_row(event, markets)
        if row12:
            yari12.append(row12)
        row45 = ust45_row(event, markets)
        if row45:
            ust45.append(row45)
        row21 = iy21_row(event, markets)
        if row21:
            iy21.append(row21)
        if date == today:
            pass
        elif date == tomorrow and time <= "23:59":
            pass
        else:
            continue
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
        "ust45": len(ust45),
        "yari12": len(yari12),
    }

    def sort_key12(row):
        day, month, year = (row["date"] or "01.01.1970").split(".")
        return (year + month + day, row["time"] or "", row["msGap"], row["home"])

    yari12.sort(key=sort_key12)
    ust45.sort(key=sort_key)
    iy21.sort(key=sort_key)
    out = {
        "updated": now.strftime("%Y-%m-%dT%H:%M%z"),
        "tol": TOL,
        "yari12Gap": YARI12_GAP,
        "rules": RULES,
        "counts": counts,
        "matches": matches,
        "yari12": yari12,
        "ust45Rules": UST45,
        "ust45": ust45,
        "iy21Rules": IY21,
        "iy21": iy21,
    }
    root = Path(__file__).resolve().parent
    path = (root.parent if root.name == "scripts" else Path("/tmp")) / "uc_oran.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(matches)} mac ({counts}) 1/2={len(yari12)} 4.5={len(ust45)} iy21={len(iy21)} -> {path}")


if __name__ == "__main__":
    main()
