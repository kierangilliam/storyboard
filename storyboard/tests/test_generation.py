import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from storyboard.core.image.generate import (
    ImageGen,
    ImageModelDefinition,
    ImageModels,
    ImageTemplateContext,
    ImageTemplatePart,
)
from storyboard.core.shapes import TTSTemplate
from storyboard.core.tts.generate import (
    TTSGen,
    TTSModelDefinition,
    TTSModels,
    TTSTemplateContext,
    _compute_tts_cache_hash,
)


@pytest.mark.asyncio
async def test_image_gen_calls_gemini_with_correct_prompt(
    mock_gemini_client: MagicMock, tmp_path: Path, test_image_file: Path
):
    model: ImageModelDefinition = ImageModels.gemini("pro")
    parts: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="Turn this person "),
        ImageTemplatePart(type="image", content=str(test_image_file)),
        ImageTemplatePart(type="prompt", content=" into anime style"),
    ]

    result = await ImageGen.make(
        model=model, parts=parts, cache_directory=str(tmp_path), use_cached=False
    )

    mock_gemini_client.aio.models.generate_content.assert_called_once()

    call_args = mock_gemini_client.aio.models.generate_content.call_args
    config = call_args.kwargs["config"]
    contents = call_args.kwargs["contents"]

    assert config.response_modalities == ["IMAGE"]
    assert len(contents) == 3
    assert isinstance(contents[0], str)
    assert "Turn this person" in contents[0]


@pytest.mark.asyncio
async def test_image_gen_caching(
    mock_gemini_client: MagicMock, tmp_path: Path, test_image_file: Path
):
    model: ImageModelDefinition = ImageModels.gemini("pro")
    parts: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="Test prompt"),
    ]

    result1 = await ImageGen.make(
        model=model, parts=parts, cache_directory=str(tmp_path), use_cached=True
    )

    assert result1.used_cached is False
    assert mock_gemini_client.aio.models.generate_content.call_count == 1

    result2 = await ImageGen.make(
        model=model, parts=parts, cache_directory=str(tmp_path), use_cached=True
    )

    assert result2.used_cached is True
    assert mock_gemini_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_image_gen_cache_hash_content_based(tmp_path: Path):
    from storyboard.core.image.generate import _compute_cache_hash

    model1: ImageModelDefinition = ImageModels.gemini("pro")
    model2: ImageModelDefinition = ImageModels.gemini("flash")
    parts1: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="Test prompt 1"),
    ]
    parts2: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="Test prompt 2"),
    ]

    hash1: str = _compute_cache_hash(parts1, model1)
    hash2: str = _compute_cache_hash(parts1, model2)
    hash3: str = _compute_cache_hash(parts2, model1)
    hash4: str = _compute_cache_hash(parts1, model1)

    assert hash1 != hash2
    assert hash1 != hash3
    assert hash1 == hash4


@pytest.mark.asyncio
async def test_image_gen_from_template(
    mock_gemini_client: MagicMock, tmp_path: Path, test_image_file: Path
):
    model: ImageModelDefinition = ImageModels.gemini("pro")
    template: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="Turn ", key=None),
        ImageTemplatePart(type="image", content="", key="char_ref"),
        ImageTemplatePart(type="prompt", content="", key="style"),
    ]
    context = ImageTemplateContext(char_ref=str(test_image_file), style=" anime style")

    result = await ImageGen.from_template(
        model=model,
        template=template,
        context=context,
        cache_directory=str(tmp_path),
        use_cached=False,
    )

    mock_gemini_client.aio.models.generate_content.assert_called_once()

    call_args = mock_gemini_client.aio.models.generate_content.call_args
    contents = call_args.kwargs["contents"]

    assert len(contents) == 3


@pytest.mark.asyncio
async def test_image_gen_reference_photos_order(
    mock_gemini_client: MagicMock, tmp_path: Path, test_image_file: Path
):
    model: ImageModelDefinition = ImageModels.gemini("pro")
    parts: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="prompt1 "),
        ImageTemplatePart(type="image", content=str(test_image_file)),
        ImageTemplatePart(type="prompt", content=" prompt2 "),
        ImageTemplatePart(type="image", content=str(test_image_file)),
        ImageTemplatePart(type="prompt", content=" prompt3"),
    ]

    result = await ImageGen.make(
        model=model, parts=parts, cache_directory=str(tmp_path), use_cached=False
    )

    assert len(result.reference_photos) == 2
    assert all(str(test_image_file) in photo for photo in result.reference_photos)

    call_args = mock_gemini_client.aio.models.generate_content.call_args
    contents = call_args.kwargs["contents"]

    assert len(contents) == 5


@pytest.mark.asyncio
async def test_tts_gen_calls_gemini_with_correct_prompt(
    mock_gemini_client: MagicMock, tmp_path: Path
):
    model: TTSModelDefinition = TTSModels.gemini("flash")
    prompt: str = "Test narration content"
    voice_id: str = "Fenrir"

    result = await TTSGen.make(
        model=model,
        prompt=prompt,
        voice_id=voice_id,
        output_path=str(tmp_path),
        cache_directory=str(tmp_path / "cache"),
        use_cached=False,
    )

    mock_gemini_client.aio.models.generate_content.assert_called_once()

    call_args = mock_gemini_client.aio.models.generate_content.call_args
    config = call_args.kwargs["config"]
    contents = call_args.kwargs["contents"]

    assert config.response_modalities == ["AUDIO"]
    assert config.speech_config is not None
    assert contents == prompt


@pytest.mark.asyncio
async def test_tts_gen_caching(mock_gemini_client: MagicMock, tmp_path: Path):
    model: TTSModelDefinition = TTSModels.gemini("flash")
    prompt: str = "Test content"
    voice_id: str = "Fenrir"

    result1 = await TTSGen.make(
        model=model,
        prompt=prompt,
        voice_id=voice_id,
        output_path=str(tmp_path / "output1"),
        cache_directory=str(tmp_path / "cache"),
        use_cached=True,
    )

    assert result1.used_cached is False
    assert mock_gemini_client.aio.models.generate_content.call_count == 1

    result2 = await TTSGen.make(
        model=model,
        prompt=prompt,
        voice_id=voice_id,
        output_path=str(tmp_path / "output2"),
        cache_directory=str(tmp_path / "cache"),
        use_cached=True,
    )

    assert result2.used_cached is True
    assert mock_gemini_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_tts_gen_wav_file_format(mock_gemini_client: MagicMock, tmp_path: Path):
    model: TTSModelDefinition = TTSModels.gemini("flash")

    result = await TTSGen.make(
        model=model,
        prompt="Test",
        voice_id="Fenrir",
        output_path=str(tmp_path),
        cache_directory=str(tmp_path / "cache"),
        output_name="test_audio",
        use_cached=False,
    )

    output_path: Path = Path(result.output_path)
    assert output_path.exists()
    assert output_path.suffix == ".wav"

    with wave.open(str(output_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000


@pytest.mark.asyncio
async def test_tts_gen_from_template(mock_gemini_client: MagicMock, tmp_path: Path):
    from storyboard.core.shapes import Character, CharacterTTSConfig

    model: TTSModelDefinition = TTSModels.gemini("flash")
    template = TTSTemplate(
        id="test",
        voice_id="{$character.tts.voice}",
        prompt="{$character.tts.style}:\n\n{$content}",
    )

    character = Character(
        id="test",
        name="Test",
        reference_photo="./test.png",
        tts=CharacterTTSConfig(style="Dramatic tone", voice="Fenrir"),
    )
    context = TTSTemplateContext(character=character, content="Hello world")

    result = await TTSGen.from_template(
        model=model,
        template=template,
        context=context,
        output_path=str(tmp_path),
        cache_directory=str(tmp_path / "cache"),
        use_cached=False,
    )

    mock_gemini_client.aio.models.generate_content.assert_called_once()

    call_args = mock_gemini_client.aio.models.generate_content.call_args
    contents = call_args.kwargs["contents"]

    assert "Dramatic tone" in contents
    assert "Hello world" in contents


@pytest.mark.asyncio
async def test_tts_cache_hash_includes_all_components():
    model1: TTSModelDefinition = TTSModels.gemini("flash")
    model2: TTSModelDefinition = TTSModels.gemini("pro")

    hash1: str = _compute_tts_cache_hash("Fenrir", "Test prompt", model1)
    hash2: str = _compute_tts_cache_hash("Kore", "Test prompt", model1)
    hash3: str = _compute_tts_cache_hash("Fenrir", "Different prompt", model1)
    hash4: str = _compute_tts_cache_hash("Fenrir", "Test prompt", model1)
    hash5: str = _compute_tts_cache_hash("Fenrir", "Test prompt", model2)

    assert hash1 != hash2
    assert hash1 != hash3
    assert hash1 == hash4
    assert hash1 != hash5
