"""
Configuration for IMIShell.

Binary and directory paths are configurable via environment variables so the
same code runs natively (binaries on the host) or inside the Docker image.
"""

import os
from pathlib import Path

# Processing binaries
METEOIO_BIN = os.environ.get('METEOIO_BIN', 'meteoio_timeseries')
SNOWPACK_BIN = os.environ.get('SNOWPACK_BIN', 'snowpack')

# Directory paths
OUTPUT_DIR = Path(os.environ.get('IMIS_OUTPUT_DIR', './output'))
TEMPLATE_DIR = Path(os.environ.get('IMIS_TEMPLATE_DIR', './input/templates'))
IMIS_DIR = Path(os.environ.get('IMIS_META_DIR', './input/imis'))
CONFIG_DIR = Path(os.environ.get('IMIS_CONFIG_DIR', './config'))


def get_meteoio_bin() -> str:
    return METEOIO_BIN


def get_snowpack_bin() -> str:
    return SNOWPACK_BIN


def get_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def get_template_dir() -> Path:
    return TEMPLATE_DIR


def get_imis_dir() -> Path:
    return IMIS_DIR


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR
