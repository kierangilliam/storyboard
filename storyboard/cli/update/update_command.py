#!/usr/bin/env python3
"""Update command for regenerating specific scene frames."""

import asyncio
import json
import sys
import time
from pathlib import Path

from storyboard.cli.generate.parallel_generator import ParallelSceneGenerator
from storyboard.cli.update.interactive import interactive_select
from storyboard.cli.update.selector_parser import parse_update_selector
from storyboard.core.load.load import load_scene_graph


async def main_async(args):
    start_time = time.time()

    if args.root_dir:
        root_dir = Path(args.root_dir)
        input_path = root_dir / args.input
        output_path = root_dir / args.output
        base_path = input_path.parent
    else:
        input_path = Path(args.input)
        output_path = Path(args.output)
        base_path = input_path.parent

    try:
        scene_graph = load_scene_graph(input_path, base_path)
    except Exception as e:
        print(f"Error loading scene graph: {e}", file=sys.stderr)
        return 1

    if args.selector:
        try:
            scene_id, frame_id, asset_types = parse_update_selector(
                args.selector, scene_graph
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        result = interactive_select(scene_graph)
        if result is None:
            print("\nCancelled.")
            return 0
        scene_id, frame_id, asset_types = result

    # Validate frame has TTS if audio requested
    if "audio" in asset_types:
        scene = next((s for s in scene_graph.scenes if s.id == scene_id), None)
        frame = next((f for f in scene.frames if f.id == frame_id), None)
        if frame.tts is None:
            print(
                f"Error: Frame '{scene_id}.{frame_id}' has no TTS configuration. "
                f"Cannot generate audio asset.",
                file=sys.stderr,
            )
            return 1

    asset_type_str = "/".join(sorted(asset_types))
    print(f"Target: scene={scene_id}, frame={frame_id}, assets={asset_type_str}")

    scene_output_path = output_path / scene_id
    generator = ParallelSceneGenerator(scene_graph=scene_graph)

    print(f"Generating {asset_type_str}...")
    use_cached = args.use_cache
    if use_cached:
        print("  Using cache if available")
    else:
        print("  Bypassing cache (forcing regeneration)")

    try:
        frame_result, failures = await generator.generate_frame_selective(
            scene_id=scene_id,
            frame_id=frame_id,
            scene_output_path=str(scene_output_path),
            asset_types=asset_types,
            use_cached=use_cached,
        )
    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        return 1

    # Update metadata.json for this scene
    metadata_path = scene_output_path / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Update frame entry
        for frame_entry in metadata.get("frames", []):
            if frame_entry["frame_id"] == frame_id:
                # Only update the assets that were regenerated
                if "image" in asset_types:
                    frame_entry["assets"]["image"] = frame_result.image_asset
                if "audio" in asset_types:
                    frame_entry["assets"]["audio"] = frame_result.audio_asset
                break

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "=" * 60)
    print(f"Update complete in {duration:.1f}s")
    print(f"Scene: {scene_id}")
    print(f"Frame: {frame_id}")
    print(f"Assets: {asset_type_str}")

    if failures:
        print(f"\nFailed assets:")
        for task in failures:
            print(f"  {task.asset_type}: {task.error}")
        return 1
    else:
        print("All assets updated successfully ✓")
        return 0


def update_command(args):
    return asyncio.run(main_async(args))
