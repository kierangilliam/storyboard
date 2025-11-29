"""Parser for converting YAML data into Pydantic models."""

import re
from pathlib import Path
from typing import Any

from storyboard.core.load.references import resolve_references
from storyboard.core.shapes import (
    Assets,
    Character,
    CharacterTTSConfig,
    Frame,
    ImageConfig,
    ImageTemplate,
    ImageTemplatePart,
    Scene,
    SceneGraph,
    StoryboardConfig,
    TTSConfig,
    TTSTemplate,
)


class ParseError(Exception):
    """Exception raised when parsing fails."""

    pass


def _preprocess_template_config(
    data: dict[str, Any], config_type: str, frame_id: str | None = None
) -> dict[str, Any]:
    """Preprocess template config by validating and stripping $ prefix from variable keys.

    Ensures that all keys except 'template' have a $ prefix in the raw data.
    """
    preprocessed: dict[str, Any] = {}

    for key, value in data.items():
        if key == "template":
            preprocessed[key] = value
        elif key.startswith("$"):
            # Strip the $ prefix for the actual field name
            preprocessed[key[1:]] = value
        else:
            # Key doesn't have $ prefix and isn't 'template' - this is an error
            frame_context = f" in frame '{frame_id}'" if frame_id else ""
            raise ParseError(
                f"Invalid {config_type} config{frame_context}: "
                f"key '{key}' must be prefixed with '$' (should be '${key}'). "
                f"Only 'template' is allowed without the prefix."
            )

    return preprocessed


def parse_character_tts_config(data: dict[str, Any]) -> CharacterTTSConfig:
    return CharacterTTSConfig(style=data["style"], voice=data["voice"])


def parse_character(data: dict[str, Any]) -> Character:
    tts = parse_character_tts_config(data["tts"]) if "tts" in data else None
    return Character(
        id=data["id"],
        name=data["name"],
        reference_photo=data["reference_photo"],
        tts=tts,
    )


def parse_tts_template(data: dict[str, Any]) -> TTSTemplate:
    return TTSTemplate(
        id=data["id"],
        voice_id=data["voice_id"],
        prompt=data["prompt"],
    )


def _expand_prompt_string(prompt_string: str) -> list[ImageTemplatePart]:
    """Parse string with embedded [image ...] and {$variable} syntax."""
    prompt_string = prompt_string.strip()

    parts: list[ImageTemplatePart] = []

    # Pattern matches [image ...] anywhere (not anchored)
    image_pattern = r"\[image\s+(\$[\w]+|\.?[\w/.\-]+)\]"

    # Split on image pattern, capturing the reference
    # Result: [text_before, image_ref, text_after, image_ref, ...]
    segments = re.split(image_pattern, prompt_string)

    for i, segment in enumerate(segments):
        if not segment:
            continue

        if i % 2 == 0:
            # Even indices: regular text (may contain {$variables})
            var_pattern = r"\{\$(\w+)\}"
            var_segments = re.split(var_pattern, segment)

            for j, var_seg in enumerate(var_segments):
                if not var_seg:
                    continue

                if j % 2 == 0:
                    # Regular text
                    parts.append(ImageTemplatePart(type="prompt", content=var_seg))
                else:
                    # Variable name (captured group)
                    parts.append(
                        ImageTemplatePart(type="prompt", key=var_seg, content="")
                    )
        else:
            # Odd indices: image reference (captured from [image ...])
            reference = segment.strip()

            if reference.startswith("$"):
                # Variable reference
                parts.append(
                    ImageTemplatePart(type="image", key=reference[1:], content="")
                )
            else:
                # File path
                parts.append(
                    ImageTemplatePart(type="image", content=reference, key=None)
                )

    return parts


def parse_image_template(data: dict[str, Any]) -> ImageTemplate:
    """Parse image template with string-based instructions containing inline [image ...] and {$variable} syntax."""
    if "instructions" in data:
        parts: list[ImageTemplatePart] = _expand_prompt_string(data["instructions"])
    elif "prompt" in data:
        parts: list[ImageTemplatePart] = _expand_prompt_string(data["prompt"])
    else:
        parts: list[ImageTemplatePart] = []

    return ImageTemplate(id=data["id"], parts=parts)


def parse_assets(data: dict[str, Any]) -> Assets:
    images_data = {}
    if "images" in data:
        for category, templates in data["images"].items():
            images_data[category] = [
                parse_image_template(template) for template in templates
            ]

    tts_data = {}
    if "tts" in data:
        for category, templates in data["tts"].items():
            tts_data[category] = [
                parse_tts_template(template) for template in templates
            ]

    return Assets(images=images_data, tts=tts_data)


def parse_frame(data: dict[str, Any]) -> Frame:
    """Parse a frame from raw data. References (@) are resolved post-processing."""
    frame_id = data.get("id", "unknown")

    # Preprocess image config
    image_data = data["image"].copy()

    # Strip _ prefix from template reference
    if "template" in image_data and isinstance(image_data["template"], str):
        if image_data["template"].startswith("_"):
            image_data["template"] = image_data["template"][1:]

    # Validate and strip $ prefix from variable definition keys
    preprocessed_image = _preprocess_template_config(image_data, "image", frame_id)
    image_config = ImageConfig(**preprocessed_image)

    # Preprocess tts config similarly
    tts_config = None
    if "tts" in data:
        tts_data = data["tts"].copy()

        # Strip _ prefix from template reference
        if "template" in tts_data and isinstance(tts_data["template"], str):
            if tts_data["template"].startswith("_"):
                tts_data["template"] = tts_data["template"][1:]

        # Validate and strip $ prefix from variable definition keys
        preprocessed_tts = _preprocess_template_config(tts_data, "tts", frame_id)
        tts_config = TTSConfig(**preprocessed_tts)

    return Frame(
        scene_id=data["scene_id"],
        id=data["id"],
        image=image_config,
        tts=tts_config,
    )


def _resolve_path(path_str: str, base_path: Path) -> str:
    file_path = Path(path_str)

    # Resolve relative paths using base_path
    if not file_path.is_absolute():
        if path_str.startswith("./"):
            resolved_path = base_path / path_str[2:]
        else:
            resolved_path = base_path / path_str
    else:
        resolved_path = file_path

    return str(resolved_path.absolute())


def _resolve_file_paths(scene_graph: SceneGraph) -> SceneGraph:
    """Resolve all relative file paths in the scene graph to absolute paths."""
    data = scene_graph.model_dump()
    base_path = scene_graph.base_path

    # Resolve character reference photos
    for character in data.get("characters", []):
        if "reference_photo" in character:
            character["reference_photo"] = _resolve_path(character["reference_photo"], base_path)

    # Resolve image template parts
    for category in data.get("assets", {}).get("images", {}).values():
        for template in category:
            for part in template.get("parts", []):
                if part.get("type") == "image" and part.get("content") and not part.get("key"):
                    # Static image reference - resolve it
                    part["content"] = _resolve_path(part["content"], base_path)

    # Resolve paths in frame image configs (template variables)
    for scene in data.get("scenes", []):
        for frame in scene.get("frames", []):
            image_config = frame.get("image", {})
            for key, value in list(image_config.items()):
                if key != "template" and isinstance(value, str):
                    # Check if this looks like a file path
                    if "/" in value or any(value.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]):
                        image_config[key] = _resolve_path(value, base_path)

    return SceneGraph(**data)


def parse_scene_graph(data: dict[str, Any], base_path: Path | None = None) -> SceneGraph:
    characters = [parse_character(c) for c in data.get("characters", [])]

    assets = parse_assets(data.get("assets", {}))

    scenes: list[Scene] = []

    raw_scenes = data.get("scenes", [])

    for scene_data in raw_scenes:
        scene_id = scene_data["id"]

        # Frames are nested within each scene in the YAML structure
        raw_frames = scene_data.get("frames", [])
        scene_frames: list[Frame] = []

        for frame_data in raw_frames:
            frame = parse_frame(frame_data)
            scene_frames.append(frame)

        scene = Scene(
            id=scene_id,
            name=scene_data["name"],
            frames=scene_frames,
        )
        scenes.append(scene)

    # Parse config if present
    config_data = data.get("config", {})
    config = StoryboardConfig(**config_data) if config_data else StoryboardConfig()

    # Determine base path
    if base_path is None:
        base_path = Path.cwd()

    # Build the initial scene graph (with unresolved references and relative paths)
    scene_graph = SceneGraph(
        characters=characters, assets=assets, scenes=scenes, config=config, base_path=base_path
    )

    # Resolve all file paths to absolute paths
    scene_graph = _resolve_file_paths(scene_graph)

    # Resolve all @ references as a post-processing step
    return resolve_references(scene_graph)
