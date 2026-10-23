#!/usr/bin/env python3
"""Bülten üzerine geliştirilmiş model:
- Power de-vig
- Dixon-Coles düzeltilmiş Poisson
- Lig filtresi + min played + edge cap
- Home advantage
"""
from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Europe/Istanbul")
ROOT = Path(__file__).resolve().parent.parent

SITES = ["Forebet", "PredictZ", "WinDrawWin", "Statarea", "SoccerVista"]
MIN_EDGE = 0.05
MAX_EDGE = 0.22
MIN_PLAYED = 6
RHO = -0.13  # Dixon-Coles rho

ALLOWED_LEAGUES = {
    "TSL", "T1L",
    "İNP", "INGPL2",
    "İTA", "İTB",
    "İS1", "İS2",
    "FR1", "FR2",
    "HOL", "HOL2",
    "POR", "POR2",
    "BEL", "BEL2",
    "RUS1", "UKR",
    "POL1", "ÇEK2",
    "DAN1", "NOR",
    "İSV", "AVU",
    "AL1", "BR1",
}

def is_allowed_league(league: str) -> bool:
    return bool(league) and league.upper() in {l.upper() for l in ALLOWED_LEAGUES}

def enough_played(home, away) -> bool:
    if not home or not away:
        return False
    return (home.get("played") or 0) >= MIN_PLAYED and (away.get("played") or 0) >= MIN_PLAYED

def atomic_write_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def dixon_coles_probs(xg_h: float, xg_a: float, rho: float = RHO, max_goals: int = 8) -> dict | None:
    if xg_h is None or xg_a is None or xg_h < 0 or xg_a < 0:
        return None
    home_wins = draws = away_wins = under25 = 0.0
    total = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, xg_h) * poisson_pmf(a, xg_a)
            # Dixon-Coles tau
            if h == 0 and a == 0:
                tau = 1 - xg_h * xg_a * rho
            elif h == 0 and a == 1:
                tau = 1 + xg_h * rho
            elif h == 1 and a == 0:
                tau = 1 + xg_a * rho
            elif h == 1 and a == 1:
                tau = 1 - rho
            else:
                tau = 1.0
            p *= max(tau, 0.0)
            total += p
            if h > a:
                home_wins += p
            elif h == a:
                draws += p
            else:
                away_wins += p
            if h + a < 3:
                under25 += p
    if total <= 0:
        return None
    p1 = home_wins / total
    px = draws / total
    p2 = away_wins / total
    return {
        "opta_p1": round(p1 * 100, 1),
        "opta_px": round(px * 100, 1),
        "opta_p2": round(p2 * 100, 1),
        "opta_max": round(max(p1, px, p2) * 100, 1),
        "opta_under25": round(under25 / total * 100, 1),
        "opta_fav": "1" if p1 >= px and p1 >= p2 else ("X" if px >= p2 else "2"),
        "opta_sims": "DixonColes-matrix",
    }

def power_devig(odds: list[float]) -> tuple[list[float], float] | None:
    if any(o is None or o <= 1.01 for o in odds):
        return None
    implied = [1.0 / o for o in odds]
    if sum(implied) <= 1.0:
        return implied, 1.0
    lo, hi = 0.5, 2.0
    for _ in range(50):
        mid = (lo + hi) / 2
        total = sum(p ** mid for p in implied)
        if total > 1.0:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    fair = [p ** k for p in implied]
    s = sum(fair)
    fair = [x / s for x in fair]
    return fair, k

def consensus(opta_fav: Optional[str], site_picks: Optional[dict] = None) -> dict:
    if not site_picks:
        return {
            "consensus": 0, "agree": 0, "total": 5,
            "label": "site verisi bekleniyor", "strong": False, "sites": SITES,
        }
    agrees = sum(1 for p in site_picks.values() if p == opta_fav)
    total = len(site_picks)
    score = (agrees / total * 100) if total else 0
    return {
        "consensus": round(score), "agree": agrees, "total": total,
        "label": f"{agrees}/{total} site Opta ile aynı",
        "strong": score >= 60, "sites": list(site_picks.keys()),
    }

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
    exp_home = round(h_att * a_def * lg_h * 1.10, 2)
    exp_away = round(a_att * h_def * lg_a * 0.90, 2)
    return {"xgH": exp_home, "xgA": exp_away}

def main():
    path = ROOT / "bulten.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    filled = 0
    high_prob = []
    high_edge = []
    for match in data.get("matches") or []:
        league = match.get("league") or ""
        allowed = is_allowed_league(league)
        home_tbl = (match.get("homeTable") or {}).get("home")
        away_tbl = (match.get("awayTable") or {}).get("away")
        played_ok = enough_played(home_tbl, away_tbl)

        xg = poisson_xg(home_tbl, away_tbl, match.get("lgH"), match.get("lgA"))
        if not xg or not played_ok:
            for k in ("xgH", "xgA", "opta_p1", "opta_px", "opta_p2", "opta_max", "opta_under25", "opta_fav", "opta_sims", "consensus",
                      "fair_p1", "fair_px", "fair_p2", "edge_1", "edge_x", "edge_2", "has_edge", "power_k"):
                match.pop(k, None)
            continue
        match.update(xg)
        probs = dixon_coles_probs(xg["xgH"], xg["xgA"])
        if probs:
            match.update(probs)
            site_picks = match.get("site_picks")
            cons = consensus(probs["opta_fav"], site_picks)
            match["consensus"] = cons
            filled += 1
            if probs["opta_max"] >= 55 and allowed:
                high_prob.append({
                    "id": match.get("id"), "home": match.get("home"), "away": match.get("away"),
                    "league": league, "date": match.get("date"), "time": match.get("time"),
                    "opta_max": probs["opta_max"], "opta_fav": probs["opta_fav"],
                    "consensus": cons["consensus"], "consensus_label": cons["label"], "strong": cons["strong"],
                })

        odds = [match.get("o1"), match.get("ox"), match.get("o2")]
        devig = power_devig(odds)
        if devig and probs and allowed and played_ok:
            fair, k = devig
            match["fair_p1"] = round(fair[0] * 100, 1)
            match["fair_px"] = round(fair[1] * 100, 1)
            match["fair_p2"] = round(fair[2] * 100, 1)
            match["power_k"] = round(k, 3)
            e1 = (probs["opta_p1"] / 100) - fair[0]
            ex = (probs["opta_px"] / 100) - fair[1]
            e2 = (probs["opta_p2"] / 100) - fair[2]
            match["edge_1"] = round(e1 * 100, 1)
            match["edge_x"] = round(ex * 100, 1)
            match["edge_2"] = round(e2 * 100, 1)
            max_edge = max(e1, ex, e2)
            match["has_edge"] = MIN_EDGE <= max_edge <= MAX_EDGE
            if match["has_edge"]:
                high_edge.append({
                    "id": match.get("id"), "home": match.get("home"), "away": match.get("away"),
                    "league": league, "date": match.get("date"), "time": match.get("time"),
                    "opta_fav": probs["opta_fav"], "max_edge": round(max_edge * 100, 1),
                    "o1": match.get("o1"), "ox": match.get("ox"), "o2": match.get("o2"),
                    "fair_p1": match["fair_p1"], "opta_p1": probs["opta_p1"],
                })

    high_prob.sort(key=lambda x: (-x["opta_max"], -x["consensus"]))
    high_edge.sort(key=lambda x: -x["max_edge"])
    data["xgUpdated"] = datetime.now(IST).isoformat(timespec="minutes")
    data["optaHigh"] = high_prob[:20]
    data["edgeHigh"] = high_edge[:20]
    data["optaModel"] = "DixonColes + PowerDeVig + LeagueFilter + MinPlayed + EdgeCap"
    data["consensusSites"] = SITES
    data["minEdge"] = MIN_EDGE
    data["maxEdge"] = MAX_EDGE
    data["minPlayed"] = MIN_PLAYED
    data["rho"] = RHO
    data["allowedLeagues"] = sorted(ALLOWED_LEAGUES)
    atomic_write_json(path, data)
    atomic_write_json(ROOT / "app_summary.json", {
        "updated": data["xgUpdated"],
        "status": "success",
        "xg": filled,
        "matches": len(data.get("matches") or []),
        "opta_high": len(high_prob),
        "edge_high": len(high_edge),
        "model": "DixonColes+PowerDeVig+LeagueFilter+MinPlayed+EdgeCap",
    })
    print(f"Dixon-Coles analysis: {filled} with xG, high-edge: {len(high_edge)}")

if __name__ == "__main__":
    main()
