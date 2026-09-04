"""Distance / commute tool.

Uses straight-line (haversine) distance as a stand-in. Swap `_distance_km`'s
body for a real OneMap (https://www.onemap.gov.sg) routing call before demo —
OneMap is free, Singapore-official, and reads better to local judges than
Google Maps for this specific use case.
"""
from __future__ import annotations

import math
from functools import lru_cache

from ..schema import ChildProfile, SchoolFitEvidence
from .sen_support import get_school

# Placeholder geocode — replace with a real geocoder (OneMap /commonapi/search)
# keyed off profile.home_address_text / home_postal_district.
_DEMO_HOME_COORDS = (1.3521, 103.8198)


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_commute_minutes(distance_km: float) -> int:
    # Rough Singapore urban-commute heuristic: ~2.5 min/km, floor of 8 min.
    return max(8, round(distance_km * 2.5))


def commute_tool(profile: ChildProfile, school_id: str) -> SchoolFitEvidence:
    school = get_school(school_id)
    if school is None:
        raise ValueError(f"Unknown school_id: {school_id}")

    home_lat, home_lng = _DEMO_HOME_COORDS  # TODO: geocode profile.home_address_text
    dist = round(_distance_km(home_lat, home_lng, school["lat"], school["lng"]), 2)
    minutes = estimate_commute_minutes(dist)

    within_1km = dist <= 1.0
    within_2km = dist <= 2.0
    band = "within 1km" if within_1km else ("1-2km" if within_2km else "beyond 2km")

    score = 1.0 if within_1km else (0.6 if within_2km else 0.25)
    concern = None
    if profile.max_commute_minutes and minutes > profile.max_commute_minutes:
        concern = f"Estimated commute ({minutes} min) exceeds the stated limit ({profile.max_commute_minutes} min)."
        score = min(score, 0.3)

    return SchoolFitEvidence(
        school_id=school_id,
        source="commute",
        summary=f"{school['name']}: ~{dist} km, ~{minutes} min commute ({band} — matters for P1 balloting priority).",
        concern=concern,
        score_0_to_1=score,
        citation="Straight-line distance placeholder — replace with OneMap routing API before use.",
    )
