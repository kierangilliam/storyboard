#!/usr/bin/env python3
"""Parallel CLI tool for generating scene assets from SDL files."""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from storyboard.cli.generate.logging_manager import StructuredLogger
from storyboard.cli.generate.parallel_generator import ParallelSceneGenerator
from storyboard.cli.generate.ui import TerminalUI
from storyboard.core.load.load import load_scene_graph
from storyboard.core.load.validate import validate_scene_graph


async def main_async(args):
    """Async main function for parallel generation."""
    start_time = time.time()

    # Determine paths
    if args.root_dir:
        root_dir = Path(args.root_dir)
        input_path = root_dir / args.input
        output_path = root_dir / args.output
        base_path = input_path.parent
    else:
        input_path = Path(args.input)
        output_path = Path(args.output)
        base_path = input_path.parent

    # Load the scene graph
    print(f"Loading scene graph from: {input_path}")
    try:
        scene_graph = load_scene_graph(input_path, base_path)
    except Exception as e:
        print(f"Error loading scene graph: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate scene graph
    print("Validating scene graph...")
    try:
        validate_scene_graph(scene_graph, base_path)
        print("✓ Validation passed")
    except Exception as e:
        print(f"✗ Validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate all scenes
    scene_ids = [scene.id for scene in scene_graph.scenes]
    print(f"\nGenerating all scenes: {', '.join(scene_ids)}")

    # Initialize logging
    logger = StructuredLogger()
    logger.log_generation_start(str(input_path), len(scene_ids))

    # Initialize UI
    ui = TerminalUI(sdl_file=str(input_path), total_scenes=len(scene_ids))

    # Initialize scene states in UI
    for scene in scene_graph.scenes:
        if scene.id in scene_ids:
            frame_ids = [frame.id for frame in scene.frames]

            # Determine which frames have audio
            has_audio = {}
            for frame in scene.frames:
                # Frame has audio if it has a tts config
                has_audio[frame.id] = frame.tts is not None

            ui.initialize_scene(scene.id, scene.name, frame_ids, has_audio)

    generator = ParallelSceneGenerator(scene_graph=scene_graph, callback=ui)

    print("\n" + "=" * 60)
    ui.start()

    try:
        # Generate all scenes in parallel
        results = await generator.generate_all_scenes(
            scene_ids, output_base_path=str(output_path)
        )

        # Write scene metadata files
        output_base = output_path
        successful_scenes = []

        for result in results:
            scene_output_dir = output_base / result.scene_id
            scene_output_dir.mkdir(parents=True, exist_ok=True)

            metadata = {
                "scene_id": result.scene_id,
                "scene_name": result.scene_name,
                "frames": [
                    {
                        "frame_id": frame.frame_id,
                        "speaker": frame.speaker,
                        "dialogue": frame.dialogue,
                        "assets": {
                            "image": frame.image_asset,
                            "audio": frame.audio_asset,
                        },
                        "template_used": frame.template_used,
                    }
                    for frame in result.frames
                ],
            }

            metadata_path = scene_output_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            if not result.failed_assets:
                successful_scenes.append(metadata)
                logger.log_scene_complete(result.scene_id, len(result.frames))

        # Write root metadata.json
        if successful_scenes:
            root_metadata = {
                "scenes": [
                    {
                        "scene_id": scene["scene_id"],
                        "scene_name": scene["scene_name"],
                        "frame_count": len(scene["frames"]),
                        "metadata_path": f"{scene['scene_id']}/metadata.json",
                    }
                    for scene in successful_scenes
                ],
                "generation_metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "sdl_file": str(input_path),
                    "total_scenes": len(successful_scenes),
                    "failed_scenes": [r.scene_id for r in results if r.failed_assets],
                },
            }

            root_metadata_path = output_base / "metadata.json"
            with open(root_metadata_path, "w") as f:
                json.dump(root_metadata, f, indent=2)

    finally:
        ui.stop()

    # Calculate final statistics
    end_time = time.time()
    duration_s = end_time - start_time

    failed_scene_count = sum(1 for r in results if r.failed_assets)
    successful_scene_count = len(results) - failed_scene_count

    logger.log_generation_complete(len(results), failed_scene_count, duration_s)

    # Print summary
    print("\n" + "=" * 60)
    print("Generation complete!")
    print(f"  Successful: {successful_scene_count}/{len(scene_ids)}")
    print(f"  Duration: {duration_s:.1f}s")
    print(f"  Logs: {logger.log_file}")

    if failed_scene_count > 0:
        print(f"\n  Failed scenes:")
        for result in results:
            if result.failed_assets:
                print(f"    - {result.scene_id}")
                for asset in result.failed_assets:
                    print(f"      {asset.frame_id}/{asset.asset_type}: {asset.error}")
        sys.exit(1)
    else:
        print("  All scenes generated successfully ✓")


def generate_command(args):
    """Generate scene assets from the main SDL file."""
    asyncio.run(main_async(args))
