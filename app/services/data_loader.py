"""
data_loader.py
--------------
Loads and merges the Maharashtra GeoJSON files at application startup.
Pre-computes dissolved taluka and district GeoDataFrames so that
spatial queries at those levels are fast at request time.
"""

import logging
from pathlib import Path

import geopandas as gpd
from shapely.strtree import STRtree

from app.core.config import (
    GEOJSON_FILES,
    COL_DISTRICT,
    COL_TALUKA,
    COL_NAME,
    COL_STATE,
    COL_CEN,
)

logger = logging.getLogger(__name__)


class GeoDataStore:
    """
    Singleton-style container that holds:
      - village_gdf  : full village-level GeoDataFrame
      - taluka_gdf   : dissolved taluka-level GeoDataFrame
      - district_gdf : dissolved district-level GeoDataFrame
      - village_tree : STRtree spatial index over village geometries
    """

    def __init__(self) -> None:
        self.village_gdf: gpd.GeoDataFrame | None = None
        self.taluka_gdf: gpd.GeoDataFrame | None = None
        self.district_gdf: gpd.GeoDataFrame | None = None
        self.village_tree: STRtree | None = None
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load GeoJSON files, merge them, and pre-compute derived layers."""
        if self._loaded:
            logger.info("GeoDataStore already loaded – skipping.")
            return

        logger.info("Loading GeoJSON files …")
        frames = self._read_files(GEOJSON_FILES)

        logger.info("Merging %d file(s) …", len(frames))
        village_gdf = gpd.pd.concat(frames, ignore_index=True)

        # Ensure geometry CRS is WGS84 (EPSG:4326)
        if village_gdf.crs is None:
            village_gdf = village_gdf.set_crs("EPSG:4326")
        else:
            village_gdf = village_gdf.to_crs("EPSG:4326")

        self.village_gdf = village_gdf
        logger.info("Village GDF ready: %d features", len(self.village_gdf))

        # Build spatial index
        logger.info("Building STRtree spatial index …")
        self.village_tree = STRtree(self.village_gdf.geometry.values)

        # Pre-compute taluka & district boundaries
        logger.info("Dissolving taluka boundaries …")
        self.taluka_gdf = self._dissolve(
            self.village_gdf,
            by=[COL_DISTRICT, COL_TALUKA],
            agg={COL_STATE: "first"},
        )

        logger.info("Dissolving district boundaries …")
        self.district_gdf = self._dissolve(
            self.village_gdf,
            by=[COL_DISTRICT],
            agg={COL_STATE: "first"},
        )

        self._loaded = True
        logger.info("GeoDataStore fully loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_files(paths: list[Path]) -> list[gpd.GeoDataFrame]:
        frames = []
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"GeoJSON file not found: {path}")
            logger.info("  Reading %s …", path.name)
            gdf = gpd.read_file(str(path))
            frames.append(gdf)
        return frames

    @staticmethod
    def _dissolve(
        gdf: gpd.GeoDataFrame,
        by: list[str],
        agg: dict,
    ) -> gpd.GeoDataFrame:
        """Dissolve geometries by grouping columns and aggregate extra fields."""
        dissolved = gdf.dissolve(by=by, aggfunc=agg).reset_index()
        return dissolved


# Module-level singleton — imported by other modules
geo_store = GeoDataStore()
