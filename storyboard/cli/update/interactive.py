"""Interactive selection for update command."""

import sys
from typing import Literal

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from storyboard.core.shapes import SceneGraph

console = Console()


def interactive_select(
    scene_graph: SceneGraph,
) -> tuple[str, str, set[Literal["image", "audio"]]] | None:
    """Interactive selection of scene, frame, and asset types.

    Returns:
        Tuple of (scene_id, frame_id, asset_types) or None if cancelled
    """
    # Scene selection
    console.print()
    table = Table(title="Select Scene", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=6)
    table.add_column("Scene Name", style="bold")
    table.add_column("Scene ID", style="dim")
    table.add_column("Frames", justify="right", style="cyan")

    for idx, scene in enumerate(scene_graph.scenes, start=1):
        table.add_row(
            str(idx),
            scene.name,
            scene.id,
            str(len(scene.frames))
        )

    console.print(table)
    console.print()
    scene_input = Prompt.ask(
        "[bold yellow]Enter scene number or ID[/bold yellow]",
        default="q"
    ).strip()

    if scene_input.lower() == "q":
        return None

    # Resolve scene
    selected_scene = None
    try:
        scene_idx = int(scene_input)
        if 1 <= scene_idx <= len(scene_graph.scenes):
            selected_scene = scene_graph.scenes[scene_idx - 1]
    except ValueError:
        # Try string ID lookup
        for scene in scene_graph.scenes:
            if scene.id == scene_input:
                selected_scene = scene
                break

    if not selected_scene:
        console.print(f"[red]Error: Scene not found: '{scene_input}'[/red]")
        return None

    # Frame selection
    console.print()
    frame_table = Table(
        title=f"Select Frame from: [bold]{selected_scene.name}[/bold]",
        show_header=True,
        header_style="bold cyan"
    )
    frame_table.add_column("#", style="dim", width=6)
    frame_table.add_column("Frame ID", style="bold")
    frame_table.add_column("Available Assets", justify="left")

    for idx, frame in enumerate(selected_scene.frames, start=1):
        assets = []
        if frame.image:
            assets.append("[cyan]image[/cyan]")
        if frame.tts:
            assets.append("[yellow]tts[/yellow]")

        assets_str = ", ".join(assets) if assets else "[dim]none[/dim]"
        frame_table.add_row(
            str(idx),
            frame.id,
            assets_str
        )

    console.print(frame_table)
    console.print()
    frame_input = Prompt.ask(
        "[bold yellow]Enter frame number or ID[/bold yellow]",
        default="q"
    ).strip()

    if frame_input.lower() == "q":
        return None

    # Resolve frame
    selected_frame = None
    try:
        frame_idx = int(frame_input)
        if 1 <= frame_idx <= len(selected_scene.frames):
            selected_frame = selected_scene.frames[frame_idx - 1]
    except ValueError:
        # Try string ID lookup
        for frame in selected_scene.frames:
            if frame.id == frame_input:
                selected_frame = frame
                break

    if not selected_frame:
        console.print(f"[red]Error: Frame not found: '{frame_input}'[/red]")
        return None

    # Asset type selection
    console.print()

    # Build available options based on what the frame has
    has_image = selected_frame.image is not None
    has_tts = selected_frame.tts is not None

    if not has_image and not has_tts:
        console.print("[red]Error: Frame has no assets to regenerate.[/red]")
        return None

    asset_table = Table(
        title="Select Assets to Regenerate",
        show_header=True,
        header_style="bold cyan"
    )
    asset_table.add_column("#", style="dim", width=6)
    asset_table.add_column("Asset Type", style="bold")
    asset_table.add_column("Available", justify="center", style="dim")

    option_map = {}
    option_num = 1

    # Only show "both" if both are available
    if has_image and has_tts:
        asset_table.add_row(str(option_num), "Both image and audio", "[green]✓[/green]")
        option_map[str(option_num)] = {"image", "audio"}
        option_num += 1

    # Show image option if available
    if has_image:
        asset_table.add_row(str(option_num), "Image only", "[cyan]✓[/cyan]")
        option_map[str(option_num)] = {"image"}
        option_num += 1

    # Show audio option if available
    if has_tts:
        asset_table.add_row(str(option_num), "Audio/TTS only", "[yellow]✓[/yellow]")
        option_map[str(option_num)] = {"audio"}
        option_num += 1

    console.print(asset_table)
    console.print()

    valid_options = list(option_map.keys())
    max_option = max(int(k) for k in valid_options)

    asset_input = Prompt.ask(
        f"[bold yellow]Enter selection (1-{max_option})[/bold yellow]",
        default="q"
    ).strip()

    if asset_input.lower() == "q":
        return None

    # Resolve asset types from option map
    if asset_input in option_map:
        asset_types = option_map[asset_input]
    else:
        console.print(f"[red]Error: Invalid selection: '{asset_input}'. Please choose from {', '.join(valid_options)}[/red]")
        return None

    # Show confirmation panel
    console.print()
    confirmation_text = Text()
    confirmation_text.append("Scene: ", style="bold")
    confirmation_text.append(f"{selected_scene.name}", style="cyan")
    confirmation_text.append(f" ({selected_scene.id})\n", style="dim")
    confirmation_text.append("Frame: ", style="bold")
    confirmation_text.append(f"{selected_frame.id}\n", style="cyan")
    confirmation_text.append("Assets: ", style="bold")
    confirmation_text.append("/".join(sorted(asset_types)), style="yellow")

    panel = Panel(
        confirmation_text,
        title="[bold green]✓ Selection Confirmed[/bold green]",
        border_style="green"
    )
    console.print(panel)

    return selected_scene.id, selected_frame.id, asset_types
