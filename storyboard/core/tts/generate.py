import asyncio
import hashlib
import os
import shutil
import wave
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from storyboard.core.shapes import TTSModel, TTSVendor, TTSVoice
from storyboard.core.templating import render_template_string


class TTSModelDefinition(BaseModel):
    vendor: TTSVendor
    model_variant: TTSModel
    audio_format: Literal["wav"] = "wav"
    sample_rate: int = 24000
    channels: int = 1
    sample_width: int = 2


class TTSModels:
    @staticmethod
    def gemini(model: Literal["flash", "pro", "lite"] = "flash") -> TTSModelDefinition:
        model_map = {
            "flash": "gemini-2.5-flash-preview-tts",
            "pro": "gemini-2.5-pro-preview-tts",
            "lite": "gemini-2.5-flash-lite-preview-tts",
        }
        return TTSModelDefinition(
            vendor="gemini",
            model_variant=model_map[model],
        )


class TTSVoiceConfig(BaseModel):
    voice_id: TTSVoice
    style_instructions: str = Field(..., description="Voice style prompt")


class TTSGenerationResult(BaseModel):
    content: str = Field(..., description="Text that was synthesized")
    voice_config: TTSVoiceConfig = Field(..., description="Voice configuration used")
    model: TTSModelDefinition = Field(..., description="Model used for generation")
    output_path: str = Field(..., description="Absolute path to generated WAV file")
    hash: str = Field(..., description="Content hash used for caching")
    used_cached: bool = Field(..., description="Whether result was from cache")
    duration_seconds: float = Field(
        ..., description="Duration of generated audio in seconds"
    )


class TTSTemplateContext(BaseModel):
    model_config = {"extra": "allow"}

    def get(self, key: str, default: str | None = None) -> str | None:
        return getattr(self, key, default)


def _compute_tts_cache_hash(
    voice_id: str,
    prompt: str,
    model: TTSModelDefinition,
) -> str:
    hash_components: list[str] = [
        model.vendor,
        model.model_variant,
        voice_id,
        prompt,
    ]
    combined = "".join(hash_components)
    full_hash = hashlib.sha256(combined.encode()).hexdigest()
    return full_hash[:16]


def _get_audio_duration(wav_path: str) -> float:
    """Extract duration from WAV file in seconds."""
    with wave.open(wav_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def _write_wave_file(
    filename: str,
    pcm: bytes,
    channels: int = 1,
    rate: int = 24000,
    sample_width: int = 2,
):
    """Write PCM audio data to a WAV file with proper headers."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


class TTSGen:
    @staticmethod
    async def from_template(
        model: TTSModelDefinition,
        template,
        context: TTSTemplateContext,
        output_path: str,
        cache_directory: str,
        output_name: str = "audio",
        use_cached: bool = True,
    ) -> TTSGenerationResult:
        """Render template and defer to make()."""
        context_dict = context.model_dump()
        voice_id = render_template_string(template.voice_id, context_dict)
        prompt = render_template_string(template.prompt, context_dict)

        return await TTSGen.make(
            model=model,
            prompt=prompt,
            voice_id=voice_id,
            output_path=output_path,
            cache_directory=cache_directory,
            output_name=output_name,
            use_cached=use_cached,
        )

    @staticmethod
    async def make(
        model: TTSModelDefinition,
        prompt: str,
        voice_id: str,
        output_path: str,
        cache_directory: str,
        output_name: str = "audio",
        use_cached: bool = True,
    ) -> TTSGenerationResult:
        """Generate speech audio from prompt and voice ID."""
        cache_hash = _compute_tts_cache_hash(voice_id, prompt, model)

        # Setup cache directory (content-based cache location)
        cache_dir = Path(cache_directory)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"tts_{cache_hash}.wav"

        # Setup output directory (final location for the file)
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{output_name}.wav"

        # Check cache
        if use_cached and cache_file.exists():
            duration = _get_audio_duration(str(cache_file))
            # Copy cached file to output location
            shutil.copy2(cache_file, output_file)
            return TTSGenerationResult(
                content=prompt,
                voice_config=TTSVoiceConfig(voice_id=voice_id, style_instructions=""),
                model=model,
                output_path=str(output_file.absolute()),
                hash=cache_hash,
                used_cached=True,
                duration_seconds=duration,
            )

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

        response = await client.aio.models.generate_content(
            model=model.model_variant,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_id,
                        )
                    )
                ),
            ),
        )

        audio_data = response.candidates[0].content.parts[0].inline_data.data
        _write_wave_file(str(cache_file), audio_data)
        shutil.copy2(cache_file, output_file)
        duration = _get_audio_duration(str(output_file))

        return TTSGenerationResult(
            content=prompt,
            voice_config=TTSVoiceConfig(voice_id=voice_id, style_instructions=""),
            model=model,
            output_path=str(output_file.absolute()),
            hash=cache_hash,
            used_cached=False,
            duration_seconds=duration,
        )

    @staticmethod
    def from_template_sync(
        model: TTSModelDefinition,
        template,
        context: TTSTemplateContext,
        output_path: str,
        cache_directory: str,
        output_name: str = "audio",
        use_cached: bool = True,
    ) -> TTSGenerationResult:
        return asyncio.run(
            TTSGen.from_template(
                model, template, context, output_path, cache_directory, output_name, use_cached
            )
        )

    @staticmethod
    def make_sync(
        model: TTSModelDefinition,
        prompt: str,
        voice_id: str,
        output_path: str,
        cache_directory: str,
        output_name: str = "audio",
        use_cached: bool = True,
    ) -> TTSGenerationResult:
        return asyncio.run(
            TTSGen.make(model, prompt, voice_id, output_path, cache_directory, output_name, use_cached)
        )
