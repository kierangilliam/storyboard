import json
from pathlib import Path

from storyboard.core.load.load import load_scene_graph


def test_load_simple_scene_graph(simple_fixture_path: Path):
    scene_graph = load_scene_graph(simple_fixture_path)

    assert scene_graph is not None
    assert len(scene_graph.characters) == 1
    assert scene_graph.characters[0].id == "test_char"
    assert scene_graph.characters[0].name == "Test Character"

    assert "templates" in scene_graph.assets.images
    assert len(scene_graph.assets.images["templates"]) == 1

    assert len(scene_graph.scenes) == 1
    assert scene_graph.scenes[0].id == "test_scene"
    assert len(scene_graph.scenes[0].frames) == 1


def test_load_main_content():
    content_path: Path = Path("example/content/main.yaml")
    base_path: Path = Path("example")

    scene_graph = load_scene_graph(content_path, base_path)

    assert scene_graph is not None
    assert len(scene_graph.characters) > 0

    character_ids: list[str] = [char.id for char in scene_graph.characters]
    assert "nick" in character_ids
    assert "chris" in character_ids

    assert len(scene_graph.scenes) > 0

    assert scene_graph.config is not None
    assert scene_graph.config.output.directory == "./output"


def test_scene_graph_json_serialization(simple_fixture_path: Path):
    scene_graph = load_scene_graph(simple_fixture_path)

    scene_dict: dict = scene_graph.model_dump()

    assert "characters" in scene_dict
    assert "assets" in scene_dict
    assert "scenes" in scene_dict
    assert "config" in scene_dict

    json_str: str = json.dumps(scene_dict)
    assert json_str is not None
    assert len(json_str) > 0

    parsed: dict = json.loads(json_str)
    assert parsed["characters"][0]["name"] == "Test Character"
