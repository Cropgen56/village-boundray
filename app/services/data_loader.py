"""
data_loader.py
--------------
Downloads the Maharashtra GeoJSON files from Cloud Storage and merges them
once at application startup (never per request).
Pre-computes dissolved taluka and district geometries, keyed for O(1)
lookup, so spatial queries at those levels are fast at request time.
"""

import logging
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.strtree import STRtree

from app.core.config import (
    GCS_BUCKET_NAME,
    GCS_GEOJSON_OBJECTS,
    COL_DISTRICT,
    COL_TALUKA,
    COL_NAME,
    COL_STATE,
    COL_CEN,
)
from app.services.gcs import download_to_file

logger = logging.getLogger(__name__)

# Only these attribute columns are ever used — skip the rest when reading
_COLUMNS = [COL_NAME, COL_TALUKA, COL_DISTRICT, COL_STATE, COL_CEN]


class GeoDataStore:
    """
    Singleton-style container that holds:
      - village_geoms : array of village geometries (indexed by village_tree)
      - village_attrs : per-village tuple (name, taluka, district, state, census_code)
      - village_tree  : STRtree spatial index over village_geoms
      - taluka_geoms  : {(district, taluka): geometry}
      - district_geoms: {district: geometry}
    """

    def __init__(self) -> None:
        self.village_geoms: np.ndarray | None = None
        self.village_attrs: list[tuple] = []
        self.village_tree: STRtree | None = None
        self.taluka_geoms: dict[tuple[str, str], object] = {}
        self.district_geoms: dict[str, object] = {}
        self.source_counts: dict[str, int] = {}  # gs:// URI -> feature count
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load GeoJSON files, merge them, and pre-compute derived layers."""
        if self._loaded:
            logger.info("GeoDataStore already loaded – skipping.")
            return

        logger.info("Loading GeoJSON files from Cloud Storage …")
        frames = self._read_files()

        logger.info("Merging %d file(s) …", len(frames))
        gdf = pd.concat(frames, ignore_index=True)

        # Ensure geometry CRS is WGS84 (EPSG:4326)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        else:
            gdf = gdf.to_crs("EPSG:4326")

        # Plain Python values (None instead of NaN) so they serialize cleanly
        attrs = gdf[_COLUMNS].astype(object).where(gdf[_COLUMNS].notna(), None)
        attrs[COL_CEN] = attrs[COL_CEN].map(lambda v: None if v is None else str(v))

        self.village_geoms = gdf.geometry.values.to_numpy()
        self.village_attrs = list(attrs.itertuples(index=False, name=None))
        logger.info("Villages ready: %d features", len(self.village_attrs))

        logger.info("Building STRtree spatial index …")
        self.village_tree = STRtree(self.village_geoms)

        logger.info("Dissolving taluka boundaries …")
        talukas = gdf.dissolve(by=[COL_DISTRICT, COL_TALUKA])
        self.taluka_geoms = dict(zip(talukas.index, talukas.geometry.values))

        logger.info("Dissolving district boundaries …")
        districts = gdf.dissolve(by=COL_DISTRICT)
        self.district_geoms = dict(zip(districts.index, districts.geometry.values))

        self._loaded = True
        logger.info(
            "GeoDataStore fully loaded (%d talukas, %d districts).",
            len(self.taluka_geoms),
            len(self.district_geoms),
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_files(self) -> list[gpd.GeoDataFrame]:
        """
        Download each GeoJSON object to a temp file and parse it. Files are
        handled one at a time and deleted right after parsing, so only one
        raw file sits on disk at once (Cloud Run's /tmp counts against memory).
        """
        missing = [
            name
            for name, value in {"GCS_BUCKET_NAME": GCS_BUCKET_NAME, **GCS_GEOJSON_OBJECTS}.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "See .env.example."
            )

        frames = []
        with tempfile.TemporaryDirectory(prefix="boundary-data-") as tmp:
            for object_path in GCS_GEOJSON_OBJECTS.values():
                uri = f"gs://{GCS_BUCKET_NAME}/{object_path}"
                local = Path(tmp) / Path(object_path).name
                download_to_file(GCS_BUCKET_NAME, object_path, local)

                gdf = gpd.read_file(local, columns=_COLUMNS)
                local.unlink()

                absent = set(_COLUMNS) - set(gdf.columns)
                if gdf.empty or absent:
                    raise RuntimeError(
                        f"{uri} is not a usable boundary dataset "
                        f"(features={len(gdf)}, missing columns={sorted(absent)})."
                    )

                logger.info("  Parsed %s: %d features", uri, len(gdf))
                self.source_counts[uri] = len(gdf)
                frames.append(gdf)
        return frames


# Module-level singleton — imported by other modules
geo_store = GeoDataStore()
