"""
boundary.py
-----------
The single API route: boundary lookup by coordinate and level.
Responses are RFC 7946 GeoJSON with Content-Type: application/geo+json.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.spatial import get_boundary

router = APIRouter()

# MIME type per RFC 7946
GEO_JSON_MEDIA_TYPE = "application/geo+json"


# Sync handler: the lookup is CPU-bound, so FastAPI runs it in its
# threadpool instead of blocking the event loop.
@router.get(
    "/boundary/",
    tags=["Boundary"],
    summary="Get boundary by coordinate and level",
    description=(
        "Pass a latitude/longitude pair and an administrative level. "
        "Returns an **RFC 7946 GeoJSON Feature** with `Content-Type: application/geo+json`."
    ),
    response_class=Response,
    responses={
        200: {"content": {GEO_JSON_MEDIA_TYPE: {}}, "description": "RFC 7946 GeoJSON Feature"},
        404: {"description": "No boundary found for the given coordinates"},
    },
)
def boundary_lookup(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (WGS84)", examples=[19.570304]),
    lng: float = Query(..., ge=-180, le=180, description="Longitude (WGS84)", examples=[77.8438]),
    level: Literal["village", "taluka", "district"] = Query(
        "village", description="Administrative level"
    ),
) -> Response:
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

    return Response(content=feature, media_type=GEO_JSON_MEDIA_TYPE)
