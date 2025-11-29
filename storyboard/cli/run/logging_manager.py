"""JSON-based structured logger for tracking asset generation events."""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(str, Enum):
    INFO = "INFO"
    ERROR = "ERROR"
    WARNING = "WARNING"


class StructuredLogger:
    """JSON logger for generation pipeline events."""

    def __init__(self, log_dir: str = ".storyboard/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{timestamp}.log"

    def log(self, level: LogLevel, **data: Any) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            **data,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_asset_start(
        self,
        scene_id: str,
        frame_id: str,
        asset_type: str,
        cached: bool = False,
    ) -> None:
        self.log(
            LogLevel.INFO,
            event="asset_start",
            scene_id=scene_id,
            frame_id=frame_id,
            asset_type=asset_type,
            cached=cached,
        )

    def log_asset_complete(
        self,
        scene_id: str,
        frame_id: str,
        asset_type: str,
        cached: bool,
        duration_ms: float,
        hash: str,
        output_path: str,
    ) -> None:
        self.log(
            LogLevel.INFO,
            event="asset_complete",
            scene_id=scene_id,
            frame_id=frame_id,
            asset_type=asset_type,
            status="complete",
            cached=cached,
            duration_ms=duration_ms,
            hash=hash,
            output_path=output_path,
        )

    def log_asset_error(
        self,
        scene_id: str,
        frame_id: str,
        asset_type: str,
        error_type: str,
        error_message: str,
    ) -> None:
        self.log(
            LogLevel.ERROR,
            event="asset_error",
            scene_id=scene_id,
            frame_id=frame_id,
            asset_type=asset_type,
            status="failed",
            error_type=error_type,
            error_message=error_message,
        )

    def log_scene_complete(self, scene_id: str, frame_count: int) -> None:
        self.log(
            LogLevel.INFO,
            event="scene_complete",
            scene_id=scene_id,
            frame_count=frame_count,
        )

    def log_generation_start(self, sdl_file: str, scene_count: int) -> None:
        self.log(
            LogLevel.INFO,
            event="generation_start",
            sdl_file=sdl_file,
            scene_count=scene_count,
        )

    def log_generation_complete(
        self, total_scenes: int, failed_scenes: int, duration_s: float
    ) -> None:
        self.log(
            LogLevel.INFO,
            event="generation_complete",
            total_scenes=total_scenes,
            successful_scenes=total_scenes - failed_scenes,
            failed_scenes=failed_scenes,
            duration_s=duration_s,
        )
