"""Parallel scene generation orchestrator."""

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from storyboard.core.image.generate import (
    ImageGen,
    ImageModelDefinition,
    ImageModels,
    ImageTemplateContext,
    _compute_cache_hash,
    _render_template_parts,
)
from storyboard.core.image.optimize import to_webp
from storyboard.core.shapes import Frame, ImageTemplate, SceneGraph, StoryboardConfig
from storyboard.core.templating import render_template_string
from storyboard.core.tts.generate import (
    TTSGen,
    TTSModelDefinition,
    TTSModels,
    TTSTemplateContext,
    _compute_tts_cache_hash,
)
from storyboard.core.tts.optimize import optimize_audio

logger = logging.getLogger(__name__)


def _get_image_model_from_config(config: StoryboardConfig) -> ImageModelDefinition:
    """Convert config model reference to ImageModelDefinition."""
    model_ref = config.image.default_model
    if model_ref.vendor == "gemini":
        if model_ref.model == "gemini-3-pro-image-preview":
            return ImageModels.gemini("pro")
        elif model_ref.model == "gemini-2.5-flash-image":
            return ImageModels.gemini("flash")
    raise ValueError(f"Unsupported image model: {model_ref.vendor}/{model_ref.model}")


def _get_tts_model_from_config(config: StoryboardConfig) -> TTSModelDefinition:
    """Convert config model reference to TTSModelDefinition."""
    model_ref = config.tts.default_model
    if model_ref.vendor == "gemini":
        if model_ref.model == "gemini-2.5-flash-preview-tts":
            return TTSModels.gemini("flash")
    raise ValueError(f"Unsupported TTS model: {model_ref.vendor}/{model_ref.model}")


async def _retry_with_backoff(
    func,
    config: StoryboardConfig,
    *args,
    **kwargs,
):
    """Retry function with exponential backoff based on config."""
    retry_config = config.generation.retry

    if not retry_config.enabled:
        return await func(*args, **kwargs)

    last_exception = None
    for attempt in range(retry_config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < retry_config.max_attempts - 1:
                delay = retry_config.delay_seconds * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_config.max_attempts} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {retry_config.max_attempts} attempts failed. Last error: {e}"
                )

    raise last_exception


@dataclass
class AssetTask:
    """Represents a single asset generation task."""

    scene_id: str
    frame_id: str
    asset_type: Literal["image", "audio"]
    status: Literal["pending", "generating", "cached", "complete", "failed"] = "pending"
    hash: str | None = None
    cached: bool = False
    error: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    output_path: str | None = None

    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@dataclass
class FrameResult:
    """Result of generating assets for a single frame."""

    frame_id: str
    speaker: dict | None
    dialogue: str | None
    image_asset: dict
    audio_asset: dict | None
    template_used: str


@dataclass
class SceneResult:
    """Result of generating a complete scene."""

    scene_id: str
    scene_name: str
    frames: list[FrameResult]
    failed_assets: list[AssetTask] = field(default_factory=list)


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""

    def on_asset_start(self, asset: AssetTask) -> None:
        """Called when asset generation starts."""
        ...

    def on_asset_complete(self, asset: AssetTask) -> None:
        """Called when asset generation completes."""
        ...

    def on_asset_cached(self, asset: AssetTask) -> None:
        """Called when asset is found in cache."""
        ...

    def on_asset_error(self, asset: AssetTask, error: Exception) -> None:
        """Called when asset generation fails."""
        ...

    def on_scene_complete(self, scene_id: str) -> None:
        """Called when scene generation completes."""
        ...


class ParallelSceneGenerator:
    """Parallel scene generation orchestrator."""

    def __init__(
        self,
        scene_graph: SceneGraph,
        callback: ProgressCallback | None = None,
    ):
        self.scene_graph = scene_graph
        self.callback = callback
        self.config = scene_graph.config
        concurrent = self.config.generation.max_concurrent
        self.api_semaphore = asyncio.Semaphore(concurrent)

    async def generate_all_scenes(
        self,
        scene_ids: list[str],
        output_base_path: str | None = None,
    ) -> list[SceneResult]:
        """Generate all scenes in parallel."""
        base_path = (
            output_base_path
            if output_base_path is not None
            else f"{self.config.output.directory}/scenes"
        )
        tasks = [self.generate_scene(scene_id, base_path) for scene_id in scene_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scene_results = []
        for result in results:
            if isinstance(result, Exception):
                # Scene failed completely - log but continue
                logger.error(f"Scene generation failed: {result}")
            else:
                scene_results.append(result)

        return scene_results

    async def generate_scene(
        self, scene_id: str, output_base_path: str | None = None
    ) -> SceneResult:
        """Generate all assets for a scene in parallel."""
        base_path = (
            output_base_path
            if output_base_path is not None
            else f"{self.config.output.directory}/scenes"
        )
        # Find the scene
        scene = None
        for s in self.scene_graph.scenes:
            if s.id == scene_id:
                scene = s
                break

        if scene is None:
            raise ValueError(f"Scene not found: {scene_id}")

        # Create output directory
        scene_output_dir = Path(base_path) / scene_id
        scene_output_dir.mkdir(parents=True, exist_ok=True)

        # Generate all frames in parallel
        frame_tasks = [
            self.generate_frame_assets(frame, str(scene_output_dir))
            for frame in scene.frames
        ]
        frame_results = await asyncio.gather(*frame_tasks, return_exceptions=True)

        # Collect results and errors
        successful_frames = []
        failed_assets = []

        for result in frame_results:
            if isinstance(result, Exception):
                logger.error(f"Frame generation failed: {result}")
            else:
                frame_result, frame_failures = result
                successful_frames.append(frame_result)
                failed_assets.extend(frame_failures)

        # Notify callback
        if self.callback:
            self.callback.on_scene_complete(scene_id)

        return SceneResult(
            scene_id=scene.id,
            scene_name=scene.name,
            frames=successful_frames,
            failed_assets=failed_assets,
        )

    async def generate_frame_assets(
        self, frame: Frame, scene_output_path: str
    ) -> tuple[FrameResult, list[AssetTask]]:
        """Generate image and audio assets for a frame in parallel."""
        # Create frame-specific directory
        frame_output_dir = Path(scene_output_path) / frame.id
        frame_output_dir.mkdir(parents=True, exist_ok=True)

        # Find image template
        template = None
        template_id = frame.image.template
        for category_templates in self.scene_graph.assets.images.values():
            for tmpl in category_templates:
                if tmpl.id == template_id:
                    template = tmpl
                    break
            if template:
                break

        if template is None:
            raise ValueError(f"Image template not found: {template_id}")

        # Create asset tasks
        image_task = AssetTask(
            scene_id=frame.scene_id, frame_id=frame.id, asset_type="image"
        )

        audio_task = None
        tasks = [
            self._generate_image_asset(
                image_task, frame, template, str(frame_output_dir)
            )
        ]

        if frame.tts:
            audio_task = AssetTask(
                scene_id=frame.scene_id, frame_id=frame.id, asset_type="audio"
            )
            tasks.append(
                self._generate_audio_asset(audio_task, frame, str(frame_output_dir))
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        image_result = results[0]
        audio_result = results[1] if len(results) > 1 else None

        failed_assets = []

        if isinstance(image_result, Exception):
            image_task.status = "failed"
            image_task.error = str(image_result)
            failed_assets.append(image_task)
            raise image_result

        if audio_result and isinstance(audio_result, Exception):
            audio_task.status = "failed"
            audio_task.error = str(audio_result)
            failed_assets.append(audio_task)
            audio_result = None

        # Extract dialogue from TTS config for frame result (may not exist for all templates)
        dialogue = None
        if frame.tts:
            tts_data = frame.tts.model_dump()
            dialogue = tts_data.get("dialogue")

        # Build frame result
        frame_result = FrameResult(
            frame_id=frame.id,
            speaker=None,
            dialogue=dialogue,
            image_asset=image_result,
            audio_asset=audio_result,
            template_used=template_id,
        )

        return frame_result, failed_assets

    async def _generate_image_asset(
        self,
        task: AssetTask,
        frame: Frame,
        template: ImageTemplate,
        output_path: str,
    ) -> dict:
        """Generate a single image asset."""
        # Build context
        context_dict = frame.image.model_dump(exclude={"template"})
        context = ImageTemplateContext(**context_dict)

        # Check cache before generating
        model = _get_image_model_from_config(self.config)
        rendered_parts = _render_template_parts(template.parts, context)
        cache_hash = _compute_cache_hash(rendered_parts, model)

        cache_dir = self.config.output.cache.images
        cache_path = Path(cache_dir) / f"image_{cache_hash}.png"
        is_cached = cache_path.exists()

        task.hash = cache_hash
        task.cached = is_cached

        if is_cached:
            task.status = "cached"
            if self.callback:
                self.callback.on_asset_cached(task)
        else:
            task.status = "generating"
            task.start_time = time.time()
            if self.callback:
                self.callback.on_asset_start(task)

        try:
            # Use semaphore to limit concurrent API calls
            async with self.api_semaphore:
                timeout = self.config.generation.timeout_seconds
                result = await asyncio.wait_for(
                    _retry_with_backoff(
                        ImageGen.from_template,
                        self.config,
                        model=model,
                        template=template.parts,
                        context=context,
                        cache_directory=cache_dir,
                        use_cached=True,
                    ),
                    timeout=timeout,
                )

            task.end_time = time.time()
            task.status = "complete"

            # Convert to WebP with fixed filename if optimization is enabled
            if self.config.image.optimize.enabled:
                webp_path = to_webp(
                    result.output_path,
                    output_path=Path(output_path) / "image.webp",
                    quality=self.config.image.optimize.quality,
                )
            else:
                webp_path = Path(output_path) / "image.png"
                shutil.copy2(result.output_path, webp_path)

            task.output_path = str(webp_path)

            if self.callback:
                self.callback.on_asset_complete(task)

            output_format = "webp" if self.config.image.optimize.enabled else "png"
            return {
                "path": str(
                    Path(webp_path)
                    .resolve()
                    .relative_to(Path(output_path).resolve().parent.parent.parent)
                ),
                "hash": result.hash,
                "format": output_format,
            }

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            if self.callback:
                self.callback.on_asset_error(task, e)
            raise

    async def _generate_audio_asset(
        self,
        task: AssetTask,
        frame: Frame,
        frame_output_path: str,
    ) -> dict:
        """Generate a single audio asset using template system."""
        model = _get_tts_model_from_config(self.config)

        # Find TTS template
        template_id = frame.tts.template
        tts_template = None

        for category_templates in self.scene_graph.assets.tts.values():
            for tmpl in category_templates:
                if tmpl.id == template_id:
                    tts_template = tmpl
                    break
            if tts_template:
                break

        if tts_template is None:
            raise ValueError(f"TTS template not found: {template_id}")

        # Build context from frame.tts fields (excluding 'template')
        context_dict = frame.tts.model_dump(exclude={"template"})
        context = TTSTemplateContext(**context_dict)

        # Render template for cache hash computation
        voice_id = render_template_string(tts_template.voice_id, context_dict)
        prompt = render_template_string(tts_template.prompt, context_dict)

        cache_hash = _compute_tts_cache_hash(voice_id, prompt, model)
        cache_dir = self.config.output.cache.audio
        cache_path = Path(cache_dir) / f"tts_{cache_hash}.wav"
        is_cached = cache_path.exists()

        task.hash = cache_hash
        task.cached = is_cached

        if is_cached:
            task.status = "cached"
            if self.callback:
                self.callback.on_asset_cached(task)
        else:
            task.status = "generating"
            task.start_time = time.time()
            if self.callback:
                self.callback.on_asset_start(task)

        try:
            async with self.api_semaphore:
                timeout = self.config.generation.timeout_seconds
                result = await asyncio.wait_for(
                    _retry_with_backoff(
                        TTSGen.from_template,
                        self.config,
                        model,
                        tts_template,
                        context,
                        frame_output_path,
                        cache_dir,
                        "tts",
                        True,
                    ),
                    timeout=timeout,
                )

            task.end_time = time.time()
            task.status = "complete"

            # Optimize audio if enabled
            if self.config.tts.optimize.enabled:
                optimized_path = optimize_audio(
                    result.output_path,
                    output_path=Path(frame_output_path) / "tts.opus",
                    quality=self.config.tts.optimize.quality,
                )
                task.output_path = str(optimized_path)
                output_format = "opus"
                final_path = optimized_path
            else:
                task.output_path = result.output_path
                output_format = "wav"
                final_path = Path(result.output_path)

            if self.callback:
                self.callback.on_asset_complete(task)

            return {
                "path": str(
                    final_path.resolve().relative_to(
                        Path(frame_output_path).resolve().parent.parent.parent
                    )
                ),
                "hash": result.hash,
                "format": output_format,
            }

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            if self.callback:
                self.callback.on_asset_error(task, e)
            raise
