# IMIShell

A minimal local tool to extract **clean IMIS station timeseries** for a region and time frame.

Draw a polygon on the map, set a buffer and a time frame — IMIShell detects the [IMIS](https://www.slf.ch/en/avalanche-bulletin-and-snow-situation/measured-values/) stations (same selection logic as [A3Dshell](https://github.com/frischwood/A3Dshell)), downloads their data from the SLF DBO database, applies filtering/resampling/gap-filling, and writes SMET timeseries.

Two interchangeable processing engines:

- **meteoio** — `meteoio_timeseries` (MeteoIO alone): download, clean, write. Configured by `input/templates/meteoioConfig.ini`.
- **snowpack** — `snowpack` (built on MeteoIO, as used by A3Dshell): additionally runs the snow model. Configured by `input/templates/spConfig.ini`.

Both engines share the same filters, resampling and generators.

> **Local only**: the DBO database (`pgdata.int.slf.ch`) requires the SLF VPN.

## Run with Docker (recommended)

```bash
docker-compose up --build
# open http://localhost:8502
```

The image compiles MeteoIO (with the DBO plugin) and Snowpack from source.

## Run natively

Needs `meteoio_timeseries` / `snowpack` binaries on the host (paths via `METEOIO_BIN` / `SNOWPACK_BIN` env vars):

```bash
pip install -r requirements.txt
streamlit run gui_app.py
```

Without binaries, the GUI still works for drawing and station detection.

## Output

Each run writes a self-contained folder:

```
output/<run_name>/
├── io.ini            # generated engine configuration (reproducible)
├── stations.csv      # selected IMIS stations
├── snowfiles/        # one bare-soil .sno per station
├── snowfiles_out/    # snowpack engine only: final snow profiles
└── meteo/            # ← the clean SMET timeseries
```

## Configuration

- `input/templates/meteoioConfig.ini` / `spConfig.ini` — processing configuration (filters, resampling, generators, DBO URL). Station IDs, paths and the time frame are injected at run time.
- `input/imis/` — IMIS station metadata (copied from A3Dshell).
- Env vars: `METEOIO_BIN`, `SNOWPACK_BIN`, `IMIS_OUTPUT_DIR`, `IMIS_TEMPLATE_DIR`, `IMIS_META_DIR`, `IMIS_CONFIG_DIR`.
- The binary paths can also be overridden per run in the GUI ("Binaries" expander) — e.g. to point at a specific locally compiled MeteoIO or Snowpack version.
