from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image


@pytest.fixture
def mock_gemini_client(monkeypatch):
    """Mock Gemini API client for testing without real API calls."""
    mock_client = MagicMock()

    async def mock_generate_content(*args, **kwargs):
        config = kwargs.get("config")
        if config.response_modalities == ["IMAGE"]:
            mock_response = MagicMock()
            mock_image = Image.new("RGB", (100, 100), color="red")
            mock_part = MagicMock()
            mock_part.as_image.return_value = mock_image
            mock_response.parts = [mock_part]
            return mock_response
        else:
            mock_response = MagicMock()
            fake_audio = b"\x00" * (24000 * 2)
            mock_response.candidates = [
                MagicMock(
                    content=MagicMock(
                        parts=[MagicMock(inline_data=MagicMock(data=fake_audio))]
                    )
                )
            ]
            return mock_response

    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=mock_generate_content
    )
    monkeypatch.setattr(
        "storyboard.core.image.generate.genai.Client", lambda: mock_client
    )
    monkeypatch.setattr("storyboard.core.tts.generate.genai.Client", lambda: mock_client)

    return mock_client


@pytest.fixture
def test_image_file(tmp_path: Path) -> Path:
    """Create a 1x1 pixel test PNG image."""
    image_path: Path = tmp_path / "test_image.png"
    img = Image.new("RGB", (1, 1), color="white")
    img.save(image_path)
    return image_path


@pytest.fixture
def simple_fixture_path(tmp_path: Path, test_image_file: Path) -> Path:
    """Create minimal valid YAML fixture set."""
    fixtures_dir: Path = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    main_yaml: str = f"""characters: ./characters.yaml
image_templates: ./image_templates.yaml
tts_templates: ./tts_templates.yaml
scenes: ./scenes.yaml

config:
  output:
    directory: ./output
    cache:
      images: .cache/images
      audio: .cache/audio
"""

    characters_yaml: str = f"""_test_char:
  name: Test Character
  reference_photo: {test_image_file}
  tts:
    style: "Test style"
    voice: Fenrir
"""

    image_templates_yaml: str = """_test_template:
  instructions: "Turn this person {{image $character_reference}} into a test style with backdrop {{$backdrop}}"
"""

    tts_templates_yaml: str = """_test_tts:
  voice_id: "{$character.tts.voice}"
  prompt: "{$character.tts.style}:\\n\\n{$content}"
"""

    scenes_yaml: str = """_test_scene:
  name: Test Scene
  frames:
    _test_frame:
      image:
        template: _test_template
        $character_reference: "@characters._test_char.reference_photo"
        $backdrop: "A test backdrop"
      tts:
        template: _test_tts
        $character: "@characters._test_char"
        $content: "Test dialogue"
"""

    (fixtures_dir / "main.yaml").write_text(main_yaml)
    (fixtures_dir / "characters.yaml").write_text(characters_yaml)
    (fixtures_dir / "image_templates.yaml").write_text(image_templates_yaml)
    (fixtures_dir / "tts_templates.yaml").write_text(tts_templates_yaml)
    (fixtures_dir / "scenes.yaml").write_text(scenes_yaml)

    return fixtures_dir / "main.yaml"
