"""
IMIS (Intercantonal Measurement and Information System) station management.

Handles selection of meteorological stations within a buffered ROI.
Copied from A3Dshell (src/data/imis.py) and trimmed to the buffer-selection use case.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    logger.warning("geopandas not available")

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False


class IMISManager:
    """Manages IMIS meteorological station selection."""

    def __init__(self, imis_data_dir: Path):
        """
        Initialize IMIS manager.

        Args:
            imis_data_dir: Directory containing IMIS metadata files
        """
        if not GEOPANDAS_AVAILABLE:
            raise ImportError("geopandas required for IMIS management")

        self.imis_dir = Path(imis_data_dir)

        # IMIS metadata file paths
        self.meta_10y = self.imis_dir / "imisMeta_10y.txt"
        self.meta_daily = self.imis_dir / "imisMeta_daily.txt"
        self.meta_shp = self.imis_dir / "imisMeta_merged.shp"

        # Load metadata
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> pd.DataFrame:
        """
        Load IMIS station metadata.

        Returns:
            DataFrame with station metadata
        """
        logger.info("Loading IMIS metadata")

        if self.meta_10y.exists() and self.meta_daily.exists():
            logger.info(f"   Loading from {self.meta_10y.name} and {self.meta_daily.name}")

            df_10y = pd.read_table(
                self.meta_10y,
                sep=" ",
                skipinitialspace=True,
                comment="#",
                header=0,
                index_col="ID"
            )

            df_daily = pd.read_table(
                self.meta_daily,
                sep=" ",
                skipinitialspace=True,
                comment="#",
                header=0,
                index_col="ID"
            )

            # Combine (10y takes precedence)
            df_meta = df_10y.combine_first(df_daily)

            if PYPROJ_AVAILABLE:
                df_meta["E_N_2056"] = df_meta.apply(
                    lambda row: self._transform_4326_to_2056(
                        row["LATITUDE"],
                        row["LONGITUDE"]
                    ),
                    axis=1
                )
            else:
                logger.warning("pyproj not available, skipping coordinate transformation")

            logger.info(f"   Loaded {len(df_meta)} stations")
            return df_meta

        else:
            logger.warning("IMIS metadata text files not found")
            return pd.DataFrame()

    def _transform_4326_to_2056(self, lat: float, lon: float) -> tuple:
        """
        Transform WGS84 to CH1903+.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Tuple of (easting, northing)
        """
        if not PYPROJ_AVAILABLE:
            # Rough approximation
            e = (lon - 7.5) * 111000 + 2600000
            n = (lat - 46.5) * 111000 + 1200000
            return (e, n)

        transformer = Transformer.from_crs(crs_from='epsg:4326', crs_to='epsg:2056')
        n, e = transformer.transform(lat, lon)
        return (e, n)

    def get_stations_in_buffer(
        self,
        roi,
        buffer_size: float
    ) -> "gpd.GeoDataFrame":
        """
        Get IMIS stations within buffered ROI.

        Args:
            roi: ROI object with geometry
            buffer_size: Buffer distance in meters

        Returns:
            GeoDataFrame of qualified stations
        """
        logger.info("Selecting IMIS stations in buffered ROI")
        logger.info(f"   Buffer size: {buffer_size}m")

        # Load shapefile if available
        if self.meta_shp.exists():
            logger.info(f"   Loading from {self.meta_shp.name}")
            gdf_imis = gpd.read_file(self.meta_shp)

            if gdf_imis.crs is None:
                gdf_imis = gdf_imis.set_crs("EPSG:4326")

            gdf_imis = gdf_imis.to_crs("EPSG:2056")

        else:
            logger.info("   Creating GeoDataFrame from metadata")

            if "E_N_2056" not in self.metadata.columns:
                raise ValueError("IMIS metadata missing coordinates")

            coords = list(self.metadata["E_N_2056"].values)
            eastings = [c[0] for c in coords]
            northings = [c[1] for c in coords]

            from shapely.geometry import Point
            geometry = [Point(e, n) for e, n in zip(eastings, northings)]

            gdf_imis = gpd.GeoDataFrame(
                self.metadata.reset_index(),
                geometry=geometry,
                crs="EPSG:2056"
            )

        # Buffer ROI and select stations within
        buffered_roi = roi.buffer(buffer_size)
        mask = buffered_roi.geometry.iloc[0].contains(gdf_imis.geometry)
        selected = gdf_imis[mask]

        logger.info(f"   Selected {len(selected)} stations")

        return selected
