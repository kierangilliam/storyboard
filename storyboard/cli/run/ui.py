"""Terminal UI for generation pipeline using Rich library."""

import time
from dataclasses import dataclass, field
from typing import Literal

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from storyboard.cli.run.parallel_generator import AssetTask

SHOW_FRAMES_STATUSES = {"in_progress", "failed"}


@dataclass
class AssetState:
    """State of a single asset."""

    asset_type: Literal["image", "audio"]
    status: Literal["pending", "generating", "cached", "complete", "failed"]
    hash: str | None = None
    cached: bool = False
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class FrameState:
    """State of a frame's assets."""

    frame_id: str
    image: AssetState = field(default_factory=lambda: AssetState("image", "pending"))
    audio: AssetState | None = None


@dataclass
class SceneState:
    """State of a scene's generation."""

    scene_id: str
    scene_name: str
    frame_count: int
    status: Literal["pending", "in_progress", "complete", "failed"] = "pending"
    frames: dict[str, FrameState] = field(default_factory=dict)


class TerminalUI:
    """Rich-based terminal UI for generation progress."""

    def __init__(self, sdl_file: str, total_scenes: int):
        self.sdl_file = sdl_file
        self.total_scenes = total_scenes
        self.start_time = time.time()

        self.console = Console()
        self.scenes: dict[str, SceneState] = {}
        self.completed_count = 0
        self.failed_count = 0

        self.live: Live | None = None

    def initialize_scene(
        self,
        scene_id: str,
        scene_name: str,
        frame_ids: list[str],
        has_audio: dict[str, bool] | None = None,
    ) -> None:
        """Initialize a scene with its frames.

        Args:
            scene_id: Scene identifier
            scene_name: Scene name
            frame_ids: List of frame IDs in the scene
            has_audio: Dict mapping frame_id to whether it has audio (default: None means no audio for any frame)
        """
        has_audio = has_audio or {}
        frames = {
            fid: FrameState(
                frame_id=fid,
                audio=AssetState("audio", "pending")
                if has_audio.get(fid, False)
                else None,
            )
            for fid in frame_ids
        }
        self.scenes[scene_id] = SceneState(
            scene_id=scene_id,
            scene_name=scene_name,
            frame_count=len(frame_ids),
            status="pending",
            frames=frames,
        )

    def start(self) -> None:
        """Start the live display."""
        self.live = Live(
            self._create_layout(), console=self.console, refresh_per_second=4
        )
        self.live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self.live:
            self.live.stop()

    def on_asset_start(self, asset: AssetTask) -> None:
        """Handle asset generation start."""
        scene = self.scenes.get(asset.scene_id)
        if not scene:
            return

        scene.status = "in_progress"
        frame = scene.frames.get(asset.frame_id)
        if not frame:
            return

        if asset.asset_type == "image":
            frame.image.status = "generating"
        elif frame.audio:
            frame.audio.status = "generating"

        self._update_display()

    def on_asset_cached(self, asset: AssetTask) -> None:
        """Handle asset cache hit."""
        scene = self.scenes.get(asset.scene_id)
        if not scene:
            return

        scene.status = "in_progress"
        frame = scene.frames.get(asset.frame_id)
        if not frame:
            return

        if asset.asset_type == "image":
            frame.image.status = "cached"
            frame.image.cached = True
            frame.image.hash = asset.hash
        elif frame.audio:
            frame.audio.status = "cached"
            frame.audio.cached = True
            frame.audio.hash = asset.hash

        self._update_display()

    def on_asset_complete(self, asset: AssetTask) -> None:
        """Handle asset generation completion."""
        scene = self.scenes.get(asset.scene_id)
        if not scene:
            return

        frame = scene.frames.get(asset.frame_id)
        if not frame:
            return

        if asset.asset_type == "image":
            frame.image.status = "complete"
            frame.image.cached = asset.cached
            frame.image.hash = asset.hash
            frame.image.duration_ms = asset.duration_ms()
        elif frame.audio:
            frame.audio.status = "complete"
            frame.audio.cached = asset.cached
            frame.audio.hash = asset.hash
            frame.audio.duration_ms = asset.duration_ms()

        self._update_display()

    def on_asset_error(self, asset: AssetTask, error: Exception) -> None:
        """Handle asset generation error."""
        scene = self.scenes.get(asset.scene_id)
        if not scene:
            return

        frame = scene.frames.get(asset.frame_id)
        if not frame:
            return

        if asset.asset_type == "image":
            frame.image.status = "failed"
            frame.image.error = str(error)
        elif frame.audio:
            frame.audio.status = "failed"
            frame.audio.error = str(error)

        self._update_display()

    def on_scene_complete(self, scene_id: str) -> None:
        """Handle scene completion."""
        scene = self.scenes.get(scene_id)
        if not scene:
            return

        # Check if any assets failed
        has_failures = False
        for frame in scene.frames.values():
            if frame.image.status == "failed":
                has_failures = True
            if frame.audio and frame.audio.status == "failed":
                has_failures = True

        if has_failures:
            scene.status = "failed"
            self.failed_count += 1
        else:
            scene.status = "complete"
            self.completed_count += 1

        self._update_display()

    def _update_display(self) -> None:
        """Update the live display."""
        if self.live:
            self.live.update(self._create_layout())

    def _create_layout(self) -> Panel:
        """Create the full layout."""
        header = self._create_header()

        scene_content = []
        for scene in self.scenes.values():
            scene_content.append(self._create_expanded_scene(scene))

        content = Text()
        content.append(header)
        content.append("\n\n")

        for i, scene_text in enumerate(scene_content):
            if i > 0:
                content.append("\n")
            content.append(scene_text)

        return Panel(content, title="Scene Generation Progress", border_style="blue")

    def _create_header(self) -> Text:
        """Create the header text."""
        elapsed = time.time() - self.start_time
        text = Text()
        text.append(f"SDL File: {self.sdl_file}\n", style="dim")
        text.append(
            f"Total Scenes: {self.total_scenes}  |  "
            f"Completed: {self.completed_count}  |  "
            f"Failed: {self.failed_count}\n",
            style="bold",
        )
        text.append(f"Elapsed: {elapsed:.1f}s", style="dim")
        return text

    def _create_expanded_scene(self, scene: SceneState) -> Text:
        """Create expanded view for scene."""
        text = Text()

        if scene.status == "complete":
            text.append("✓ ", style="green bold")
            text.append(f"{scene.scene_name}", style="green bold")
            text.append(f" ({scene.frame_count} frames)", style="dim")
        elif scene.status == "in_progress":
            text.append("⏳ ", style="yellow bold")
            text.append(f"{scene.scene_name}\n", style="yellow bold")
        elif scene.status == "failed":
            text.append("✗ ", style="red bold")
            text.append(f"{scene.scene_name}\n", style="red bold")
        else:
            text.append("○ ", style="dim")
            text.append(f"{scene.scene_name}\n", style="dim")

        if scene.status in SHOW_FRAMES_STATUSES:
            for frame in scene.frames.values():
                text.append("  ")
                text.append(self._format_frame(frame))
                text.append("\n")

        return text

    def _format_frame(self, frame: FrameState) -> Text:
        """Format a single frame's assets."""
        text = Text()
        text.append(f"├─ {frame.frame_id}\n")

        # Image asset
        text.append("  │  ├─ ")
        text.append(self._format_asset(frame.image, "Image"))
        text.append("\n")

        # Audio asset (if present)
        if frame.audio:
            text.append("  │  └─ ")
            text.append(self._format_asset(frame.audio, "Audio"))
        else:
            text.append("  │  └─ ")
            text.append("○ Audio: (no dialogue)", style="dim")

        return text

    def _format_asset(self, asset: AssetState, label: str) -> Text:
        """Format a single asset status."""
        text = Text()

        if asset.status == "complete":
            text.append("■ ", style="green")
            cached_label = "(cached)" if asset.cached else "(generated)"
            text.append(f"{label}: ", style="green")
            text.append(f"{asset.hash or 'unknown'} {cached_label}", style="dim")
        elif asset.status == "cached":
            text.append("■ ", style="yellow")
            text.append(f"{label}: ", style="yellow")
            text.append(f"{asset.hash or 'unknown'} (cached)", style="dim")
        elif asset.status == "generating":
            text.append("◐ ", style="blue")
            text.append(f"{label}: Generating...", style="blue")
        elif asset.status == "failed":
            text.append("✗ ", style="red")
            text.append(f"{label}: FAILED", style="red")
            if asset.error:
                text.append(f" - {asset.error[:50]}...", style="red dim")
        else:  # pending
            text.append("○ ", style="dim")
            text.append(f"{label}: Pending...", style="dim")

        return text
