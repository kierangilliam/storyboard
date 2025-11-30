#!/usr/bin/env python3
"""Main CLI entry point for storyboard."""

import argparse
import sys

import os
from dotenv import load_dotenv

from storyboard.cli.composite.composite_command import composite_command
from storyboard.cli.image.image_command import image_command
from storyboard.cli.init.init_command import init_command
from storyboard.cli.generate.generate_command import generate_command
from storyboard.cli.serve.serve_command import serve_command
from storyboard.cli.tts.tts_command import tts_command


def main():
    """Main CLI dispatcher."""
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

    try:
        parser = argparse.ArgumentParser(
            prog="storyboard", description="Storyboard scene generation CLI tool"
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Init command
        init_parser = subparsers.add_parser(
            "init", help="Initialize a new storyboard project"
        )
        init_parser.add_argument(
            "--name",
            help="Project name (will be prompted if not provided)",
        )

        # Generate command
        generate_parser = subparsers.add_parser(
            "generate", help="Generate scene assets from storyboard main.yaml files"
        )
        generate_parser.add_argument(
            "--input",
            help="Path to main.yaml file (default: content/main.yaml)",
            default="content/main.yaml",
        )
        generate_parser.add_argument(
            "--output",
            default="./output",
            help="Output directory for generated scenes (default: ./output)",
        )
        generate_parser.add_argument(
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
        image_parser = subparsers.add_parser(
            "image", help="Generate images with Gemini"
        )
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

        # Serve command
        serve_parser = subparsers.add_parser(
            "serve", help="Start web server to view generated scenes"
        )
        serve_parser.add_argument(
            "--scene-folder",
            default="./output",
            help="Path to output directory containing metadata.json (default: ./output)",
        )
        serve_parser.add_argument(
            "--port",
            type=int,
            default=6767,
            help="Server port (default: 6767)",
        )

        # Update command
        update_parser = subparsers.add_parser(
            "update",
            help="Regenerate specific scene frame assets (bypasses cache by default)",
        )
        update_parser.add_argument(
            "selector",
            nargs="?",
            help=(
                "Frame selector: 'scene_id.frame_id', 'scene_id.frame_id.image', "
                "or 'scene_id.frame_id.tts'. "
                "If omitted, interactive mode will prompt for selection."
            ),
        )
        update_parser.add_argument(
            "--input",
            help="Path to main.yaml file (default: content/main.yaml)",
            default="content/main.yaml",
        )
        update_parser.add_argument(
            "--output",
            default="./output",
            help="Output directory (default: ./output)",
        )
        update_parser.add_argument(
            "--root-dir",
            help="Root directory for resolving relative paths in SDL (default: parent directory of input file)",
        )
        update_parser.add_argument(
            "--use-cache",
            action="store_true",
            help="Use cached assets if available (default: always regenerate)",
        )

        # Composite command
        composite_parser = subparsers.add_parser(
            "composite", help="Create composite videos from generated scenes"
        )
        composite_subparsers = composite_parser.add_subparsers(
            dest="composite_command", help="Composite subcommands"
        )

        movie_parser = composite_subparsers.add_parser(
            "movie", help="Create a movie from all scenes"
        )
        movie_parser.add_argument(
            "--scene-folder",
            required=True,
            help="Path to output directory containing metadata.json",
        )
        movie_parser.add_argument(
            "--output",
            help="Output path for movie file (default: output/movie.mp4)",
        )
        movie_parser.add_argument(
            "--resolution",
            help="Video resolution in WxH format (e.g., 1920x1080)",
        )
        movie_parser.add_argument(
            "--input",
            help="Path to SDL file for loading config (default: content/main.yaml)",
        )

        # Parse arguments
        args = parser.parse_args()

        # Dispatch to appropriate command
        if args.command == "init":
            return init_command(args)
        elif args.command == "generate":
            return generate_command(args)
        elif args.command == "tts":
            return tts_command(args)
        elif args.command == "image":
            return image_command(args)
        elif args.command == "serve":
            return serve_command(args)
        elif args.command == "update":
            from storyboard.cli.update.update_command import update_command

            return update_command(args)
        elif args.command == "composite":
            return composite_command(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main() or 0)
