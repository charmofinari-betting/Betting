"""api-sports fixtures: fetch (with a local cache), normalise, and match sheet picks to fixtures.

Free plan: only dates from yesterday to tomorrow are available. Every response is
kept in data/api/<sport>/<date>.json, so re-runs are free and history is kept.
"""
import difflib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from log_picks import norm

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data" / "api"
KEY_FILE = HERE.parent / "secrets" / "api-sports.txt"
PHT = timezone(timedelta(hours=8))
SHEETS_EPOCH = datetime(1899, 12, 30)
ENDPOINTS = {
    "Football": "https://v3.football.api-sports.io/fixtures?date={date}&timezone=Asia/Manila",
    "Basketball": "https://v1.basketball.api-sports.io/games?date={date}&timezone=Asia/Manila",
}
FRESH_FOR = 3 * 3600  # re-fetch a cached day after 3h (kickoffs move, results arrive)

# Words that say nothing about which team it is.
NOISE = {"fc", "fk", "sk", "nk", "bc", "kk", "ac", "cf", "sc", "cd", "ca", "club", "de", "the", "afc",
         "basket", "basketball"}
# Words that say WHICH squad it is: these must agree, or it's a different team
# (Slavia Praha B is not Slavia Praha).
SQUAD = {"b": "reserve", "ii": "reserve", "2": "reserve", "reserves": "reserve", "u17": "u17", "u18": "u18",
         "u19": "u19", "u20": "u20", "u21": "u21", "u23": "u23", "w": "women", "women": "women",
         "womens": "women", "fem": "women", "femenino": "women", "ladies": "women"}


@dataclass(frozen=True)
class Game:
    sport: str
    id: int
    home: str
    away: str
    kickoff: float      # Sheets date serial, PHT
    league: str
    country: str
    status: str         # short code: NS, FT, AET, PEN, PST, CANC, ...
    home_score: int | None
    away_score: int | None
    home_ht: int | None
    away_ht: int | None


def serial(ts):
    return (datetime.fromtimestamp(ts, PHT).replace(tzinfo=None) - SHEETS_EPOCH).total_seconds() / 86400


def fetch(sport, date, now=None, session=requests):
    """Raw API JSON for one sport and date (YYYY-MM-DD, PHT), from cache when fresh."""
    path = CACHE / sport.lower() / f"{date}.json"
    now = now or time.time()
    if path.exists() and now - path.stat().st_mtime < FRESH_FOR:
        return json.loads(path.read_text(encoding="utf-8"))
    key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    data = session.get(ENDPOINTS[sport].format(date=date), headers={"x-apisports-key": key}, timeout=30).json()
    if data.get("errors"):
        raise RuntimeError(f"api-sports {sport} {date}: {data['errors']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def games(sport, data):
    out = []
    for g in data.get("response", []):
        if sport == "Football":
            f, ht = g["fixture"], g["score"]["halftime"]
            # Bets settle on 90 minutes: use the full-time score, not "goals" (which adds extra time).
            ft = g["score"]["fulltime"]
            home, away = (ft["home"], ft["away"]) if ft["home"] is not None else (g["goals"]["home"], g["goals"]["away"])
            out.append(Game(sport, f["id"], g["teams"]["home"]["name"], g["teams"]["away"]["name"],
                            serial(f["timestamp"]), g["league"]["name"], g["league"]["country"] or "",
                            f["status"]["short"], home, away, ht["home"], ht["away"]))
        else:
            s = g["scores"]
            ht = [None, None]
            if s["home"]["quarter_1"] is not None and s["home"]["quarter_2"] is not None:
                ht = [s[t]["quarter_1"] + s[t]["quarter_2"] for t in ("home", "away")]
            out.append(Game(sport, g["id"], g["teams"]["home"]["name"], g["teams"]["away"]["name"],
                            serial(g["timestamp"]), g["league"]["name"], (g.get("country") or {}).get("name", ""),
                            g["status"]["short"], s["home"]["total"], s["away"]["total"], ht[0], ht[1]))
    return out


def _tokens(name):
    return {t for t in norm(name).split() if t not in NOISE and t not in SQUAD}


def _squad(name):
    return {SQUAD[t] for t in norm(name).split() if t in SQUAD}


def name_score(sheet_name, api_name):
    """0..1. Token containment catches short API names ('Kashima' in 'Kashima Antlers');
    the character ratio catches spelling variants."""
    if _squad(sheet_name) != _squad(api_name):
        return 0.0
    a, b = _tokens(sheet_name), _tokens(api_name)
    contain = 0.0
    if a and b:
        common = a & b
        # A short common word only counts when it is the whole name on one side (HJK, SJK, AIK).
        if common and (max(len(t) for t in common) >= 4 or common in (a, b)):
            contain = len(common) / min(len(a), len(b))
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    return max(contain, ratio)


SURE, MAYBE = 0.8, 0.5


def match(sport, home, away, candidates, kickoff=None, aliases=None):
    """Best fixture for a pick. Returns (game, confidence) with confidence 'sure', 'check' or None.
    aliases: {sheet team name: api team name} confirmed earlier."""
    aliases = aliases or {}
    pool = [g for g in candidates if g.sport == sport
            and (kickoff is None or abs(g.kickoff - kickoff) <= 3 / 24)]
    scored = []
    for g in pool:
        h = 1.0 if aliases.get(home) == g.home else name_score(home, g.home)
        a = 1.0 if aliases.get(away) == g.away else name_score(away, g.away)
        scored.append((min(h, a), (h + a) / 2, g))
    if not scored:
        return None, None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    worst, avg, g = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0
    if worst >= SURE and runner_up < SURE:
        return g, "sure"
    if worst >= MAYBE:
        return g, "check"
    return None, None
