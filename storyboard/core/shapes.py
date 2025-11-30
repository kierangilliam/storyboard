from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from pydantic.functional_serializers import PlainSerializer


def _validate_non_whitespace_only(v: str) -> str:
    if not v.strip():
        raise ValueError("String cannot be only whitespace")
    return v


def _validate_path_format(v: str) -> str:
    if not v.strip():
        raise ValueError("Path cannot be empty")
    try:
        Path(v)
    except Exception as e:
        raise ValueError(f"Invalid path format: {v}") from e
    return v


NonEmptyStr = Annotated[str, Field(min_length=1), AfterValidator(_validate_non_whitespace_only)]
PathStr = Annotated[str, AfterValidator(_validate_path_format)]

# Type definitions for vendors, models, and voices
ImageVendor: TypeAlias = Literal["gemini"]
ImageModel: TypeAlias = Literal["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]

TTSVendor: TypeAlias = Literal["gemini"]
TTSModel: TypeAlias = Literal[
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-tts",
    "gemini-2.5-flash-lite-preview-tts",
]
TTSVoice: TypeAlias = Literal[
    "Aoede",
    "Kore",
    "Fenrir",
    "Enceladus",
    "Schedar",
    "Vindemiatrix",
]


class TTSConfig(BaseModel):
    model_config = {"extra": "allow"}
    template: NonEmptyStr


class TTSTemplate(BaseModel):
    id: NonEmptyStr
    voice_id: NonEmptyStr
    prompt: NonEmptyStr


class CharacterTTSConfig(BaseModel):
    style: NonEmptyStr
    voice: TTSVoice


class Character(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr
    reference_photo: PathStr
    tts: CharacterTTSConfig | None = None


class ImageTemplatePart(BaseModel):
    type: Literal["prompt", "image"]
    content: str
    key: str | None = Field(
        None,
        description="Variable key (e.g., 'character_reference')",
        pattern=r"^[a-zA-Z0-9_-]+$",
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_content_key_relationship(self):
        if self.key is None and (not self.content or not self.content.strip()):
            raise ValueError("content cannot be empty when key is not provided")
        return self


class ImageTemplate(BaseModel):
    id: NonEmptyStr
    parts: list[ImageTemplatePart] = Field(min_length=1)
    prompt: list[str | dict[str, str]] | None = None


class Assets(BaseModel):
    images: dict[str, list[ImageTemplate]] = Field(default_factory=dict)
    tts: dict[str, list[TTSTemplate]] = Field(default_factory=dict)


class ImageConfig(BaseModel):
    model_config = {"extra": "allow"}

    template: NonEmptyStr


class Frame(BaseModel):
    scene_id: NonEmptyStr
    id: NonEmptyStr
    image: ImageConfig
    tts: TTSConfig | None = None


class Scene(BaseModel):
    id: NonEmptyStr
    name: NonEmptyStr
    frames: list[Frame] = Field(default_factory=list)


class OutputCacheConfig(BaseModel):
    images: PathStr = ".storyboard/generated/images"
    audio: PathStr = ".storyboard/generated/audio"


class OutputConfig(BaseModel):
    directory: PathStr = "./output"
    cache: OutputCacheConfig = Field(default_factory=OutputCacheConfig)


class ImageModelRefConfig(BaseModel):
    vendor: ImageVendor
    model: ImageModel


class TTSModelRefConfig(BaseModel):
    vendor: TTSVendor
    model: TTSModel


class ImageOptimizeConfig(BaseModel):
    enabled: bool = True
    quality: int = Field(default=80, ge=1, le=100)


class ImageGenerationConfig(BaseModel):
    default_model: ImageModelRefConfig
    optimize: ImageOptimizeConfig = Field(default_factory=ImageOptimizeConfig)


class TTSOptimizeConfig(BaseModel):
    enabled: bool = True
    quality: int = Field(default=8, ge=1)


class TTSGenerationConfig(BaseModel):
    default_model: TTSModelRefConfig
    optimize: TTSOptimizeConfig = Field(default_factory=TTSOptimizeConfig)


class RetryConfig(BaseModel):
    enabled: bool = True
    max_attempts: int = Field(default=3, ge=1)
    delay_seconds: int = Field(default=2, ge=0)


class GenerationConfig(BaseModel):
    max_concurrent: int = Field(default=10, ge=1)
    timeout_seconds: int = Field(default=120, ge=1)
    retry: RetryConfig = Field(default_factory=RetryConfig)


class StoryboardConfig(BaseModel):
    output: OutputConfig = Field(default_factory=OutputConfig)
    image: ImageGenerationConfig = Field(
        default_factory=lambda: ImageGenerationConfig(
            default_model=ImageModelRefConfig(
                vendor="gemini", model="gemini-3-pro-image-preview"
            )
        )
    )
    tts: TTSGenerationConfig = Field(
        default_factory=lambda: TTSGenerationConfig(
            default_model=TTSModelRefConfig(
                vendor="gemini", model="gemini-2.5-flash-preview-tts"
            )
        )
    )
    generation: GenerationConfig = Field(default_factory=GenerationConfig)


class SceneGraph(BaseModel):
    characters: list[Character] = Field(default_factory=list)
    assets: Assets = Field(default_factory=Assets)
    scenes: list[Scene] = Field(default_factory=list)
    config: StoryboardConfig = Field(default_factory=StoryboardConfig)
    base_path: Annotated[Path, PlainSerializer(lambda x: str(x), return_type=str)] = Field(
        default=Path.cwd(), description="Base path for resolving relative file paths"
    )

    @field_validator("base_path", mode="before")
    @classmethod
    def validate_base_path(cls, v: Path | str) -> Path:
        if isinstance(v, str):
            return Path(v)
        return v
