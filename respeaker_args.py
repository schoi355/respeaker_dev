import argparse
from pathlib import Path

def wave_file(file_name: str) -> Path:
    """Validator for .wav file"""
    file = Path(file_name)
    if file.suffix != ".wav":
        parser.error("File is not a .wav file")
    return file

def json_file(file_name: str) -> Path:
    """Validator for .json file"""
    file = Path(file_name)
    if file.suffix != ".json":
        parser.error("File is not a .json file")
    return file

parser = argparse.ArgumentParser()


def voice_recorder_args() -> argparse.ArgumentParser:
    """
    Parse arguments to respeaker_local.py
    usage: respeaker_local.py [-h] [-i INDEX] [-d DURATION] [-t TIMESTEP] [-w WAVE] [-j JSON] 
    options:
        -h, --help:                          show this help message and exit
        -i INDEX, --index INDEX:             input device id (default: 1)
        -d DURATION, --duration DURATION:    recording duration (s)
        -t TIMESTEP, --timestep TIMESTEP:    timestep for DOA (s)
        -w WAVE, --wave WAVE:                save voice data into wave format
        -j JSON, --json JSON:                save doa and timestamp into json format
    """

    parser.description = "Parse arguments to respeaker.py"

    parser.add_argument(
        "-i",
        "--index",
        dest="index",
        action="store",
        default=1,
        type=int,
        help="input device id (default: 1)",
    )

    parser.add_argument(
        "-d",
        "--duration",
        dest="duration",
        action="store",
        type=int,
        help="recording duration (s)",
    )

    parser.add_argument(
        "-t",
        "--timestep",
        dest="timestep",
        action="store",
        type=float,
        help="timestep for DOA (s)",
    )

    parser.add_argument(
        "-w",
        "--wave",
        dest="wave",
        action="store",
        type=lambda s: wave_file(s),
        help="save voice data into wave format",
    )
    
    parser.add_argument(
        "-j",
        "--json",
        dest="json",
        action="store",
        type=lambda s: json_file(s),
        help="save doa and timestamp into json format",
    )


    return parser