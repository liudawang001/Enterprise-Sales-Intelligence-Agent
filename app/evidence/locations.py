from __future__ import annotations

from math import cos, radians, sqrt

from app.entities.enums import EntityType
from app.entities.models import EnterpriseLocation
from app.entities.normalizer import AddressNormalizer


def _distance_m(left: EnterpriseLocation, right: EnterpriseLocation) -> float | None:
    if None in {left.lat, left.lng, right.lat, right.lng}:
        return None
    dx = (left.lng - right.lng) * 111_320 * cos(radians((left.lat + right.lat) / 2))
    dy = (left.lat - right.lat) * 110_540
    return sqrt(dx * dx + dy * dy)


def deduplicate_office_locations(
    locations: list[EnterpriseLocation], *, coordinate_tolerance_m: float = 50
) -> list[EnterpriseLocation]:
    allowed = {EntityType.OFFICE, EntityType.BRANCH}
    result: list[EnterpriseLocation] = []
    normalizer = AddressNormalizer()
    for item in locations:
        if item.location_type not in allowed:
            continue
        normalized = normalizer.normalize(item.address) or item.normalized_address
        candidate = item.model_copy(update={"normalized_address": normalized})
        duplicate = any(
            existing.normalized_address == normalized
            or (_distance_m(existing, candidate) is not None and _distance_m(existing, candidate) <= coordinate_tolerance_m)
            for existing in result
        )
        if not duplicate:
            result.append(candidate)
    return result
