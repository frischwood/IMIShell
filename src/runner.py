"""
Run preparation and execution for IMIShell.

Builds a self-contained run directory (io.ini, per-station .sno files, output
folders) and executes either meteoio_timeseries or snowpack on it. The ini
templating and .sno generation follow A3Dshell's src/preprocessing/snowpack.py.
"""

import configparser
import logging
import pickle
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, List, Optional

import jinja2

from .config import get_meteoio_bin, get_snowpack_bin

logger = logging.getLogger(__name__)

# Sampling rate passed to meteoio_timeseries (-s, minutes)
SAMPLING_RATE_MIN = 60

ENGINE_TEMPLATES = {
    "meteoio": "meteoioConfig.ini",
    "snowpack": "spConfig.ini",
}


def prepare_run(
    run_name: str,
    engine: str,
    stations,
    output_dir: Path,
    template_dir: Path,
) -> Path:
    """
    Create the run directory with io.ini, .sno files and output folders.

    Args:
        run_name: Name of the run (used as directory name and EXPERIMENT)
        engine: "meteoio" or "snowpack"
        stations: GeoDataFrame of selected IMIS stations
        output_dir: Base output directory
        template_dir: Directory containing ini/sno templates

    Returns:
        Path to the run directory
    """
    if engine not in ENGINE_TEMPLATES:
        raise ValueError(f"Unknown engine: {engine}")
    if len(stations) == 0:
        raise ValueError("No stations selected")

    run_dir = Path(output_dir) / run_name
    meteo_dir = run_dir / "meteo"
    sno_dir = run_dir / "snowfiles"
    sno_out_dir = run_dir / "snowfiles_out"

    for directory in [meteo_dir, sno_dir, sno_out_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    _create_sno_files(stations, sno_dir, template_dir, run_name)
    _create_ini_file(run_name, engine, stations, run_dir, template_dir)

    # Keep the selected stations alongside the results for reproducibility
    stations.drop(columns="geometry").to_csv(run_dir / "stations.csv", index=False)

    return run_dir


def _create_ini_file(run_name, engine, stations, run_dir: Path, template_dir: Path) -> None:
    """Create io.ini from the engine's template, with paths relative to run_dir."""
    template_ini = Path(template_dir) / ENGINE_TEMPLATES[engine]
    if not template_ini.exists():
        raise FileNotFoundError(f"Template not found: {template_ini}")

    config = configparser.ConfigParser(delimiters="=")
    config.read(template_ini)

    # The subprocess runs with cwd=run_dir, so all paths are relative to it
    config["Output"]["METEOPATH"] = "./meteo"
    if engine == "snowpack":
        config["Output"]["EXPERIMENT"] = run_name
        config["Input"]["METEOPATH"] = "./meteo"
        config["Input"]["SNOWPATH"] = "./snowfiles"
        config["Output"]["SNOWPATH"] = "./snowfiles_out"

    for i, (_, station) in enumerate(stations.iterrows(), 1):
        config["Input"][f"STATION{i}"] = station["ID"]

    ini_path = run_dir / "io.ini"
    with open(ini_path, 'w') as f:
        config.write(f)

    logger.info(f"Created {ini_path} with {len(stations)} stations")


def _create_sno_files(stations, sno_dir: Path, template_dir: Path, run_name: str) -> None:
    """Create one bare-soil .sno file per station from the jinja2 template."""
    template_sno = Path(template_dir) / "template.sno"
    dict_sno_path = Path(template_dir) / "dictSno.pkl"

    if not (template_sno.exists() and dict_sno_path.exists()):
        raise FileNotFoundError(
            f"Missing .sno template files in {template_dir} "
            f"(template.sno / dictSno.pkl)"
        )

    with open(dict_sno_path, "rb") as f:
        sno_dict = pickle.load(f)

    template_loader = jinja2.FileSystemLoader(template_sno.parent)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(template_sno.name)

    for _, station in stations.iterrows():
        sno_dict.update(
            experiment=run_name,
            station_id=station["ID"],
            station_name=station["ID"],
            latitude=station["LATITUDE"],
            longitude=station["LONGITUDE"],
            altitude=station["ELEVATION"],
        )

        sno_file = sno_dir / f"{station['ID']}.sno"
        sno_file.write_text(template.render(sno_dict))

    logger.info(f"Created {len(stations)} .sno files in {sno_dir}")


def build_command(
    engine: str,
    start_date: datetime,
    end_date: datetime,
    binary: Optional[str] = None,
) -> List[str]:
    """
    Build the engine command line (run with cwd=run_dir).

    Args:
        engine: "meteoio" or "snowpack"
        start_date: Begin of the time frame
        end_date: End of the time frame
        binary: Path to the engine binary; defaults to the
            METEOIO_BIN / SNOWPACK_BIN environment configuration

    Returns:
        Command as list of arguments
    """
    end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S')

    if engine == "meteoio":
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S')
        return [
            binary or get_meteoio_bin(),
            "-c", "io.ini",
            "-b", start_str,
            "-e", end_str,
            "-s", str(SAMPLING_RATE_MIN),
        ]

    # Snowpack needs the first timestep after the .sno profile date (as in A3Dshell)
    start_str = (start_date + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S')
    return [
        binary or get_snowpack_bin(),
        "-c", "io.ini",
        "-b", start_str,
        "-e", end_str,
    ]


def run_streaming(cmd: List[str], run_dir: Path) -> Iterator[str]:
    """
    Execute the command in run_dir, yielding merged stdout/stderr lines.

    The final yielded line is "EXIT_CODE <n>".

    Args:
        cmd: Command as list of arguments
        run_dir: Working directory for the subprocess
    """
    # Record the exact command: io.ini alone doesn't capture the time frame,
    # sampling rate or binary, and reruns must be reproducible
    (Path(run_dir) / "command.txt").write_text(" ".join(cmd) + "\n")

    binary = cmd[0]
    if shutil.which(binary) is None and not Path(binary).exists():
        yield f"ERROR: binary not found: {binary}"
        yield "Set METEOIO_BIN / SNOWPACK_BIN or run inside the Docker image."
        yield "EXIT_CODE 127"
        return

    process = subprocess.Popen(
        cmd,
        cwd=run_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        yield line.rstrip()

    process.wait()
    yield f"EXIT_CODE {process.returncode}"
