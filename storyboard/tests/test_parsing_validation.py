from pathlib import Path

import pytest
from pydantic import ValidationError

from storyboard.core.load.load import load_scene_graph
from storyboard.core.load.parse import ParseError
from storyboard.core.load.references import CircularReferenceError
from storyboard.core.load.validate import ValidationError as SceneValidationError
from storyboard.core.load.validate import validate_scene_graph
from storyboard.core.shapes import (
    Character,
    CharacterTTSConfig,
    ImageTemplate,
    ImageTemplatePart,
    StoryboardConfig,
)


def test_invalid_image_vendor():
    with pytest.raises(ValidationError) as exc_info:
        StoryboardConfig(
            image={"default_model": {"vendor": "openai", "model": "dall-e-3"}}
        )
    error_msg: str = str(exc_info.value)
    assert "Input should be 'gemini'" in error_msg


def test_invalid_image_model():
    with pytest.raises(ValidationError) as exc_info:
        StoryboardConfig(
            image={"default_model": {"vendor": "gemini", "model": "invalid-model"}}
        )
    error_msg: str = str(exc_info.value)
    assert (
        "Input should be 'gemini-3-pro-image-preview' or 'gemini-2.5-flash-image'"
        in error_msg
    )


def test_invalid_tts_voice():
    with pytest.raises(ValidationError) as exc_info:
        CharacterTTSConfig(style="Test style", voice="InvalidVoice")
    error_msg: str = str(exc_info.value)
    assert (
        "Input should be 'Aoede', 'Kore', 'Fenrir', 'Enceladus', 'Schedar' or 'Vindemiatrix'"
        in error_msg
    )


def test_invalid_quality_range():
    with pytest.raises(ValidationError) as exc_info:
        StoryboardConfig(image={"optimize": {"enabled": True, "quality": 101}})
    error_msg: str = str(exc_info.value)
    assert "quality must be between 1 and 100, got 101" in error_msg


def test_invalid_retry_config():
    with pytest.raises(ValidationError) as exc_info:
        StoryboardConfig(
            generation={
                "retry": {"enabled": True, "max_attempts": 0, "delay_seconds": 1}
            }
        )
    error_msg: str = str(exc_info.value)
    assert "max_attempts must be at least 1, got 0" in error_msg


def test_invalid_reference_section():
    fixture_path: Path = Path("storyboard/tests/fixtures/invalid/bad_references.yaml")

    with pytest.raises(ValueError) as exc_info:
        scene_graph = load_scene_graph(fixture_path)

    error_msg: str = str(exc_info.value)
    assert (
        "No item with id='nonexistent' found in list at path: characters._nonexistent"
        == error_msg
    )


def test_invalid_character_reference(tmp_path: Path, test_image_file: Path):
    bad_ref_yaml: str = f"""_test_char:
  name: Test Character
  reference_photo: {test_image_file}
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(bad_ref_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test {$var}"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "{$content}"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames:
    _frame:
      image:
        template: _test_template
        $var: "@characters.nonexistent.name"
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = f"""characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    with pytest.raises(ValueError) as exc_info:
        scene_graph = load_scene_graph(main_file)

    error_msg: str = str(exc_info.value)
    assert (
        "No item with id='nonexistent' found in list at path: characters.nonexistent"
        == error_msg
    )


def test_invalid_attribute_reference(tmp_path: Path, test_image_file: Path):
    bad_ref_yaml: str = f"""_test_char:
  name: Test Character
  reference_photo: {test_image_file}
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(bad_ref_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test {$var}"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "{$content}"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames:
    _frame:
      image:
        template: _test_template
        $var: "@characters.test_char.nonexistent_field"
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = f"""characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    with pytest.raises(ValueError) as exc_info:
        scene_graph = load_scene_graph(main_file)

    error_msg: str = str(exc_info.value)
    assert (
        "Cannot access 'nonexistent_field' on Character at path: characters.test_char.nonexistent_field"
        == error_msg
    )


def test_circular_reference(tmp_path: Path, test_image_file: Path):
    chars_yaml: str = f"""_char1:
  name: "@characters._char2.name"
  reference_photo: {test_image_file}
_char2:
  name: "@characters._char1.name"
  reference_photo: {test_image_file}
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(chars_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "Test"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames: {}
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = """characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    with pytest.raises(CircularReferenceError) as exc_info:
        load_scene_graph(main_file)

    error_msg: str = str(exc_info.value)
    assert error_msg.startswith("Circular reference detected: @characters.")


def test_missing_template_variables():
    fixture_path: Path = Path(
        "storyboard/tests/fixtures/invalid/bad_template_vars.yaml"
    )
    scene_graph = load_scene_graph(fixture_path)

    with pytest.raises(SceneValidationError) as exc_info:
        validate_scene_graph(scene_graph, fixture_path.parent)

    error_msg: str = str(exc_info.value)
    assert (
        "Frame 'test_frame': missing required template variables for template 'simple_template': ['backdrop']"
        in error_msg
    )


def test_undefined_template_reference(tmp_path: Path, test_image_file: Path):
    chars_yaml: str = f"""_test_char:
  name: Test
  reference_photo: {test_image_file}
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(chars_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "Test"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames:
    _frame:
      image:
        template: _nonexistent_template
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = """characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    scene_graph = load_scene_graph(main_file)

    with pytest.raises(SceneValidationError) as exc_info:
        validate_scene_graph(scene_graph, main_file.parent)

    error_msg: str = str(exc_info.value)
    assert (
        "Frame 'frame' in scene 'test_scene': template 'nonexistent_template' not found in assets"
        in error_msg
    )


def test_nonexistent_character_photo():
    fixture_path: Path = Path("storyboard/tests/fixtures/invalid/bad_paths.yaml")

    with pytest.raises(ValueError) as exc_info:
        scene_graph = load_scene_graph(fixture_path)

    error_msg: str = str(exc_info.value)
    assert (
        "No item with id='simple_char' found in list at path: characters._simple_char"
        == error_msg
    )


def test_nonexistent_image_template_reference(tmp_path: Path):
    chars_yaml: str = """_test_char:
  name: Test
  reference_photo: ../assets/test_image.png
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(chars_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test [image ./missing.png]"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "Test"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames: {}
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = """characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    scene_graph = load_scene_graph(main_file)

    with pytest.raises(SceneValidationError) as exc_info:
        validate_scene_graph(scene_graph, main_file.parent)

    error_msg: str = str(exc_info.value)
    assert (
        "Image template 'test_template' (category 'templates'): reference not found"
        in error_msg
    )
    assert "missing.png" in error_msg


def test_invalid_file_extension(tmp_path: Path):
    chars_yaml: str = """_test_char:
  name: Test
  reference_photo: ./test.txt
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(chars_yaml)

    (tmp_path / "test.txt").write_text("Not an image")

    templates_yaml: str = """_test_template:
  instructions: "Test"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "Test"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    scenes_yaml: str = """_test_scene:
  name: Test
  frames: {}
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = """characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    scene_graph = load_scene_graph(main_file)

    with pytest.raises(SceneValidationError) as exc_info:
        validate_scene_graph(scene_graph, main_file.parent)

    error_msg: str = str(exc_info.value)
    assert (
        "Character 'test_char': reference_photo has invalid extension '.txt'"
        in error_msg
    )


def test_empty_string_validation():
    with pytest.raises(ValidationError) as exc_info:
        Character(id="", name="Test", reference_photo="./test.png")
    error_msg: str = str(exc_info.value)
    assert "String should have at least 1 character" in error_msg


def test_image_template_part_key_validation():
    with pytest.raises(ValidationError) as exc_info:
        ImageTemplatePart(type="prompt", content="test", key="invalid key!")
    error_msg: str = str(exc_info.value)
    assert (
        "key must contain only alphanumeric characters, hyphens, and underscores"
        in error_msg
    )


def test_image_template_requires_non_empty_parts():
    with pytest.raises(ValidationError) as exc_info:
        ImageTemplate(id="test", parts=[])
    error_msg: str = str(exc_info.value)
    assert "parts list cannot be empty" in error_msg


def test_image_config_requires_dollar_prefix(tmp_path: Path, test_image_file: Path):
    """Test that image config keys require $ prefix for template variables."""
    chars_yaml: str = f"""_test_char:
  name: Test
  reference_photo: {test_image_file}
"""
    chars_file: Path = tmp_path / "characters.yaml"
    chars_file.write_text(chars_yaml)

    templates_yaml: str = """_test_template:
  instructions: "Test {$backdrop}"
"""
    templates_file: Path = tmp_path / "templates.yaml"
    templates_file.write_text(templates_yaml)

    tts_yaml: str = """_test_tts:
  voice_id: Fenrir
  prompt: "Test"
"""
    tts_file: Path = tmp_path / "tts.yaml"
    tts_file.write_text(tts_yaml)

    # Missing $ prefix on backdrop - should fail
    scenes_yaml: str = """_test_scene:
  name: Test
  frames:
    _frame:
      image:
        template: _test_template
        backdrop: "A tavern"
"""
    scenes_file: Path = tmp_path / "scenes.yaml"
    scenes_file.write_text(scenes_yaml)

    main_yaml: str = """characters: ./characters.yaml
image_templates: ./templates.yaml
tts_templates: ./tts.yaml
scenes: ./scenes.yaml
"""
    main_file: Path = tmp_path / "main.yaml"
    main_file.write_text(main_yaml)

    with pytest.raises(ParseError) as exc_info:
        load_scene_graph(main_file)

    error_msg: str = str(exc_info.value)
    assert "Invalid image config" in error_msg
    assert "key 'backdrop' must be prefixed with '$'" in error_msg
    assert "should be '$backdrop'" in error_msg
