"""
spatial.py
----------
All spatial query logic lives here.
Depends on GeoDataStore (data_loader.py) being loaded before use.
"""

import json
import logging
from typing import Optional

from shapely.geometry import Point

from app.core.config import (
    COL_DISTRICT,
    COL_TALUKA,
    COL_NAME,
    COL_STATE,
    COL_CEN,
    SUPPORTED_LEVELS,
)
from app.services.data_loader import geo_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_boundary(lat: float, lng: float, level: str) -> Optional[dict]:
    """
    Find the boundary at the requested administrative level for the given
    coordinate and return an RFC 7946 GeoJSON Feature dict, or None if
    no feature matches.

    Parameters
    ----------
    lat   : Latitude  (WGS84)
    lng   : Longitude (WGS84)
    level : One of 'village', 'taluka', 'district'
    """
    if level not in SUPPORTED_LEVELS:
        raise ValueError(
            f"Unsupported level '{level}'. Choose from: {sorted(SUPPORTED_LEVELS)}"
        )

    point = Point(lng, lat)  # Shapely uses (x=lng, y=lat)

    # Step 1: find the village that contains the point
    village_row = _find_village(point)
    if village_row is None:
        return None

    # Step 2: fetch the geometry + build proper GeoJSON Feature at requested level
    return _build_feature(village_row, level)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_village(point: Point) -> Optional[dict]:
    """
    Use STRtree to quickly narrow candidates, then do exact containment check.
    Returns the matched GeoDataFrame row as a dict, or None.
    """
    tree = geo_store.village_tree
    gdf  = geo_store.village_gdf

    # STRtree.query returns indices of geometries whose bboxes intersect the point
    candidate_indices = tree.query(point)

    for idx in candidate_indices:
        geom = gdf.geometry.iloc[idx]
        if geom.contains(point):
            return gdf.iloc[idx].to_dict()

    return None


def _build_feature(village_row: dict, level: str) -> Optional[dict]:
    """
    Build an RFC 7946 GeoJSON Feature for the requested admin level.
    All metadata goes into the `properties` object.
    """
    # --- resolve the geometry row for this level ---
    if level == "village":
        geom_row = village_row
    elif level == "taluka":
        district = village_row.get(COL_DISTRICT)
        taluka   = village_row.get(COL_TALUKA)
        gdf  = geo_store.taluka_gdf
        mask = (gdf[COL_DISTRICT] == district) & (gdf[COL_TALUKA] == taluka)
        matched = gdf[mask]
        if matched.empty:
            logger.warning("No taluka geometry for district=%s taluka=%s", district, taluka)
            return None
        geom_row = matched.iloc[0].to_dict()
    elif level == "district":
        district = village_row.get(COL_DISTRICT)
        gdf  = geo_store.district_gdf
        mask = gdf[COL_DISTRICT] == district
        matched = gdf[mask]
        if matched.empty:
            logger.warning("No district geometry for district=%s", district)
            return None
        geom_row = matched.iloc[0].to_dict()
    else:
        return None

    # --- serialize geometry ---
    geometry = geom_row.get("geometry")
    if geometry is None:
        return None

    geom_dict = json.loads(json.dumps(geometry.__geo_interface__))

    # --- build properties (all metadata lives here, per RFC 7946) ---
    props: dict = {"level": level}

    # Always include the full admin hierarchy from the original village hit
    if level == "village":
        props["name"]         = village_row.get(COL_NAME)
        props["taluka"]       = village_row.get(COL_TALUKA)
        props["district"]     = village_row.get(COL_DISTRICT)
        props["state"]        = village_row.get(COL_STATE)
        props["census_code"]  = (
            str(village_row[COL_CEN]) if village_row.get(COL_CEN) else None
        )
    elif level == "taluka":
        props["taluka"]   = village_row.get(COL_TALUKA)
        props["district"] = village_row.get(COL_DISTRICT)
        props["state"]    = village_row.get(COL_STATE)
        # include the queried village as reference
        props["queried_village"]      = village_row.get(COL_NAME)
        props["queried_village_code"] = (
            str(village_row[COL_CEN]) if village_row.get(COL_CEN) else None
        )
    elif level == "district":
        props["district"] = village_row.get(COL_DISTRICT)
        props["state"]    = village_row.get(COL_STATE)
        props["queried_village"]      = village_row.get(COL_NAME)
        props["queried_village_code"] = (
            str(village_row[COL_CEN]) if village_row.get(COL_CEN) else None
        )

    # --- assemble RFC 7946 Feature ---
    return {
        "type":       "Feature",
        "geometry":   geom_dict,
        "properties": props,
    }
