"""Selector parsing for update command."""

from typing import Literal

from storyboard.core.shapes import SceneGraph


def parse_update_selector(
    selector: str, scene_graph: SceneGraph
) -> tuple[str, str, set[Literal["image", "audio"]]]:
    """Parse update selector and resolve to IDs and asset types.

    Supports:
    - "scene_id.frame_id" -> string IDs
    - "scene_id.frame_id.image" -> selective asset type
    - "scene_id.frame_id.tts" -> audio asset (tts is alias for audio)

    Returns:
        Tuple of (scene_id, frame_id, asset_types_set)

    Raises:
        ValueError: If selector format is invalid or IDs not found
    """
    parts = selector.split(".")

    if len(parts) < 2 or len(parts) > 3:
        raise ValueError(
            f"Invalid selector format: '{selector}'. "
            "Expected: <scene>.<frame>[.<asset_type>]"
        )

    scene_selector, frame_selector = parts[0], parts[1]
    asset_type = parts[2] if len(parts) == 3 else None

    # Resolve asset types
    asset_types: set[Literal["image", "audio"]] = {"image", "audio"}
    if asset_type:
        if asset_type not in {"image", "tts", "audio"}:
            raise ValueError(
                f"Invalid asset type: '{asset_type}'. Must be 'image' or 'tts'"
            )
        # Normalize tts/audio to audio, image to image
        if asset_type in {"tts", "audio"}:
            asset_types = {"audio"}
        else:
            asset_types = {"image"}

    # Resolve scene ID (string lookup only)
    scene = None
    for s in scene_graph.scenes:
        if s.id == scene_selector:
            scene = s
            break

    if not scene:
        available = [f"{s.id}" for s in scene_graph.scenes]
        raise ValueError(
            f"Scene not found: '{scene_selector}'\n"
            f"Available scenes:\n  " + ", ".join(available)
        )

    scene_id = scene.id

    # Resolve frame ID (string lookup only)
    frame = None
    for f in scene.frames:
        if f.id == frame_selector:
            frame = f
            break

    if not frame:
        available = [f.id for f in scene.frames]
        raise ValueError(
            f"Frame not found in scene '{scene_id}': '{frame_selector}'\n"
            f"Available frames in {scene_id}:\n  " + ", ".join(available)
        )

    return scene_id, frame.id, asset_types
