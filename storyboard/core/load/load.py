"""Loader for reading and parsing YAML scene description files."""

from pathlib import Path
from typing import Any

import yaml

from storyboard.core.load.parse import parse_scene_graph
from storyboard.core.shapes import SceneGraph


def load_scene_graph(
    file_path: str | Path, base_path: Path | None = None
) -> SceneGraph:
    """Load and parse a scene graph from a YAML file.

    Args:
        file_path: Path to the main YAML file
        base_path: Base directory for resolving relative paths in the SDL.
                  Defaults to the parent directory of file_path.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        main_config = yaml.safe_load(f)

    # Load referenced files (relative to the YAML file location)
    yaml_base_path = file_path.parent
    data = _load_multi_file_config(main_config, yaml_base_path)

    # Determine base path for resolving asset paths
    if base_path is None:
        base_path = yaml_base_path

    # Parse the scene graph with path resolution context
    scene_graph = parse_scene_graph(data, base_path)

    return scene_graph


def _convert_tag_dict_to_array(tag_dict: dict) -> list[dict]:
    """Convert dictionary with _-prefixed keys to array with id fields.

    Input:  {_nick: {"name": "Nick", ...}}
    Output: [{"id": "nick", "name": "Nick", ...}]
    """
    result: list[dict] = []

    for key, value in tag_dict.items():
        if not key.startswith("_"):
            raise ValueError(f"Expected _ prefix on key: {key}")

        item_id = key[1:]  # Strip _ prefix
        item_dict = {"id": item_id, **value}
        result.append(item_dict)

    return result


def _convert_scenes_dict_to_array(scenes_dict: dict) -> list[dict]:
    """Convert scenes dictionary to array format, processing nested frames.

    Scenes have nested frames that also need _ prefix processing.
    """
    result: list[dict] = []

    for scene_key, scene_value in scenes_dict.items():
        if not scene_key.startswith("_"):
            raise ValueError(f"Expected _ prefix on scene key: {scene_key}")

        scene_id = scene_key[1:]  # Strip _ prefix

        # Process frames if present
        frames_dict = scene_value.get("frames", {})
        frames_array: list[dict] = []

        for frame_key, frame_value in frames_dict.items():
            if not frame_key.startswith("_"):
                raise ValueError(f"Expected _ prefix on frame key: {frame_key}")

            frame_id = frame_key[1:]  # Strip _ prefix
            frame_dict = {
                "id": frame_id,
                "scene_id": scene_id,  # Add parent scene_id
                **frame_value,
            }
            frames_array.append(frame_dict)

        # Build scene dict
        scene_dict = {
            "id": scene_id,
            "name": scene_value["name"],
            "frames": frames_array,
        }
        result.append(scene_dict)

    return result


def _load_multi_file_config(main_config: dict, base_path: Path) -> dict:
    """Load all referenced YAML files and merge into a single structure."""
    result: dict[str, Any] = {}

    # Load characters
    if "characters" in main_config:
        char_path = base_path / main_config["characters"]
        with open(char_path, "r") as f:
            characters_dict = yaml.safe_load(f)
        result["characters"] = _convert_tag_dict_to_array(characters_dict)

    # Load image templates
    if "image_templates" in main_config:
        tmpl_path = base_path / main_config["image_templates"]
        with open(tmpl_path, "r") as f:
            templates_dict = yaml.safe_load(f)
        result.setdefault("assets", {}).setdefault("images", {})["templates"] = (
            _convert_tag_dict_to_array(templates_dict)
        )

    # Load TTS templates
    if "tts_templates" in main_config:
        tts_path = base_path / main_config["tts_templates"]
        with open(tts_path, "r") as f:
            tts_dict = yaml.safe_load(f)
        result.setdefault("assets", {}).setdefault("tts", {})["templates"] = (
            _convert_tag_dict_to_array(tts_dict)
        )

    # Load scenes
    if "scenes" in main_config:
        scenes_path = base_path / main_config["scenes"]
        with open(scenes_path, "r") as f:
            scenes_dict = yaml.safe_load(f)
        result["scenes"] = _convert_scenes_dict_to_array(scenes_dict)

    # Load config
    if "config" in main_config:
        result["config"] = main_config["config"]

    return result


