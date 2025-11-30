#!/usr/bin/env python3
"""CLI command to serve generated scenes via web interface."""

from pathlib import Path

from rich.console import Console

from storyboard.cli.serve.server import start_server

console = Console()


def serve_command(args):
    scene_folder: Path = Path(args.scene_folder)

    if not scene_folder.exists():
        console.print(f"[red]Error: Scene folder not found: {scene_folder}[/red]")
        return 1

    metadata_path: Path = scene_folder / "metadata.json"
    if not metadata_path.exists():
        console.print(
            f"[red]Error: metadata.json not found in {scene_folder}[/red]"
        )
        return 1

    console.print("[green]Starting server...[/green]")
    console.print(f"  Scene folder: {scene_folder.absolute()}")
    console.print(f"  Port: {args.port}")
    console.print(f"\n[blue]Open in browser:[/blue] http://localhost:{args.port}")
    console.print("\nPress Ctrl+C to stop the server")

    try:
        start_server(scene_folder=scene_folder, port=args.port)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
        return 0
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"[red]Error: Port {args.port} is already in use[/red]")
            console.print("Try a different port with --port")
        else:
            console.print(f"[red]Error starting server: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
