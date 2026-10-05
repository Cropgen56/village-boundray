"""
boundary.py
-----------
API routes for the boundary lookup endpoints.
Responses are RFC 7946 GeoJSON with Content-Type: application/geo+json.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.config import SUPPORTED_LEVELS
from app.services.spatial import get_boundary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boundary", tags=["Boundary"])

# MIME type per RFC 7946
GEO_JSON_MEDIA_TYPE = "application/geo+json"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/",
    summary="Get boundary by coordinate and level",
    description=(
        "Pass a latitude/longitude pair and an administrative level "
        "(`village`, `taluka`, or `district`). "
        "Returns an **RFC 7946 GeoJSON Feature** with `Content-Type: application/geo+json`. "
        "All metadata (name, taluka, district, state, census_code, level) is "
        "inside the `properties` object — ready to drop into any GIS tool or mapping library."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {GEO_JSON_MEDIA_TYPE: {}},
            "description": "RFC 7946 GeoJSON Feature",
        },
        404: {"description": "No boundary found for the given coordinates"},
        422: {"description": "Invalid query parameters"},
    },
)
async def boundary_lookup(
    lat: float = Query(..., description="Latitude (WGS84)", ge=-90, le=90, example=19.076),
    lng: float = Query(..., description="Longitude (WGS84)", ge=-180, le=180, example=72.877),
    level: str = Query(
        "village",
        description="Administrative level: `village` | `taluka` | `district`",
        examples=["village", "taluka", "district"],
    ),
) -> Response:
    level = level.lower().strip()

    if level not in SUPPORTED_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid level '{level}'. Supported values: {sorted(SUPPORTED_LEVELS)}",
        )

    logger.info("Boundary request → lat=%.6f lng=%.6f level=%s", lat, lng, level)

    feature = get_boundary(lat=lat, lng=lng, level=level)

    if feature is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {level} boundary found for coordinates "
                f"(lat={lat}, lng={lng}). "
                "Ensure the point is within Maharashtra, India."
            ),
        )

    return Response(
        content=json.dumps(feature, ensure_ascii=False),
        media_type=GEO_JSON_MEDIA_TYPE,
    )


@router.get(
    "/levels",
    summary="List supported administrative levels",
    description="Returns the list of administrative levels supported by this API.",
)
async def list_levels() -> dict:
    return {
        "supported_levels": sorted(SUPPORTED_LEVELS),
        "description": {
            "village":  "Individual village boundary — most granular, polygon per village",
            "taluka":   "Sub-district / taluka boundary — villages dissolved by taluka",
            "district": "District boundary — villages dissolved by district",
        },
    }
