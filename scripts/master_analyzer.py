#!/usr/bin/env python3
"""Bülten üzerine Opta Supercomputer tarzı Monte Carlo + 5 site konsensüs katmanı.
Her maç için binlerce simülasyon + ortak karar skoru."""
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


def atomic_write_json(path: Path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def sample_poisson(lam: float) -> int:
    if lam is None or lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
        if k > 15:
            break
    return k - 1


def opta_monte_carlo(xg_h: float, xg_a: float, n_sims: int = 15000) -> dict | None:
    if xg_h is None or xg_a is None:
        return None
    home_wins = draws = away_wins = under25 = 0
    for _ in range(n_sims):
        gh = sample_poisson(xg_h)
        ga = sample_poisson(xg_a)
        if gh > ga:
            home_wins += 1
        elif gh == ga:
            draws += 1
        else:
            away_wins += 1
        if gh + ga < 3:
            under25 += 1
    total = home_wins + draws + away_wins
    if total == 0:
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
        "opta_sims": n_sims,
    }


def consensus(opta_fav: Optional[str], site_picks: Optional[dict] = None) -> dict:
    """5 site ile Opta ortak karar. site_picks yoksa beklemede."""
    if not site_picks:
        return {
            "consensus": 0,
            "agree": 0,
            "total": 5,
            "label": "site verisi bekleniyor",
            "strong": False,
            "sites": SITES,
        }
    agrees = sum(1 for p in site_picks.values() if p == opta_fav)
    total = len(site_picks)
    score = (agrees / total * 100) if total else 0
    return {
        "consensus": round(score),
        "agree": agrees,
        "total": total,
        "label": f"{agrees}/{total} site Opta ile aynı",
        "strong": score >= 60,
        "sites": list(site_picks.keys()),
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
    exp_home = round(h_att * a_def * lg_h, 2)
    exp_away = round(a_att * h_def * lg_a, 2)
    return {"xgH": exp_home, "xgA": exp_away}


def main():
    path = ROOT / "bulten.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    filled = 0
    high_prob = []
    for match in data.get("matches") or []:
        home = (match.get("homeTable") or {}).get("home")
        away = (match.get("awayTable") or {}).get("away")
        xg = poisson_xg(home, away, match.get("lgH"), match.get("lgA"))
        if not xg:
            for k in ("xgH", "xgA", "opta_p1", "opta_px", "opta_p2", "opta_max", "opta_under25", "opta_fav", "opta_sims", "consensus"):
                match.pop(k, None)
            continue
        match.update(xg)
        probs = opta_monte_carlo(xg["xgH"], xg["xgA"])
        if probs:
            match.update(probs)
            # site_picks alanı varsa kullan, yoksa beklemede
            site_picks = match.get("site_picks")
            cons = consensus(probs["opta_fav"], site_picks)
            match["consensus"] = cons
            filled += 1
            if probs["opta_max"] >= 55:
                high_prob.append({
                    "id": match.get("id"),
                    "home": match.get("home"),
                    "away": match.get("away"),
                    "league": match.get("league"),
                    "date": match.get("date"),
                    "time": match.get("time"),
                    "opta_max": probs["opta_max"],
                    "opta_fav": probs["opta_fav"],
                    "consensus": cons["consensus"],
                    "consensus_label": cons["label"],
                    "strong": cons["strong"],
                })
    high_prob.sort(key=lambda x: (-x["opta_max"], -x["consensus"]))
    data["xgUpdated"] = datetime.now(IST).isoformat(timespec="minutes")
    data["optaHigh"] = high_prob[:30]
    data["optaModel"] = "MonteCarlo-15000 + Consensus"
    data["consensusSites"] = SITES
    atomic_write_json(path, data)
    atomic_write_json(ROOT / "app_summary.json", {
        "updated": data["xgUpdated"],
        "status": "success",
        "xg": filled,
        "matches": len(data.get("matches") or []),
        "opta_high": len(high_prob),
        "model": "MonteCarlo+Consensus",
    })
    print(f"Opta MC + Konsensüs {filled}/{len(data.get('matches') or [])}, high-prob: {len(high_prob)}")


if __name__ == "__main__":
    main()
