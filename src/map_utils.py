"""
Folium map helpers for IMIShell.

Lifted from A3Dshell's gui_app.py (create_roi_map / save_drawn_roi).
"""

import logging
from pathlib import Path

import folium
from folium.plugins import Draw
import geopandas as gpd
from shapely.geometry import shape

logger = logging.getLogger(__name__)


def create_roi_map(center_lat=46.8, center_lon=8.2, zoom=8):
    """
    Create an interactive map with Swisstopo layers for drawing ROI polygons.

    Args:
        center_lat: Latitude for map center (WGS84)
        center_lon: Longitude for map center (WGS84)
        zoom: Initial zoom level

    Returns:
        folium.Map object with drawing tools
    """
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None
    )

    # Swisstopo base layer (Swiss National Map)
    folium.raster_layers.WmsTileLayer(
        url='https://wms.geo.admin.ch/',
        layers='ch.swisstopo.pixelkarte-farbe',
        fmt='image/png',
        transparent=False,
        name='Swisstopo Map',
        overlay=False,
        control=True,
        attr='© swisstopo'
    ).add_to(m)

    # Drawing tools (rectangle and polygon)
    draw = Draw(
        export=False,
        draw_options={
            'polyline': False,
            'rectangle': True,
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'polygon': True
        },
        edit_options={
            'edit': True,
            'remove': True
        }
    )
    draw.add_to(m)

    return m


def save_drawn_roi(geojson_data, output_path):
    """
    Save drawn polygon as shapefile in Swiss coordinate system (EPSG:2056).

    Args:
        geojson_data: GeoJSON dict from drawn polygon (WGS84)
        output_path: Path to save shapefile

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        geom = shape(geojson_data['geometry'])

        gdf = gpd.GeoDataFrame([{'id': 1}], geometry=[geom], crs='EPSG:4326')
        gdf = gdf.to_crs('EPSG:2056')

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        gdf.to_file(output_path)

        return True, f"ROI saved to {output_path}"

    except Exception as e:
        return False, f"Error saving ROI: {str(e)}"
