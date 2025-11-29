#!/usr/bin/env python3
"""CLI script for generating images with Gemini."""

import shutil
import sys

from storyboard.core.image.generate import ImageGen, ImageModels, ImageTemplatePart
from storyboard.core.image.optimize import to_webp


def image_command(args):
    """Main CLI entry point."""
    try:
        # Build parts from prompt and reference photos
        parts: list[ImageTemplatePart] = []

        # Add reference photos first
        if args.reference_photos:
            for ref_photo in args.reference_photos:
                parts.append(ImageTemplatePart(type="image", content=ref_photo))

        # Add prompt
        parts.append(ImageTemplatePart(type="prompt", content=args.prompt))

        # Generate image
        result = ImageGen.make_sync(
            model=ImageModels.gemini(args.model),
            parts=parts,
            cache_directory=args.cache_directory,
            use_cached=not args.no_cache,
        )

        output_path = result.output_path

        # Convert to WebP if requested
        if args.webp:
            output_path = str(to_webp(output_path))

        # Copy to custom location if specified
        if args.output:
            shutil.copy(output_path, args.output)
            output_path = args.output

        print(f"Image: {output_path}")
        print(f"Cached: {result.used_cached}")
        print(f"Hash: {result.hash}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
