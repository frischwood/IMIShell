# IMIShell

A minimal local tool to extract **clean IMIS station timeseries** for a region and time frame.

Draw a polygon on the map, set a buffer and a time frame — IMIShell detects the [IMIS](https://www.slf.ch/en/avalanche-bulletin-and-snow-situation/measured-values/) stations (same selection logic as [A3Dshell](https://github.com/frischwood/A3Dshell)), downloads their data from the SLF DBO database, applies filtering/resampling/gap-filling, and writes SMET timeseries.

Two interchangeable processing engines:

- **meteoio** — `meteoio_timeseries` (MeteoIO alone): download, clean, write. Configured by `input/templates/meteoioConfig.ini`.
- **snowpack** — `snowpack` (built on MeteoIO, as used by A3Dshell): additionally runs the snow model. Configured by `input/templates/spConfig.ini`.

Both engines share the same filters, resampling and generators.

> **Local only**: the DBO database (`pgdata.int.slf.ch`) requires the SLF VPN.

## Prerequisites

**Docker approach (recommended):**
- [Docker Desktop](https://docs.docker.com/desktop/) (macOS/Windows) or [Docker Engine + Compose plugin](https://docs.docker.com/engine/install/) (Linux). No Docker Hub account is needed — the base image is pulled anonymously.
- SLF VPN active on the host (for DBO access).

Everything else (MeteoIO, Snowpack, Python dependencies) is compiled/installed inside the image.

**Native approach:**
- Python ≥ 3.10 with `pip install -r requirements.txt`
- `meteoio_timeseries` and `snowpack` binaries compiled on the host (MeteoIO must be built with `-DPLUGIN_DBO=ON`)
- SLF VPN active

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

## Using a specific MeteoIO/Snowpack version

### Native

Point IMIShell at any binary on your machine. Precedence:

1. **GUI** — "Binaries" expander: set the full path for this run, e.g. `~/src/snowpack/build/bin/snowpack`.
2. **Env vars** — become the GUI defaults:
   ```bash
   METEOIO_BIN=~/src/meteoio/build/bin/meteoio_timeseries \
   SNOWPACK_BIN=~/src/snowpack/build/bin/snowpack \
   streamlit run gui_app.py
   ```
3. Otherwise `meteoio_timeseries` / `snowpack` are taken from `PATH`.

If your build uses shared libraries that are not installed system-wide, make them findable before launching (`DYLD_LIBRARY_PATH` on macOS, `LD_LIBRARY_PATH` on Linux).

### Docker

The container only sees what is inside the image, and host binaries (e.g. macOS builds) cannot run in the Linux container — so a specific version is selected **at image build time**. The Dockerfile accepts a git tag, branch or commit for each model:

```bash
docker compose build --build-arg METEOIO_REF=<tag-or-commit> --build-arg SNOWPACK_REF=<tag-or-commit>
docker compose up
```

(or uncomment the `args:` block in `docker-compose.yml` to make the pin permanent). Empty refs build the latest default branch. `BUILD_INFO.txt` inside the image records the exact commits that were compiled.

Bind-mounting your own binary into the container (`volumes: - /path/to/snowpack:/opt/custom/snowpack:ro`, then select `/opt/custom/snowpack` in the GUI) also works, but only for Linux binaries matching the container architecture that ship their own shared libraries — rebuilding with pinned refs is usually simpler.

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
- Binary paths: see [Using a specific MeteoIO/Snowpack version](#using-a-specific-meteoiosnowpack-version).
