from pathlib import Path

# Base directory of the project (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data directory where GeoJSON files live
DATA_DIR = BASE_DIR / "data"

# GeoJSON files to load
GEOJSON_FILES = [
    DATA_DIR / "mh1.geojson",
    DATA_DIR / "mh2.geojson",
]

# App metadata
APP_TITLE = "Maharashtra Boundary API"
APP_DESCRIPTION = (
    "Given a coordinate (lat/lng) in Maharashtra, returns the boundary "
    "at village, taluka (sub-district), or district level."
)
APP_VERSION = "1.0.0"

# Supported administrative levels
SUPPORTED_LEVELS = {"village", "taluka", "district"}

# Column names in the GeoJSON properties
COL_NAME     = "NAME"
COL_DISTRICT = "DISTRICT"
COL_TALUKA   = "SUB_DIST"
COL_STATE    = "STATE"
COL_TYPE     = "TYPE"
COL_CEN      = "CEN_2001"
