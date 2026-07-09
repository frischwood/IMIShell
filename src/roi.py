"""
Region of Interest (ROI) handling for IMIShell.

Trimmed from A3Dshell (src/geometry/roi.py): the ROI always comes from a
shapefile written from the polygon drawn in the GUI.
"""

import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    gpd = None
    logger.warning("geopandas not available, shapefile support will be limited")


class ROI:
    """Region of Interest loaded from a shapefile."""

    def __init__(self, shapefile_path: Path):
        """
        Initialize ROI from a shapefile.

        Args:
            shapefile_path: Path to the ROI shapefile
        """
        if not GEOPANDAS_AVAILABLE:
            raise ImportError(
                "geopandas is required for ROI handling. "
                "Install with: pip install geopandas"
            )

        self.shapefile_path = Path(shapefile_path)
        if not self.shapefile_path.exists():
            raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

        self.geometry_2056 = self._load_geometry()
        self.geometry_4326 = self.geometry_2056.to_crs("EPSG:4326")

    def _load_geometry(self) -> "gpd.GeoDataFrame":
        """
        Load ROI geometry.

        Returns:
            GeoDataFrame with ROI geometry in EPSG:2056
        """
        logger.info(f"Loading ROI from shapefile: {self.shapefile_path}")
        gdf = gpd.read_file(self.shapefile_path)

        # Clean non-geometric attributes
        gdf = gdf[~gdf.geometry.isna()]

        if gdf.crs.to_string() != "EPSG:2056":
            logger.info(f"Converting shapefile CRS from {gdf.crs} to EPSG:2056")
            gdf = gdf.to_crs("EPSG:2056")

        return gdf

    def buffer(self, distance: float) -> "gpd.GeoDataFrame":
        """
        Create buffered ROI.

        Args:
            distance: Buffer distance in meters

        Returns:
            Buffered GeoDataFrame in EPSG:2056
        """
        buffered = self.geometry_2056.buffer(distance=distance)
        return gpd.GeoDataFrame(geometry=buffered, crs="EPSG:2056")

    def get_bbox_2056(self) -> Tuple[float, float, float, float]:
        """Bounding box (minx, miny, maxx, maxy) in EPSG:2056."""
        return tuple(self.geometry_2056.total_bounds)

    def __str__(self) -> str:
        bbox = self.get_bbox_2056()
        area_km2 = self.geometry_2056.geometry.area.sum() / 1_000_000
        return (
            f"ROI(\n"
            f"  Source: {self.shapefile_path}\n"
            f"  BBox (2056): {bbox}\n"
            f"  Area: {area_km2:.2f} km²\n"
            f")"
        )
