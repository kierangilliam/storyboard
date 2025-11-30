"""Movie creation from generated scenes."""

import json
import subprocess
import tempfile
from pathlib import Path

from storyboard.core.shapes import CompositeMovieConfig


class FrameEntry:
    """Represents a single frame with its assets and duration."""

    def __init__(self, image_path: Path, audio_path: Path | None, duration: float):
        self.image_path: Path = image_path
        self.audio_path: Path | None = audio_path
        self.duration: float = duration


def create_movie(
    scene_folder: Path,
    output_path: Path,
    config: CompositeMovieConfig | None = None,
    resolution_override: str | None = None,
) -> None:
    """Create a movie from all scenes in the scene folder."""
    if config is None:
        config = CompositeMovieConfig()

    resolution: str = resolution_override or config.resolution

    # Load root metadata
    with open(scene_folder / "metadata.json") as f:
        root_metadata: dict = json.load(f)

    scenes: list[dict] = root_metadata["scenes"]
    if not scenes:
        raise ValueError("No scenes found in metadata.json")

    # Build list of frame assets with durations
    frame_entries: list[FrameEntry] = []

    for scene in scenes:
        scene_metadata_path: Path = scene_folder / scene["metadata_path"]
        with open(scene_metadata_path) as f:
            scene_metadata: dict = json.load(f)

        for frame in scene_metadata["frames"]:
            # Resolve paths relative to scene_folder parent
            image_path: Path = scene_folder.parent / frame["assets"]["image"]["path"]
            audio_asset = frame["assets"]["audio"]

            if audio_asset is not None:
                audio_path: Path = scene_folder.parent / audio_asset["path"]
                # Get audio duration using ffprobe
                duration: float = _get_audio_duration(audio_path)
            else:
                audio_path = None
                duration = config.no_audio_length

            frame_entries.append(
                FrameEntry(
                    image_path=image_path,
                    audio_path=audio_path,
                    duration=duration,
                )
            )

    # Create movie using ffmpeg
    _create_movie_with_ffmpeg(
        frame_entries=frame_entries,
        output_path=output_path,
        resolution=resolution,
        config=config,
    )


def _get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    result: subprocess.CompletedProcess = _safe_subprocess_run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        error_context=f"Failed to get audio duration for {audio_path}",
    )

    return float(result.stdout.strip())


def _create_segment_with_audio(
    entry: FrameEntry,
    output_path: Path,
    resolution: str,
    config: CompositeMovieConfig,
) -> None:
    """Create a complete segment with both video and audio tracks."""
    # Parse resolution
    width, height = map(int, resolution.split("x"))

    # Build ffmpeg command based on whether frame has audio
    if entry.audio_path is not None:
        # Frame has audio - create video from image and use actual audio
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", str(config.fps),
            "-i", str(entry.image_path),
            "-i", str(entry.audio_path),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", config.video_codec,
            "-crf", str(config.video_quality),
            "-pix_fmt", "yuv420p",
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            "-shortest",  # Stop when shortest input ends (audio)
            str(output_path),
        ]
    else:
        # Frame has no audio - create video and add silent audio
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", str(config.fps),
            "-t", str(entry.duration),
            "-i", str(entry.image_path),
            "-f", "lavfi",
            "-t", str(entry.duration),
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", config.video_codec,
            "-crf", str(config.video_quality),
            "-pix_fmt", "yuv420p",
            "-c:a", config.audio_codec,
            "-b:a", config.audio_bitrate,
            "-shortest",
            str(output_path),
        ]

    _safe_subprocess_run(
        cmd, error_context=f"Failed to create segment for {entry.image_path}"
    )


def _create_movie_with_ffmpeg(
    frame_entries: list[FrameEntry],
    output_path: Path,
    resolution: str,
    config: CompositeMovieConfig,
) -> None:
    """Create movie by building complete video+audio segments then concatenating."""
    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path: Path = Path(tmpdir)

        # Create individual segments with both video and audio
        segment_files: list[Path] = []

        for i, entry in enumerate(frame_entries):
            # Verify image exists
            if not entry.image_path.exists():
                raise FileNotFoundError(f"Image not found: {entry.image_path}")

            segment_path: Path = tmpdir_path / f"segment_{i:04d}.mp4"

            # Create segment with both video and audio
            _create_segment_with_audio(
                entry=entry,
                output_path=segment_path,
                resolution=resolution,
                config=config,
            )

            segment_files.append(segment_path)

        # Concatenate all segments
        _concatenate_segments(segment_files, output_path, config)


def _concatenate_segments(
    segment_files: list[Path], output_path: Path, config: CompositeMovieConfig
) -> None:
    """Concatenate segments using concat filter for proper audio/video sync."""
    # Build filter_complex using concat filter (not concat demuxer)
    # This ensures proper PTS handling and prevents audio drift
    n: int = len(segment_files)

    # Build input arguments
    input_args: list[str] = []
    for segment in segment_files:
        input_args.extend(["-i", str(segment)])

    # Build concat filter string: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[outv][outa]
    filter_parts: list[str] = []
    for i in range(n):
        filter_parts.append(f"[{i}:v][{i}:a]")
    filter_string: str = f"{''.join(filter_parts)}concat=n={n}:v=1:a=1[outv][outa]"

    # Concatenate using concat filter
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        *input_args,
        "-filter_complex",
        filter_string,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        config.video_codec,
        "-crf",
        str(config.video_quality),
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        config.audio_codec,
        "-b:a",
        config.audio_bitrate,
        str(output_path),
    ]

    _safe_subprocess_run(cmd, error_context="Failed to concatenate video segments")


def _safe_subprocess_run(cmd: list[str], error_context: str) -> subprocess.CompletedProcess:
    """Run subprocess with better error messages."""
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            f"{error_context}: ffmpeg/ffprobe not found. Install ffmpeg first."
        )
    except subprocess.CalledProcessError as e:
        stderr: str = e.stderr if e.stderr else ""
        raise RuntimeError(f"{error_context}: {stderr}")
