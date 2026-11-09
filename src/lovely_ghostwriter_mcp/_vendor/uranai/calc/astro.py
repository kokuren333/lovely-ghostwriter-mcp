"""Astronomical primitives (Meeus, Astronomical Algorithms 2nd ed.).

All public functions take/return Julian Day in Universal Time (JD_UT) unless noted.
Accuracy targets (verified against PyEphem in tests/test_astro.py):
  sun apparent longitude ~0.01 deg, moon ~0.05 deg, solar-term instants ~ +-15 min.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
D2R = math.pi / 180.0


def norm360(x: float) -> float:
    x = math.fmod(x, 360.0)
    return x + 360.0 if x < 0 else x


def jd_from_datetime(dt: datetime) -> float:
    """Julian Day (UT) from an aware datetime."""
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    u = dt.astimezone(timezone.utc)
    y, m = u.year, u.month
    d = u.day + (u.hour + (u.minute + (u.second + u.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def datetime_from_jd(jd: float, tz=JST) -> datetime:
    epoch = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)  # JD 2451545.0
    return (epoch + timedelta(days=jd - 2451545.0)).astimezone(tz)


def jdn(y: int, m: int, d: int) -> int:
    """Chronological Julian Day Number of a Gregorian calendar date (integer, noon-based)."""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def delta_t_seconds(year: float) -> float:
    """Approximate Delta T (TT-UT) in seconds (Espenak & Meeus polynomials, simplified)."""
    y = year
    if y < 1920:
        return 20.0
    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t ** 2 / 233 + t ** 3 / 2547
    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t ** 2 / 260 - t ** 3 / 718
    if y < 2005:
        t = y - 2000
        return 63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3 + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5
    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    return 93.0


def _jde(jd_ut: float) -> float:
    year = 2000.0 + (jd_ut - 2451545.0) / 365.25
    return jd_ut + delta_t_seconds(year) / 86400.0


def _series(terms, tau):
    return sum(a * math.cos(b + c * tau) for a, b, c in terms)


def sun_apparent_longitude(jd_ut: float) -> float:
    """Apparent geocentric ecliptic longitude of the Sun, degrees.

    Truncated VSOP87 (Meeus ch.25 "higher accuracy" + App.III), FK5 correction,
    nutation (main terms) and aberration."""
    from . import _vsop_earth as v
    jde = _jde(jd_ut)
    tau = (jde - 2451545.0) / 365250.0
    l_rad = (_series(v.L0, tau) + _series(v.L1, tau) * tau + _series(v.L2, tau) * tau ** 2
             + _series(v.L3, tau) * tau ** 3 + _series(v.L4, tau) * tau ** 4 + _series(v.L5, tau) * tau ** 5) / 1e8
    r_au = (_series(v.R0, tau) + _series(v.R1, tau) * tau + _series(v.R2, tau) * tau ** 2) / 1e8
    theta = norm360(l_rad / D2R + 180.0)
    t = tau * 10.0
    theta -= 0.09033 / 3600.0  # FK5
    omega = (125.04452 - 1934.136261 * t) * D2R
    ls = (280.4665 + 36000.7698 * t) * D2R
    lm = (218.3165 + 481267.8813 * t) * D2R
    dpsi = (-17.20 * math.sin(omega) - 1.32 * math.sin(2 * ls) - 0.23 * math.sin(2 * lm) + 0.21 * math.sin(2 * omega)) / 3600.0
    aberration = -20.4898 / 3600.0 / r_au
    return norm360(theta + dpsi + aberration)


# Meeus Table 47.A (longitude terms, unit 1e-6 deg): D, M, M', F, coefficient
_MOON_TERMS = [
    (0, 0, 1, 0, 6288774), (2, 0, -1, 0, 1274027), (2, 0, 0, 0, 658314), (0, 0, 2, 0, 213618),
    (0, 1, 0, 0, -185116), (0, 0, 0, 2, -114332), (2, 0, -2, 0, 58793), (2, -1, -1, 0, 57066),
    (2, 0, 1, 0, 53322), (2, -1, 0, 0, 45758), (0, 1, -1, 0, -40923), (1, 0, 0, 0, -34720),
    (0, 1, 1, 0, -30383), (2, 0, 0, -2, 15327), (0, 0, 1, 2, -12528), (0, 0, 1, -2, 10980),
    (4, 0, -1, 0, 10675), (0, 0, 3, 0, 10034), (4, 0, -2, 0, 8548), (2, 1, -1, 0, -7888),
    (2, 1, 0, 0, -6766), (1, 0, -1, 0, -5163), (1, 1, 0, 0, 4987), (2, -1, 1, 0, 4036),
    (2, 0, 2, 0, 3994), (4, 0, 0, 0, 3861), (2, 0, -3, 0, 3665), (0, 1, -2, 0, -2689),
    (2, 0, -1, 2, -2602), (2, -1, -2, 0, 2390), (1, 0, 1, 0, -2348), (2, -2, 0, 0, 2236),
    (0, 1, 2, 0, -2120), (0, 2, 0, 0, -2069), (2, -2, -1, 0, 2048), (2, 0, 1, -2, -1773),
    (2, 0, 0, 2, -1595), (4, -1, -1, 0, 1215), (0, 0, 2, 2, -1110), (3, 0, -1, 0, -892),
    (2, 1, 1, 0, -810), (4, -1, -2, 0, 759), (0, 2, -1, 0, -713), (2, 2, -1, 0, -700),
    (2, 1, -2, 0, 691), (2, -1, 0, -2, 596), (4, 0, 1, 0, 549), (0, 0, 4, 0, 537),
    (4, -1, 0, 0, 520), (1, 0, -2, 0, -487), (2, 1, 0, -2, -399), (0, 0, 2, -2, -381),
    (1, 1, 1, 0, 351), (3, 0, -2, 0, -340), (4, 0, -3, 0, 330), (2, -1, 2, 0, 327),
    (0, 2, 1, 0, -323), (1, 1, -1, 0, 299), (2, 0, 3, 0, 294),
]


def moon_apparent_longitude(jd_ut: float) -> float:
    """Apparent geocentric ecliptic longitude of the Moon, degrees (Meeus ch.47, main terms)."""
    t = (_jde(jd_ut) - 2451545.0) / 36525.0
    lp = 218.3164477 + 481267.88123421 * t - 0.0015786 * t ** 2 + t ** 3 / 538841 - t ** 4 / 65194000
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t ** 2 + t ** 3 / 545868 - t ** 4 / 113065000
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t ** 2 + t ** 3 / 24490000
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t ** 2 + t ** 3 / 69699 - t ** 4 / 14712000
    f = 93.2720950 + 483202.0175233 * t - 0.0036539 * t ** 2 - t ** 3 / 3526000 + t ** 4 / 863310000
    a1 = 119.75 + 131.849 * t
    a2 = 53.09 + 479264.290 * t
    e = 1 - 0.002516 * t - 0.0000074 * t * t
    s = 0.0
    for cd, cm, cmp_, cf, coef in _MOON_TERMS:
        arg = (cd * d + cm * m + cmp_ * mp + cf * f) * D2R
        k = coef * (e ** abs(cm))
        s += k * math.sin(arg)
    s += 3958 * math.sin(a1 * D2R) + 1962 * math.sin((lp - f) * D2R) + 318 * math.sin(a2 * D2R)
    omega = (125.04452 - 1934.136261 * t) * D2R
    nutation = -0.004778 * math.sin(omega)  # main term of nutation in longitude
    return norm360(lp + s / 1e6 + nutation)


def obliquity(jd_ut: float) -> float:
    t = (_jde(jd_ut) - 2451545.0) / 36525.0
    eps0 = 23.0 + 26.0 / 60 + 21.448 / 3600 - (46.8150 * t + 0.00059 * t * t - 0.001813 * t ** 3) / 3600
    omega = (125.04452 - 1934.136261 * t) * D2R
    return eps0 + 0.00256 * math.cos(omega)


def gmst_deg(jd_ut: float) -> float:
    t = (jd_ut - 2451545.0) / 36525.0
    return norm360(280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933 * t * t - t ** 3 / 38710000)


def ascendant(jd_ut: float, lat_deg: float, lon_east_deg: float) -> float:
    """Ecliptic longitude of the Ascendant, degrees."""
    ramc = norm360(gmst_deg(jd_ut) + lon_east_deg) * D2R
    eps = obliquity(jd_ut) * D2R
    phi = lat_deg * D2R
    asc = math.atan2(math.cos(ramc), -(math.sin(ramc) * math.cos(eps) + math.tan(phi) * math.sin(eps)))
    return norm360(asc / D2R)


def find_sun_longitude(target_deg: float, jd_guess: float) -> float:
    """JD_UT at which the Sun's apparent longitude equals target_deg, nearest to jd_guess."""
    jd = jd_guess
    for _ in range(50):
        diff = (target_deg - sun_apparent_longitude(jd) + 540.0) % 360.0 - 180.0
        if abs(diff) < 1e-7:
            break
        jd += diff / 0.98564736
    return jd
