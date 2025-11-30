"""Scene generation orchestrator for generating images and audio from SDL."""

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_orphaned_files(output_base_path: str = "./output/scenes") -> None:
    """Clean up orphaned scene folders and asset files after generation."""
    scenes_dir = Path(output_base_path)
    if not scenes_dir.exists():
        logger.warning(f"Output directory does not exist: {scenes_dir}")
        return

    # Read root metadata to get valid scene IDs
    root_metadata_path = scenes_dir / "metadata.json"
    if not root_metadata_path.exists():
        logger.info(f"No root metadata.json found at {root_metadata_path}, skipping cleanup")
        return

    with open(root_metadata_path, "r") as f:
        root_metadata = json.load(f)

    valid_scene_ids = {scene["scene_id"] for scene in root_metadata.get("scenes", [])}
    logger.info(f"Valid scenes from metadata: {valid_scene_ids}")

    # Clean up orphaned scene folders
    cleaned_folders = 0
    for item in scenes_dir.iterdir():
        # Skip the root metadata.json file
        if item.name == "metadata.json":
            continue

        # If it's a directory and not in valid scenes, remove it
        if item.is_dir() and item.name not in valid_scene_ids:
            logger.info(f"Removing orphaned scene folder: {item.name}")
            shutil.rmtree(item)
            cleaned_folders += 1

    # Clean up orphaned frame folders within valid scene folders
    cleaned_frames = 0
    for scene_id in valid_scene_ids:
        scene_dir = scenes_dir / scene_id
        if not scene_dir.exists():
            continue

        # Read scene metadata to get valid frame IDs
        scene_metadata_path = scene_dir / "metadata.json"
        if not scene_metadata_path.exists():
            logger.warning(f"Scene {scene_id} has no metadata.json, skipping frame cleanup")
            continue

        with open(scene_metadata_path, "r") as f:
            scene_metadata = json.load(f)

        # Collect all valid frame IDs from metadata
        valid_frame_ids = {frame["frame_id"] for frame in scene_metadata.get("frames", [])}

        # Remove orphaned frame folders
        for item in scene_dir.iterdir():
            # Skip metadata.json file
            if item.name == "metadata.json":
                continue

            # If it's a directory and not a valid frame ID, remove it
            if item.is_dir() and item.name not in valid_frame_ids:
                logger.info(f"Removing orphaned frame folder: {scene_id}/{item.name}")
                shutil.rmtree(item)
                cleaned_frames += 1

    if cleaned_folders > 0 or cleaned_frames > 0:
        logger.info(f"Cleanup complete: removed {cleaned_folders} scene folder(s) and {cleaned_frames} orphaned frame folder(s)")
    else:
        logger.info("No orphaned files found")
