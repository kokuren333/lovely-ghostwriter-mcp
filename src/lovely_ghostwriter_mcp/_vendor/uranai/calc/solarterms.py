"""The 12 'jie' (節) solar terms that open each sexagenary month."""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from . import astro

# (sun longitude, name, month branch index 0=子..11=亥)
JIE = [
    (285, "小寒", 1), (315, "立春", 2), (345, "啓蟄", 3), (15, "清明", 4), (45, "立夏", 5), (75, "芒種", 6),
    (105, "小暑", 7), (135, "立秋", 8), (165, "白露", 9), (195, "寒露", 10), (225, "立冬", 11), (255, "大雪", 0),
]
# approximate Gregorian (month, day) for initial guesses, in the same order as JIE
_GUESS = [(1, 6), (2, 4), (3, 6), (4, 5), (5, 6), (6, 6), (7, 7), (8, 8), (9, 8), (10, 8), (11, 7), (12, 7)]


@lru_cache(maxsize=512)
def jie_instants(year: int) -> tuple:
    """All 12 jie instants of a Gregorian year as tuples (jd_ut, name, branch, lon)."""
    out = []
    for (lon, name, br), (m, d) in zip(JIE, _GUESS):
        guess = astro.jd_from_datetime(datetime(year, m, d, 12, tzinfo=astro.JST))
        out.append((astro.find_sun_longitude(lon, guess), name, br, lon))
    return tuple(out)


def surrounding_jie(jd_ut: float, year_hint: int):
    """Return (previous_jie, next_jie) around jd_ut; each is (jd, name, branch, lon)."""
    cands = []
    for y in (year_hint - 1, year_hint, year_hint + 1):
        cands.extend(jie_instants(y))
    cands.sort()
    prev = max((c for c in cands if c[0] <= jd_ut), key=lambda c: c[0])
    nxt = min((c for c in cands if c[0] > jd_ut), key=lambda c: c[0])
    return prev, nxt


def risshun(year: int) -> float:
    return jie_instants(year)[1][0]
