import os

# Cloud Storage location of the boundary datasets (private bucket).
# Set via environment variables — see .env.example.
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")

# GeoJSON objects to load, in order: {env var name: object path}
GCS_GEOJSON_OBJECTS = {
    "GCS_MH1_PATH": os.getenv("GCS_MH1_PATH", ""),
    "GCS_MH2_PATH": os.getenv("GCS_MH2_PATH", ""),
}

# Column names in the GeoJSON properties
COL_NAME     = "NAME"
COL_DISTRICT = "DISTRICT"
COL_TALUKA   = "SUB_DIST"
COL_STATE    = "STATE"
COL_CEN      = "CEN_2001"
