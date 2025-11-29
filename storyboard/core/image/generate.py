import asyncio
import hashlib
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from storyboard.core.shapes import ImageModel, ImageVendor

MIME_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


class UnsupportedImageFileType(Exception):
    """Raised when an image file type is not supported."""


class ImagePrompt(BaseModel):
    """A complete image prompt with text and reference images."""

    prompt: str = Field(..., description="Text prompt for image generation")
    images: list[str] = Field(
        default_factory=list, description="List of reference image paths"
    )


class ImageModelDefinition(BaseModel):
    vendor: ImageVendor
    model: ImageModel


class ImageModels:
    @staticmethod
    def gemini(model: Literal["pro", "flash"] = "pro") -> ImageModelDefinition:
        model_variant: ImageModel = (
            "gemini-3-pro-image-preview" if model == "pro" else "gemini-2.5-flash-image"
        )
        return ImageModelDefinition(
            vendor="gemini",
            model=model_variant,
        )


class ImageGenerationResult(BaseModel):
    prompt: str = Field(..., description="The final rendered prompt used")
    reference_photos: list[str] = Field(
        default_factory=list, description="List of reference photo paths used"
    )
    model: ImageModelDefinition = Field(..., description="Model used for generation")
    output_path: str = Field(..., description="Absolute path to generated image")
    hash: str = Field(..., description="Content hash used for caching")
    used_cached: bool = Field(..., description="Whether result was from cache")
    template_context: dict[str, str] = Field(
        default_factory=dict,
        description="Template context used (if generated from template)",
    )


class ImageTemplatePart(BaseModel):
    type: Literal["prompt", "image"]
    content: str = Field(..., description="Prompt text or image path")
    key: str | None = Field(
        None, description="Variable key for substitution (e.g., 'character_reference')"
    )


class ImageTemplateContext(BaseModel):
    model_config = {"extra": "allow"}

    def get(self, key: str, default: str | None = None) -> str | None:
        return getattr(self, key, default)


def _smart_join_prompt_parts(parts: list[str]) -> str:
    if not parts:
        return ""

    if len(parts) == 1:
        return parts[0]

    result: list[str] = [parts[0]]

    for i in range(1, len(parts)):
        prev = result[-1]
        curr = parts[i]

        # Check if we should add a space before current part
        needs_space = True

        # No space if previous ends with space
        if prev and prev[-1].isspace():
            needs_space = False
        # No space if current starts with space
        elif curr and curr[0].isspace():
            needs_space = False
        # No space if previous ends with opening punctuation or current starts with closing/separator punctuation
        elif prev and prev[-1] in "'\"([":
            needs_space = False
        elif curr and curr[0] in "'\")].,;:!?":
            needs_space = False

        if needs_space:
            result.append(" ")
        result.append(curr)

    return "".join(result)


class ImageGen:
    @staticmethod
    async def from_template(
        model: ImageModelDefinition,
        template: list[ImageTemplatePart],
        context: ImageTemplateContext,
        cache_directory: str,
        use_cached: bool = True,
    ) -> ImageGenerationResult:
        rendered_parts = _render_template_parts(template, context)
        return await ImageGen.make(
            model=model,
            parts=rendered_parts,
            cache_directory=cache_directory,
            use_cached=use_cached,
        )

    @staticmethod
    async def make(
        model: ImageModelDefinition,
        parts: list[ImageTemplatePart],
        cache_directory: str,
        use_cached: bool = True,
    ) -> ImageGenerationResult:
        # Extract prompt and reference photos for metadata (order doesn't matter here)
        prompt_parts = []
        reference_photos = []

        for part in parts:
            if part.type == "prompt" and part.content:
                prompt_parts.append(part.content)
            elif part.type == "image" and part.content:
                reference_photos.append(part.content)

        # Build final prompt for metadata
        prompt = _smart_join_prompt_parts(prompt_parts)

        # Compute cache hash (content-based, preserves order)
        cache_hash = _compute_cache_hash(parts, model)

        # Setup output directory
        output_dir = Path(cache_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Output file path (PNG only - no WebP conversion)
        output_file = output_dir / f"image_{cache_hash}.png"

        # Check cache
        if use_cached and output_file.exists():
            print(f"\tCache hit: {output_file}")
            return ImageGenerationResult(
                prompt=prompt,
                reference_photos=reference_photos,
                model=model,
                output_path=str(output_file.absolute()),
                hash=cache_hash,
                used_cached=True,
                template_context={},
            )

        print(f"Generating image (Cache miss): {output_file}")

        client = genai.Client()
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )

        # Prepare contents in the same order as parts
        contents = []
        for part in parts:
            if part.type == "prompt" and part.content:
                # Add prompt text
                contents.append(part.content)
            elif part.type == "image" and part.content:
                # Load and add image data
                with open(part.content, "rb") as f:
                    image_data = f.read()

                # Determine mime type
                path = Path(part.content)
                ext = path.suffix.lower()
                mime_type = MIME_TYPE_MAP.get(ext)
                if mime_type is None:
                    raise UnsupportedImageFileType(
                        f"Unsupported image file type: {ext}. "
                        f"Supported types: {', '.join(MIME_TYPE_MAP.keys())}"
                    )

                contents.append(
                    types.Part.from_bytes(data=image_data, mime_type=mime_type)
                )

        response = await client.aio.models.generate_content(
            model=model.model,
            contents=contents,
            config=config,
        )
        if response is None or response.parts is None:
            raise ValueError("Unexpected None response")

        image = None
        for part in response.parts:
            if part.as_image() is not None:
                image = part.as_image()
                break
        if image is None:
            raise ValueError("No image generated in response")

        image.save(str(output_file))

        return ImageGenerationResult(
            prompt=prompt,
            reference_photos=reference_photos,
            model=model,
            output_path=str(output_file.absolute()),
            hash=cache_hash,
            used_cached=False,
            template_context={},
        )

    @staticmethod
    def from_template_sync(
        model: ImageModelDefinition,
        template: list[ImageTemplatePart],
        context: ImageTemplateContext,
        cache_directory: str,
        use_cached: bool = True,
    ) -> ImageGenerationResult:
        return asyncio.run(
            ImageGen.from_template(
                model, template, context, cache_directory, use_cached
            )
        )

    @staticmethod
    def make_sync(
        model: ImageModelDefinition,
        parts: list[ImageTemplatePart],
        cache_directory: str,
        use_cached: bool = True,
    ) -> ImageGenerationResult:
        return asyncio.run(ImageGen.make(model, parts, cache_directory, use_cached))


def _compute_file_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _compute_cache_hash(
    parts: list[ImageTemplatePart], model: ImageModelDefinition
) -> str:
    hash_components = [model.model]

    # Process parts in order to preserve sequence
    for part in parts:
        if part.type == "prompt" and part.content:
            # Add prompt text directly
            hash_components.append(part.content)
        elif part.type == "image" and part.content:
            # Add content hash of image file
            if Path(part.content).exists():
                file_hash = _compute_file_hash(part.content)
                hash_components.append(file_hash)

    combined = "".join(hash_components)
    full_hash = hashlib.sha256(combined.encode()).hexdigest()
    return full_hash[:16]


def _render_template_parts(
    template: list[ImageTemplatePart], context: ImageTemplateContext
) -> list[ImageTemplatePart]:
    rendered_parts: list[ImageTemplatePart] = []

    for part in template:
        # If part has a key, substitute from context
        if part.key:
            value = context.get(part.key)
            if value is None:
                raise ValueError(
                    f"Missing required template variable: '{part.key}'. "
                    f"Available: {list(context.model_dump().keys())}"
                )
            content = str(value)
            # Create new part with rendered content and no key
            rendered_part = ImageTemplatePart(
                type=part.type,
                content=content,
                key=None,  # Rendered, no longer has a variable
            )
        else:
            # Static content - keep as is
            rendered_part = part

        # Verify image files exist
        if rendered_part.type == "image" and rendered_part.content:
            if not Path(rendered_part.content).exists():
                raise FileNotFoundError(
                    f"Reference image not found: {rendered_part.content}"
                )

        rendered_parts.append(rendered_part)

    return rendered_parts
