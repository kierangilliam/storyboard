#!/usr/bin/env python3
"""Main CLI entry point for storyboard."""

import argparse
import sys

from dotenv import load_dotenv

from storyboard.cli.image.image_command import image_command
from storyboard.cli.run.run_command import run_command
from storyboard.cli.tts.tts_command import tts_command

load_dotenv()


def main():
    """Main CLI dispatcher."""
    parser = argparse.ArgumentParser(
        prog="storyboard", description="Storyboard scene generation CLI tool"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser(
        "run", help="Generate scene assets from SDL files"
    )
    run_parser.add_argument(
        "--input",
        required=True,
        help="Path to SDL file",
    )
    run_parser.add_argument(
        "--output",
        default="./output/scenes",
        help="Output directory for generated scenes (default: ./output/scenes)",
    )
    run_parser.add_argument(
        "--root-dir",
        help="Root directory for resolving relative paths in SDL (default: parent directory of input file)",
    )

    # TTS command
    tts_parser = subparsers.add_parser("tts", help="Generate TTS audio with Gemini")
    tts_parser.add_argument(
        "--voice-id",
        required=True,
        help="Gemini voice name (e.g., 'Aoede', 'Charon')",
    )
    tts_parser.add_argument(
        "--style-instructions",
        required=True,
        help="Voice style prompt for the TTS model (e.g., 'Gruff and handsome man')",
    )
    tts_parser.add_argument(
        "--content",
        required=True,
        help="Text content to synthesize",
    )
    tts_parser.add_argument(
        "--output-path",
        required=True,
        help="Directory path for output file",
    )
    tts_parser.add_argument(
        "--output-name",
        required=True,
        help="Base filename without extension (e.g., 'dialogue')",
    )
    tts_parser.add_argument(
        "--cache-directory",
        default=".storyboard/generated/audio",
        help="Cache directory for generated audio files",
    )

    # Image command
    image_parser = subparsers.add_parser("image", help="Generate images with Gemini")
    image_parser.add_argument(
        "--prompt",
        required=True,
        help="Text prompt for image generation",
    )
    image_parser.add_argument(
        "--reference-photos",
        nargs="*",
        help="Optional paths to reference images",
    )
    image_parser.add_argument(
        "--model",
        default="pro",
        choices=["pro", "flash"],
        help="Model selection: 'pro' or 'flash' (default: pro)",
    )
    image_parser.add_argument(
        "--output",
        help="Optional output path (copies from cache to this location)",
    )
    image_parser.add_argument(
        "--webp",
        action="store_true",
        help="Convert output to WebP format",
    )
    image_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (always generate new image)",
    )
    image_parser.add_argument(
        "--cache-directory",
        default=".storyboard/generated/images",
        help="Cache directory for generated images",
    )

    # Parse arguments
    args = parser.parse_args()

    # Dispatch to appropriate command
    if args.command == "run":
        return run_command(args)
    elif args.command == "tts":
        return tts_command(args)
    elif args.command == "image":
        return image_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
