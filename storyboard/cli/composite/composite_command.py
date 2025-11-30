#!/usr/bin/env python3
"""CLI command for creating composite videos from scenes."""

from pathlib import Path

from rich.console import Console

from storyboard.cli.composite.movie import create_movie
from storyboard.core.load.load import load_scene_graph

console = Console()


def composite_command(args):
    """Dispatch to composite subcommands."""
    if args.composite_command == "movie":
        return movie_command(args)
    else:
        console.print("[red]Error: No composite subcommand specified[/red]")
        console.print("Available subcommands: movie")
        return 1


def movie_command(args):
    """Create a movie from all generated scenes."""
    scene_folder: Path = Path(args.scene_folder)

    # Validate scene folder exists
    if not scene_folder.exists():
        console.print(f"[red]Error: Scene folder not found: {scene_folder}[/red]")
        return 1

    metadata_path: Path = scene_folder / "metadata.json"
    if not metadata_path.exists():
        console.print(f"[red]Error: metadata.json not found in {scene_folder}[/red]")
        console.print("Run 'storyboard generate' first to generate scenes")
        return 1

    # Load config from SDL file if provided
    config = None
    if args.input:
        sdl_path: Path = Path(args.input)
        if not sdl_path.exists():
            console.print(f"[red]Error: SDL file not found: {sdl_path}[/red]")
            return 1
        try:
            scene_graph = load_scene_graph(sdl_path, sdl_path.parent)
            config = scene_graph.config.composite.movie
        except Exception as e:
            console.print(f"[red]Error loading SDL config: {e}[/red]")
            return 1

    # Determine output path
    if args.output:
        output_path: Path = Path(args.output)
    else:
        default_name: str = config.output_filename if config else "movie.mp4"
        output_path = scene_folder / default_name

    # Override resolution if provided
    resolution: str = args.resolution if args.resolution else (
        config.resolution if config else "1920x1080"
    )

    console.print("[green]Creating movie...[/green]")
    console.print(f"  Scene folder: {scene_folder.absolute()}")
    console.print(f"  Output: {output_path.absolute()}")
    console.print(f"  Resolution: {resolution}")

    try:
        create_movie(
            scene_folder=scene_folder,
            output_path=output_path,
            config=config,
            resolution_override=resolution,
        )
        console.print(f"\n[green]Movie created successfully: {output_path}[/green]")
        return 0
    except Exception as e:
        console.print(f"\n[red]Error creating movie: {e}[/red]")
        return 1
