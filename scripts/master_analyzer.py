#!/usr/bin/env python3
"""Bulten uzerine Poisson xG ekler. Nesine ve Macsonuclari ayri betiklerde kalir."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Europe/Istanbul")
ROOT = Path(__file__).resolve().parent.parent


def atomic_write_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def poisson_xg(home, away, lg_h, lg_a):
    if not home or not away or not lg_h or not lg_a:
        return None
    hp, ap = home.get("played") or 0, away.get("played") or 0
    if hp <= 0 or ap <= 0:
        return None
    h_att = (home["gf"] / hp) / lg_h
    h_def = (home["ga"] / hp) / lg_a
    a_att = (away["gf"] / ap) / lg_a
    a_def = (away["ga"] / ap) / lg_h
    exp_home = round(h_att * a_def * lg_h, 2)
    exp_away = round(a_att * h_def * lg_a, 2)
    under = 0.0
    for h in range(4):
        for a in range(4):
            if h + a < 3:
                under += (math.exp(-exp_home) * exp_home ** h / math.factorial(h)) * (
                    math.exp(-exp_away) * exp_away ** a / math.factorial(a)
                )
    return {
        "xgH": exp_home,
        "xgA": exp_away,
        "ust25": round((1 - under) * 100, 1),
    }


def main():
    path = ROOT / "bulten.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    filled = 0
    for match in data.get("matches") or []:
        home = (match.get("homeTable") or {}).get("home")
        away = (match.get("awayTable") or {}).get("away")
        xg = poisson_xg(home, away, match.get("lgH"), match.get("lgA"))
        if not xg:
            match.pop("xgH", None)
            match.pop("xgA", None)
            match.pop("ust25", None)
            continue
        match.update(xg)
        filled += 1
    data["xgUpdated"] = datetime.now(IST).isoformat(timespec="minutes")
    atomic_write_json(path, data)
    atomic_write_json(ROOT / "app_summary.json", {
        "updated": data["xgUpdated"],
        "status": "success",
        "xg": filled,
        "matches": len(data.get("matches") or []),
    })
    print(f"xG {filled}/{len(data.get('matches') or [])}")


if __name__ == "__main__":
    main()
