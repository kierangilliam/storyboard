We're writing a system that generates content based on a scene description language (SDL) written in YAML.

See example/content/main.yaml.

We use this SDL to then generate images and TTS audio for our characters. This generation is provided by Gemini.

This SDL specifies characters that have their own voice description and visible character attributes. This metadata is used to generating audio files.

## Tests

Tests are located in `./storyboard/tests`.
Extend tests when appropriate.
Tests should be minimal and readable. We don't want unneccessary duplicate tests.
Run all tests with `just test`.

## Code conventions

Avoid verbose Python docstring comments. Especially avoid self-obvious comments.

Bad:

```
def _compute_cache_hash(
    parts: list[ImageTemplatePart], model: ImageModelDefinition
) -> str:
    """Compute content-based cache hash from rendered parts.

    Args:
        parts: List of rendered template parts (with variables filled in)
        model: Model definition

    Returns:
        12-character hash string for cache key
    """
```

Good:
```
def _compute_cache_hash(
    parts: list[ImageTemplatePart], model: ImageModelDefinition
) -> str:
    """Compute content-based cache hash from rendered parts."""
```

Bad:
```
def _compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file contents."""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
```

Good:
```
def _compute_file_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
```

Avoid bare type annotations.

Bad:
```
rendered_parts = []
```

Good:
```
rendered_parts: list[ImageTemplatePart] = []
```
