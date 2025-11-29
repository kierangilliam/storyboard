from pathlib import Path

from PIL import Image as PILImage


def to_webp(
    input_path: str | Path,
    output_path: str | Path | None = None,
    quality: int = 90,
) -> Path:
    """Convert image to WebP format."""
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input image not found: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Input path is not a file: {input_file}")

    if output_path is None:
        output_file = input_file.with_suffix(".webp")
    else:
        output_file = Path(output_path)

    with PILImage.open(input_file) as img:
        img.save(output_file, "WEBP", quality=quality)

    return output_file
