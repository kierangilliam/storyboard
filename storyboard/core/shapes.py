from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from pydantic.functional_serializers import PlainSerializer


def _validate_non_whitespace_only(v: str) -> str:
    if not v.strip():
        raise ValueError("String cannot be only whitespace")
    return v


NonEmptyStr = Annotated[str, Field(min_length=1), AfterValidator(_validate_non_whitespace_only)]

# Type definitions for vendors, models, and voices
ImageVendor = Literal["gemini"]
ImageModel = Literal["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]

TTSVendor = Literal["gemini"]
TTSModel = Literal[
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-tts",
    "gemini-2.5-flash-lite-preview-tts",
]
TTSVoice = Literal[
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
    reference_photo: NonEmptyStr
    tts: CharacterTTSConfig | None = None

    @field_validator("reference_photo")
    @classmethod
    def validate_reference_photo_path(cls, v: str) -> str:
        try:
            Path(v)
        except Exception as e:
            raise ValueError(f"Invalid path format: {v}") from e
        return v


class ImageTemplatePart(BaseModel):
    type: Literal["prompt", "image"]
    content: str
    key: str | None = Field(
        None, description="Variable key (e.g., 'character_reference')"
    )

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str | None) -> str | None:
        if v is not None:
            if not v or not v.strip():
                raise ValueError("key cannot be empty string")
            if not v.replace("_", "").replace("-", "").isalnum():
                raise ValueError(
                    f"key must contain only alphanumeric characters, hyphens, and underscores: '{v}'"
                )
        return v

    @model_validator(mode="after")
    def validate_content_key_relationship(self):
        # If there's a key, content can be empty (it's a template variable)
        # If there's no key, content must not be empty (it's a static value)
        if self.key is None and (not self.content or not self.content.strip()):
            raise ValueError("content cannot be empty when key is not provided")
        return self


class ImageTemplate(BaseModel):
    id: NonEmptyStr
    parts: list[ImageTemplatePart] = Field(default_factory=list)
    prompt: list[str | dict[str, str]] | None = None

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, v: list[ImageTemplatePart]) -> list[ImageTemplatePart]:
        if not v:
            raise ValueError("parts list cannot be empty")
        return v


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
    images: str = ".storyboard/generated/images"
    audio: str = ".storyboard/generated/audio"

    @field_validator("images", "audio")
    @classmethod
    def validate_path_string(cls, v: str) -> str:
        if not v:
            raise ValueError("Path cannot be empty")
        try:
            Path(v)
        except Exception as e:
            raise ValueError(f"Invalid path format: {v}") from e
        return v


class OutputConfig(BaseModel):
    directory: str = "./output"
    cache: OutputCacheConfig = Field(default_factory=OutputCacheConfig)

    @field_validator("directory")
    @classmethod
    def validate_directory_path(cls, v: str) -> str:
        if not v:
            raise ValueError("Directory path cannot be empty")
        try:
            Path(v)
        except Exception as e:
            raise ValueError(f"Invalid directory path format: {v}") from e
        return v


class ImageModelRefConfig(BaseModel):
    vendor: ImageVendor
    model: ImageModel


class TTSModelRefConfig(BaseModel):
    vendor: TTSVendor
    model: TTSModel


class ImageOptimizeConfig(BaseModel):
    enabled: bool = True
    quality: int = 80

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        if not 1 <= v <= 100:
            raise ValueError(f"quality must be between 1 and 100, got {v}")
        return v


class ImageGenerationConfig(BaseModel):
    default_model: ImageModelRefConfig
    optimize: ImageOptimizeConfig = Field(default_factory=ImageOptimizeConfig)


class TTSOptimizeConfig(BaseModel):
    enabled: bool = True
    quality: int = 8

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"quality must be at least 1, got {v}")
        return v


class TTSGenerationConfig(BaseModel):
    default_model: TTSModelRefConfig
    optimize: TTSOptimizeConfig = Field(default_factory=TTSOptimizeConfig)


class RetryConfig(BaseModel):
    enabled: bool = True
    max_attempts: int = 3
    delay_seconds: int = 2

    @field_validator("max_attempts")
    @classmethod
    def validate_max_attempts(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"max_attempts must be at least 1, got {v}")
        return v

    @field_validator("delay_seconds")
    @classmethod
    def validate_delay_seconds(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"delay_seconds cannot be negative, got {v}")
        return v


class GenerationConfig(BaseModel):
    max_concurrent: int = 10
    timeout_seconds: int = 120
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @field_validator("max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"max_concurrent must be at least 1, got {v}")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"timeout_seconds must be at least 1, got {v}")
        return v


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
