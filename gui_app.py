"""
IMIShell - Simple GUI
=====================

Draw a region on the map, set a buffer and a time frame, and extract clean
IMIS station timeseries (SMET) through MeteoIO or Snowpack (both via the SLF
DBO database, VPN required).

Run with: streamlit run gui_app.py
"""

import json
from datetime import datetime
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.config import get_config_dir, get_imis_dir, get_output_dir, get_template_dir
from src.imis import IMISManager
from src.map_utils import create_roi_map, save_drawn_roi
from src.roi import ROI
from src import runner

st.set_page_config(page_title="IMIShell", layout="wide")

st.title("IMIShell")
st.markdown("Extract clean IMIS timeseries: draw a region, set buffer and time frame, run.")


@st.cache_resource
def load_imis_manager():
    return IMISManager(get_imis_dir())


imis_mgr = load_imis_manager()
roi_shapefile = get_config_dir() / "shapefiles" / "roi_drawn.shp"

# ------------------------------------------------------------------
# Run parameters
# ------------------------------------------------------------------
today = datetime.now()
season_year = today.year - 1 if today.month < 10 else today.year

col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
run_name = col1.text_input("Run name", value=f"imis_{today:%Y%m%d}")
start_date = col2.date_input("Start date", value=datetime(season_year, 10, 1))
end_date = col3.date_input("End date", value=today)
buffer_size = col4.number_input(
    "Buffer (m)", value=10000, min_value=0, max_value=100000, step=1000,
    help="Stations within this distance around the drawn region are selected."
)
engine = col5.radio("Engine", ["meteoio", "snowpack"],
                    help="meteoio_timeseries downloads/cleans/writes the timeseries; "
                         "snowpack additionally runs the snow model.")

# ------------------------------------------------------------------
# Map with ROI drawing and station preview
# ------------------------------------------------------------------
map_col, stations_col = st.columns([3, 2])

stations = None
roi = None
if st.session_state.get("roi_geojson") and roi_shapefile.exists():
    roi = ROI(roi_shapefile)
    stations = imis_mgr.get_stations_in_buffer(roi, buffer_size)

m = create_roi_map()
if roi is not None:
    # Show saved ROI, buffered outline and detected stations
    folium.GeoJson(
        roi.geometry_4326.to_json(),
        style_function=lambda _: {"color": "blue", "fillOpacity": 0.1},
    ).add_to(m)
    folium.GeoJson(
        roi.buffer(buffer_size).to_crs("EPSG:4326").to_json(),
        style_function=lambda _: {"color": "orange", "fill": False, "dashArray": "5"},
    ).add_to(m)
    for _, station in stations.iterrows():
        folium.Marker(
            [station["LATITUDE"], station["LONGITUDE"]],
            tooltip=f"{station['ID']} ({station['ELEVATION']:.0f} m)",
            icon=folium.Icon(color="red", icon="cloud"),
        ).add_to(m)

with map_col:
    map_output = st_folium(m, width=700, height=550, key="roi_map")

# Persist a newly drawn polygon and rerun so overlays appear
if map_output and map_output.get("last_active_drawing"):
    drawn = map_output["last_active_drawing"]
    geom_str = json.dumps(drawn["geometry"], sort_keys=True)
    if st.session_state.get("roi_geojson") != geom_str:
        success, message = save_drawn_roi(drawn, str(roi_shapefile))
        if success:
            st.session_state["roi_geojson"] = geom_str
            st.rerun()
        else:
            st.error(message)

with stations_col:
    st.subheader("Detected IMIS stations")
    if stations is None:
        st.info("Draw a rectangle or polygon on the map to detect stations.")
    elif len(stations) == 0:
        st.warning("No IMIS stations in the buffered region. "
                   "Increase the buffer or move the region.")
    else:
        st.markdown(f"**{len(stations)} stations** within {buffer_size / 1000:.0f} km buffer")
        st.dataframe(
            stations[["ID", "ELEVATION", "LATITUDE", "LONGITUDE"]]
            .sort_values("ID")
            .reset_index(drop=True),
            height=380,
        )

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
st.divider()

can_run = stations is not None and len(stations) > 0 and run_name and " " not in run_name
if " " in (run_name or ""):
    st.error("Run name cannot contain whitespaces")

if st.button("▶️ Start", type="primary", disabled=not can_run):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())

    if start_dt >= end_dt:
        st.error("Start date must be before end date")
        st.stop()

    run_dir = runner.prepare_run(
        run_name=run_name,
        engine=engine,
        stations=stations,
        output_dir=get_output_dir(),
        template_dir=get_template_dir(),
    )
    cmd = runner.build_command(engine, start_dt, end_dt)

    st.info(f"Running in `{run_dir}`")
    st.code(" ".join(cmd), language="bash")

    log_container = st.container(height=400)
    log_placeholder = log_container.empty()
    full_log = []
    exit_code = None

    for line in runner.run_streaming(cmd, run_dir):
        if line.startswith("EXIT_CODE "):
            exit_code = int(line.split()[1])
            continue
        full_log.append(line)
        log_placeholder.code("\n".join(full_log), language="text")

    if exit_code == 0:
        smet_files = sorted((run_dir / "meteo").glob("*.smet"))
        st.success(f"✅ Done — {len(smet_files)} SMET files in `{run_dir / 'meteo'}`")
        for f in smet_files:
            st.markdown(f"- `{f.name}`")
    else:
        st.error(f"❌ Run failed with exit code {exit_code}. See log above.")
