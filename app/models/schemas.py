from typing import Any, Optional
from pydantic import BaseModel, Field


class BoundaryRequest(BaseModel):
    """Query parameters for a boundary lookup."""
    lat: float = Field(..., description="Latitude of the point (WGS84)", ge=-90, le=90)
    lng: float = Field(..., description="Longitude of the point (WGS84)", ge=-180, le=180)
    level: str = Field(
        "village",
        description="Administrative level: 'village', 'taluka', or 'district'",
    )


class GeoJSONGeometry(BaseModel):
    """Minimal GeoJSON geometry schema."""
    type: str
    coordinates: Any


class GeoJSONFeature(BaseModel):
    """
    RFC 7946-compliant GeoJSON Feature.
    All boundary metadata lives inside `properties`.
    """
    type: str = Field("Feature", description="Always 'Feature'")
    geometry: GeoJSONGeometry
    properties: dict[str, Optional[Any]] = Field(
        ...,
        description=(
            "Boundary metadata. For village: name, taluka, district, state, "
            "census_code, level. For taluka: taluka, district, state, level. "
            "For district: district, state, level."
        ),
    )
