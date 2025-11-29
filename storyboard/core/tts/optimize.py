"""TTS optimization utilities for audio compression."""

import subprocess
from pathlib import Path


def optimize_audio(
    input_path: str | Path,
    output_path: str | Path | None = None,
    quality: int = 8,
) -> Path:
    """Optimize audio file using ffmpeg with opus codec.

    Quality range: 0-10 where 0 is lowest quality/size and 10 is highest.
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input audio not found: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Input path is not a file: {input_file}")

    if output_path is None:
        output_file = input_file.with_suffix(".opus")
    else:
        output_file = Path(output_path)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Use ffmpeg to convert to opus format
    # VBR quality scale: 0 (lowest) to 10 (highest)
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(input_file),
            "-c:a",
            "libopus",
            "-vbr",
            "on",
            "-compression_level",
            str(quality),
            "-y",  # Overwrite output file if exists
            str(output_file),
        ],
        check=True,
        capture_output=True,
    )

    return output_file
