import json
from pathlib import Path

import pytest

from storyboard.core.image.generate import (
    ImageTemplateContext,
    _render_template_parts,
)
from storyboard.core.load.parse import _expand_prompt_string
from storyboard.core.load.references import resolve_references
from storyboard.core.shapes import (
    Character,
    CharacterTTSConfig,
    ImageTemplatePart,
    SceneGraph,
)
from storyboard.core.templating import render_template_string


def test_tts_template_basic_rendering():
    template_str: str = "{$voice}"
    context: dict = {"voice": "Fenrir"}

    result: str = render_template_string(template_str, context)

    assert result == "Fenrir"


def test_tts_template_nested_attributes():
    template_str: str = "{$character.tts.style}:\n\n{$content}"

    character = Character(
        id="test",
        name="Test",
        reference_photo="./test.png",
        tts=CharacterTTSConfig(style="Dramatic tone", voice="Fenrir"),
    )
    context: dict = {"character": character, "content": "Hello world"}

    result: str = render_template_string(template_str, context)

    assert result == "Dramatic tone:\n\nHello world"


def test_tts_template_missing_variable():
    template_str: str = "{$missing_var}"
    context: dict = {}

    with pytest.raises(ValueError) as exc_info:
        render_template_string(template_str, context)

    error_msg: str = str(exc_info.value)
    assert "Missing required template variable: 'missing_var'. Available: []" == error_msg


def test_image_template_prompt_variable():
    parts: list[ImageTemplatePart] = [
        ImageTemplatePart(type="prompt", content="", key="location_name")
    ]

    context = ImageTemplateContext(location_name="Test Location")

    rendered_parts: list[ImageTemplatePart] = _render_template_parts(parts, context)

    assert [p.model_dump() for p in rendered_parts] == [
        {"type": "prompt", "content": "Test Location", "key": None}
    ]


def test_image_template_image_variable(test_image_file: Path):
    parts: list[ImageTemplatePart] = [
        ImageTemplatePart(type="image", content="", key="character_reference")
    ]

    context = ImageTemplateContext(character_reference=str(test_image_file))

    rendered_parts: list[ImageTemplatePart] = _render_template_parts(parts, context)

    assert [p.model_dump() for p in rendered_parts] == [
        {"type": "image", "content": str(test_image_file), "key": None}
    ]


def test_image_template_mixed_parts(test_image_file: Path):
    prompt_str: str = f"Turn this [image $ref] into {{$style}}"

    parts: list[ImageTemplatePart] = _expand_prompt_string(prompt_str)

    assert [p.model_dump() for p in parts] == [
        {"type": "prompt", "content": "Turn this ", "key": None},
        {"type": "image", "content": "", "key": "ref"},
        {"type": "prompt", "content": " into ", "key": None},
        {"type": "prompt", "content": "", "key": "style"},
    ]

    context = ImageTemplateContext(ref=str(test_image_file), style="anime")

    rendered_parts: list[ImageTemplatePart] = _render_template_parts(parts, context)

    assert [p.model_dump() for p in rendered_parts] == [
        {"type": "prompt", "content": "Turn this ", "key": None},
        {"type": "image", "content": str(test_image_file), "key": None},
        {"type": "prompt", "content": " into ", "key": None},
        {"type": "prompt", "content": "anime", "key": None},
    ]


def test_resolve_character_reference(test_image_file: Path):
    data: dict = {
        "characters": [
            {
                "id": "nick",
                "name": "Nick Brewer",
                "reference_photo": str(test_image_file),
            }
        ],
        "assets": {"images": {}, "tts": {}},
        "scenes": [
            {
                "id": "test_scene",
                "name": "Test",
                "frames": [
                    {
                        "id": "frame1",
                        "scene_id": "test_scene",
                        "image": {
                            "template": "test",
                            "ref": "@characters.nick.name",
                        },
                    }
                ],
            }
        ],
        "config": {},
    }

    scene_graph = SceneGraph(**data)
    resolved_graph = resolve_references(scene_graph)

    frame_image = resolved_graph.scenes[0].frames[0].image
    assert frame_image.ref == "Nick Brewer"


def test_resolve_self_reference(test_image_file: Path):
    data: dict = {
        "characters": [
            {"id": "test", "name": "Test", "reference_photo": str(test_image_file)}
        ],
        "assets": {"images": {}, "tts": {}},
        "scenes": [
            {
                "id": "test_scene",
                "name": "Test",
                "frames": [
                    {
                        "id": "frame1",
                        "scene_id": "test_scene",
                        "image": {
                            "template": "test",
                            "self_ref": "@self.template",
                        },
                    }
                ],
            }
        ],
        "config": {},
    }

    scene_graph = SceneGraph(**data)
    resolved_graph = resolve_references(scene_graph)

    frame_image = resolved_graph.scenes[0].frames[0].image
    assert frame_image.self_ref == "test"


def test_resolve_parent_reference(test_image_file: Path):
    data: dict = {
        "characters": [
            {"id": "test", "name": "Test", "reference_photo": str(test_image_file)}
        ],
        "assets": {"images": {}, "tts": {}},
        "scenes": [
            {
                "id": "test_scene",
                "name": "Test",
                "frames": [
                    {
                        "id": "frame1",
                        "scene_id": "test_scene",
                        "image": {
                            "template": "test",
                            "parent_ref": "@parent.scene_id",
                        },
                    }
                ],
            }
        ],
        "config": {},
    }

    scene_graph = SceneGraph(**data)
    resolved_graph = resolve_references(scene_graph)

    frame_image = resolved_graph.scenes[0].frames[0].image
    assert frame_image.parent_ref == "test_scene"


def test_resolve_complex_nested_reference(test_image_file: Path):
    data: dict = {
        "characters": [
            {
                "id": "chris",
                "name": "Chris",
                "reference_photo": str(test_image_file),
                "tts": {"style": "Dramatic", "voice": "Enceladus"},
            }
        ],
        "assets": {"images": {}, "tts": {}},
        "scenes": [
            {
                "id": "test_scene",
                "name": "Test",
                "frames": [
                    {
                        "id": "frame1",
                        "scene_id": "test_scene",
                        "image": {
                            "template": "test",
                            "voice_ref": "@characters.chris.tts.voice",
                        },
                    }
                ],
            }
        ],
        "config": {},
    }

    scene_graph = SceneGraph(**data)
    resolved_graph = resolve_references(scene_graph)

    frame_image = resolved_graph.scenes[0].frames[0].image
    assert frame_image.voice_ref == "Enceladus"


def test_reference_json_serialization(test_image_file: Path):
    data: dict = {
        "characters": [
            {
                "id": "test",
                "name": "Test",
                "reference_photo": str(test_image_file),
                "tts": {"style": "Test style", "voice": "Fenrir"},
            }
        ],
        "assets": {"images": {}, "tts": {}},
        "scenes": [
            {
                "id": "test_scene",
                "name": "Test",
                "frames": [
                    {
                        "id": "frame1",
                        "scene_id": "test_scene",
                        "image": {
                            "template": "test",
                            "char_obj": "@characters.test",
                        },
                    }
                ],
            }
        ],
        "config": {},
    }

    scene_graph = SceneGraph(**data)
    resolved_graph = resolve_references(scene_graph)

    frame_image = resolved_graph.scenes[0].frames[0].image
    char_obj_str: str = frame_image.char_obj

    assert isinstance(char_obj_str, str)

    char_obj: dict = json.loads(char_obj_str)
    assert char_obj["name"] == "Test"
    assert char_obj["tts"]["voice"] == "Fenrir"


def test_image_bracket_syntax_parsing():
    prompt_str: str = "Some text [image ./path.png] more text"

    parts: list[ImageTemplatePart] = _expand_prompt_string(prompt_str)

    assert [p.model_dump() for p in parts] == [
        {"type": "prompt", "content": "Some text ", "key": None},
        {"type": "image", "content": "./path.png", "key": None},
        {"type": "prompt", "content": " more text", "key": None},
    ]


def test_variable_bracket_syntax_parsing():
    prompt_str: str = "Text [image $variable] end"

    parts: list[ImageTemplatePart] = _expand_prompt_string(prompt_str)

    assert [p.model_dump() for p in parts] == [
        {"type": "prompt", "content": "Text ", "key": None},
        {"type": "image", "content": "", "key": "variable"},
        {"type": "prompt", "content": " end", "key": None},
    ]
