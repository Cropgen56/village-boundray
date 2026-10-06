"""
spatial.py
----------
All spatial query logic lives here.
Depends on GeoDataStore (data_loader.py) being loaded before use.

Responses are assembled directly as JSON bytes: geometry is serialized
with shapely's native (GEOS) GeoJSON writer, and the large taluka /
district geometries are serialized once and cached.
"""

import json
from functools import lru_cache
from typing import Optional

import shapely
from shapely.geometry import Point

from app.services.data_loader import geo_store


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_boundary(lat: float, lng: float, level: str) -> Optional[bytes]:
    """
    Find the boundary at the requested administrative level for the given
    coordinate and return an RFC 7946 GeoJSON Feature as UTF-8 bytes, or
    None if no feature matches.

    Parameters
    ----------
    lat   : Latitude  (WGS84)
    lng   : Longitude (WGS84)
    level : One of 'village', 'taluka', 'district'
    """
    idx = _find_village(Point(lng, lat))  # Shapely uses (x=lng, y=lat)
    if idx is None:
        return None

    name, taluka, district, state, census_code = geo_store.village_attrs[idx]

    if level == "village":
        geometry = _village_geojson(idx)
        props = {
            "level":       level,
            "name":        name,
            "taluka":      taluka,
            "district":    district,
            "state":       state,
            "census_code": census_code,
        }
    elif level == "taluka":
        geometry = _taluka_geojson(district, taluka)
        props = {
            "level":                level,
            "taluka":               taluka,
            "district":             district,
            "state":                state,
            "queried_village":      name,
            "queried_village_code": census_code,
        }
    else:  # district
        geometry = _district_geojson(district)
        props = {
            "level":                level,
            "district":             district,
            "state":                state,
            "queried_village":      name,
            "queried_village_code": census_code,
        }

    if geometry is None:
        return None

    return (
        '{"type":"Feature","geometry":' + geometry
        + ',"properties":' + json.dumps(props, ensure_ascii=False) + "}"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_village(point: Point) -> Optional[int]:
    """
    Return the index of the village polygon containing the point, or None.
    The STRtree filters by bounding box and evaluates the exact predicate
    in C; the lowest index wins if polygons overlap.
    """
    hits = geo_store.village_tree.query(point, predicate="within")
    return int(hits.min()) if len(hits) else None


def _village_geojson(idx: int) -> str:
    return shapely.to_geojson(geo_store.village_geoms[idx])


@lru_cache(maxsize=None)
def _taluka_geojson(district: str, taluka: str) -> Optional[str]:
    geom = geo_store.taluka_geoms.get((district, taluka))
    return None if geom is None else shapely.to_geojson(geom)


@lru_cache(maxsize=None)
def _district_geojson(district: str) -> Optional[str]:
    geom = geo_store.district_geoms.get(district)
    return None if geom is None else shapely.to_geojson(geom)
