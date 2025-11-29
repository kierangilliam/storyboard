#!/usr/bin/env python3
"""CLI script for generating TTS audio with Gemini 2.5 Pro."""

import argparse
import sys
from pathlib import Path

from storyboard.core.tts.generate import TTSGen, TTSModels, TTSVoiceConfig


def tts_command(args):
    """Main CLI entry point."""
    try:
        model = TTSModels.gemini()

        result = TTSGen.make(
            model=model,
            prompt=args.content,
            voice_id=args.voice_id,
            output_path=args.output_path,
            cache_directory=args.cache_directory,
            output_name=args.output_name,
        )

        print(f"Generated: {result.output_path}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Cache: {'HIT' if result.used_cached else 'MISS'}")
        print(f"Hash: {result.hash}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
