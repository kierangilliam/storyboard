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


def _create_movie_with_ffmpeg(
    frame_entries: list[FrameEntry],
    output_path: Path,
    resolution: str,
    config: CompositeMovieConfig,
) -> None:
    """Create movie using ffmpeg concat demuxer and filter_complex for audio."""
    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path: Path = Path(tmpdir)

        # Create individual video-only segments for each frame
        video_segment_files: list[Path] = []

        for i, entry in enumerate(frame_entries):
            # Verify image exists
            if not entry.image_path.exists():
                raise FileNotFoundError(f"Image not found: {entry.image_path}")

            segment_path: Path = tmpdir_path / f"video_segment_{i:04d}.mp4"

            # Create video-only segment from image
            _create_video_only_segment(
                image_path=entry.image_path,
                duration=entry.duration,
                output_path=segment_path,
                resolution=resolution,
                config=config,
            )

            video_segment_files.append(segment_path)

        # Concatenate video segments
        video_only_path: Path = tmpdir_path / "video_only.mp4"
        _concatenate_segments(video_segment_files, video_only_path)

        # Create complete audio track
        audio_path: Path = tmpdir_path / "audio.aac"
        _create_audio_track(frame_entries, audio_path, config)

        # Mux video and audio together
        _mux_video_and_audio(video_only_path, audio_path, output_path)


def _create_video_only_segment(
    image_path: Path,
    duration: float,
    output_path: Path,
    resolution: str,
    config: CompositeMovieConfig,
) -> None:
    """Create a video-only segment from an image."""
    # Parse resolution
    width, height = map(int, resolution.split("x"))

    # Build ffmpeg command for video only
    cmd: list[str] = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-loop",
        "1",
        "-framerate",
        str(config.fps),
        "-t",
        str(duration),
        "-i",
        str(image_path),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        config.video_codec,
        "-crf",
        str(config.video_quality),
        "-pix_fmt",
        "yuv420p",
        "-an",  # No audio
        str(output_path),
    ]

    # Run ffmpeg
    _safe_subprocess_run(
        cmd, error_context=f"Failed to create video segment for {image_path}"
    )


def _create_audio_track(
    frame_entries: list[FrameEntry], output_path: Path, config: CompositeMovieConfig
) -> None:
    """Create a single continuous audio track from all frames."""
    # Build filter_complex command to concatenate audio with delays
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path: Path = Path(tmpdir)

        # Create individual audio segments
        audio_segments: list[Path] = []

        for i, entry in enumerate(frame_entries):
            segment_path: Path = tmpdir_path / f"audio_{i:04d}.wav"

            if entry.audio_path is not None:
                # Use actual audio file - keep as WAV to avoid AAC padding
                cmd: list[str] = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(entry.audio_path),
                    "-t",
                    str(entry.duration),
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    "48000",
                    str(segment_path),
                ]
            else:
                # Create silent audio segment with the configured duration
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-t",
                    str(entry.duration),
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-c:a",
                    "pcm_s16le",
                    str(segment_path),
                ]

            _safe_subprocess_run(cmd, error_context=f"Failed to create audio segment {i}")
            audio_segments.append(segment_path)

        # Concatenate all audio segments (still WAV)
        wav_output: Path = tmpdir_path / "audio.wav"
        _concatenate_audio_segments(audio_segments, wav_output)

        # Convert final audio to AAC
        _convert_audio_to_aac(wav_output, output_path, config)


def _concatenate_audio_segments(segment_files: list[Path], output_path: Path) -> None:
    """Concatenate audio segments."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file: Path = Path(f.name)
        for segment in segment_files:
            f.write(f"file '{segment.absolute()}'\n")

    try:
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ]

        _safe_subprocess_run(cmd, error_context="Failed to concatenate audio segments")
    finally:
        concat_file.unlink()


def _convert_audio_to_aac(
    input_path: Path, output_path: Path, config: CompositeMovieConfig
) -> None:
    """Convert WAV audio to AAC."""
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:a",
        config.audio_codec,
        "-b:a",
        config.audio_bitrate,
        str(output_path),
    ]

    _safe_subprocess_run(cmd, error_context="Failed to convert audio to AAC")


def _mux_video_and_audio(
    video_path: Path, audio_path: Path, output_path: Path
) -> None:
    """Mux video and audio streams together."""
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        str(output_path),
    ]

    _safe_subprocess_run(cmd, error_context="Failed to mux video and audio")


def _concatenate_segments(segment_files: list[Path], output_path: Path) -> None:
    """Concatenate video segments using ffmpeg concat demuxer."""
    # Create concat list file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file: Path = Path(f.name)
        for segment in segment_files:
            f.write(f"file '{segment.absolute()}'\n")

    try:
        # Concatenate using concat demuxer
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",  # Stream copy - no re-encoding
            str(output_path),
        ]

        _safe_subprocess_run(cmd, error_context="Failed to concatenate video segments")
    finally:
        concat_file.unlink()  # Clean up concat file


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
