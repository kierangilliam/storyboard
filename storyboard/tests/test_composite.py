import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from storyboard.cli.composite.movie import (
    FrameEntry,
    _get_audio_duration,
    create_movie,
)
from storyboard.core.shapes import CompositeMovieConfig


@pytest.fixture
def mock_scene_folder(tmp_path: Path) -> Path:
    """Create mock scene folder with metadata."""
    # Create root metadata
    root_metadata: dict = {
        "scenes": [
            {
                "scene_id": "scene1",
                "scene_name": "Scene 1",
                "frame_count": 2,
                "metadata_path": "scene1/metadata.json",
            }
        ],
        "generation_metadata": {},
    }

    scene_folder: Path = tmp_path / "output"
    scene_folder.mkdir()

    with open(scene_folder / "metadata.json", "w") as f:
        json.dump(root_metadata, f)

    # Create scene metadata
    scene_dir: Path = scene_folder / "scene1"
    scene_dir.mkdir()

    scene_metadata: dict = {
        "scene_id": "scene1",
        "scene_name": "Scene 1",
        "frames": [
            {
                "frame_id": "frame1",
                "assets": {
                    "image": {"path": "output/scene1/frame1/image.webp"},
                    "audio": {"path": "output/scene1/frame1/tts.wav"},
                },
            },
            {
                "frame_id": "frame2",
                "assets": {
                    "image": {"path": "output/scene1/frame2/image.webp"},
                    "audio": None,
                },
            },
        ],
    }

    with open(scene_dir / "metadata.json", "w") as f:
        json.dump(scene_metadata, f)

    return scene_folder


def test_get_audio_duration_calls_ffprobe_correctly(tmp_path: Path):
    """Test that audio duration extraction uses correct ffprobe command."""
    audio_file: Path = tmp_path / "test.wav"
    audio_file.touch()

    with patch("storyboard.cli.composite.movie._safe_subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="5.5\n")

        duration: float = _get_audio_duration(audio_file)

        assert duration == 5.5
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffprobe" in call_args
        assert str(audio_file) in call_args


def test_get_audio_duration_raises_on_missing_file(tmp_path: Path):
    """Test that missing audio file raises FileNotFoundError."""
    audio_file: Path = tmp_path / "nonexistent.wav"

    with pytest.raises(FileNotFoundError):
        _get_audio_duration(audio_file)


def test_frame_entry_stores_attributes_correctly():
    """Test that FrameEntry class stores attributes correctly."""
    image_path: Path = Path("/fake/image.webp")
    audio_path: Path = Path("/fake/audio.wav")
    duration: float = 7.0

    entry: FrameEntry = FrameEntry(
        image_path=image_path, audio_path=audio_path, duration=duration
    )

    assert entry.image_path == image_path
    assert entry.audio_path == audio_path
    assert entry.duration == duration


def test_frame_entry_handles_no_audio():
    """Test that FrameEntry works with no audio."""
    image_path: Path = Path("/fake/image.webp")
    duration: float = 5.0

    entry: FrameEntry = FrameEntry(
        image_path=image_path, audio_path=None, duration=duration
    )

    assert entry.image_path == image_path
    assert entry.audio_path is None
    assert entry.duration == duration


def test_create_movie_raises_on_missing_metadata(tmp_path: Path):
    """Test that missing metadata.json raises appropriate error."""
    scene_folder: Path = tmp_path / "output"
    scene_folder.mkdir()

    with pytest.raises(FileNotFoundError):
        create_movie(
            scene_folder=scene_folder,
            output_path=scene_folder / "movie.mp4",
            config=None,
        )


def test_create_movie_raises_on_empty_scenes(tmp_path: Path):
    """Test that empty scene list raises ValueError."""
    scene_folder: Path = tmp_path / "output"
    scene_folder.mkdir()

    # Create metadata with empty scenes list
    root_metadata: dict = {"scenes": [], "generation_metadata": {}}

    with open(scene_folder / "metadata.json", "w") as f:
        json.dump(root_metadata, f)

    with pytest.raises(ValueError, match="No scenes found"):
        create_movie(
            scene_folder=scene_folder,
            output_path=scene_folder / "movie.mp4",
            config=None,
        )


def test_composite_movie_config_defaults():
    """Test that CompositeMovieConfig has correct defaults."""
    config: CompositeMovieConfig = CompositeMovieConfig()

    assert config.no_audio_length == 5.0
    assert config.output_filename == "movie.mp4"
    assert config.resolution == "1920x1080"
    assert config.fps == 30
    assert config.video_codec == "libx264"
    assert config.video_quality == 23
    assert config.audio_codec == "aac"
    assert config.audio_bitrate == "192k"


def test_composite_movie_config_validation():
    """Test that CompositeMovieConfig validates inputs."""
    # Test invalid no_audio_length (must be > 0)
    with pytest.raises(Exception):
        CompositeMovieConfig(no_audio_length=0)

    with pytest.raises(Exception):
        CompositeMovieConfig(no_audio_length=-1)

    # Test invalid resolution format
    with pytest.raises(Exception):
        CompositeMovieConfig(resolution="invalid")

    # Test invalid fps (must be 1-120)
    with pytest.raises(Exception):
        CompositeMovieConfig(fps=0)

    with pytest.raises(Exception):
        CompositeMovieConfig(fps=121)

    # Test invalid video_quality (must be 0-51)
    with pytest.raises(Exception):
        CompositeMovieConfig(video_quality=-1)

    with pytest.raises(Exception):
        CompositeMovieConfig(video_quality=52)
