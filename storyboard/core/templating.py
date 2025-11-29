"""Shared templating utilities for string interpolation."""

import json
import re
from typing import Any


def render_template_string(template_str: str, context: dict[str, Any] | Any) -> str:
    """Render template string by replacing {$variable} with context values.

    Supports:
    - Simple variables: {$variable}
    - Nested attributes: {$character.tts.voice}
    - JSON string parsing in context values
    """
    result = template_str

    # Convert Pydantic models to dict
    if hasattr(context, 'model_dump'):
        context = context.model_dump()

    # Parse any JSON strings in the context (from reference resolution)
    parsed_context = {}
    for key, value in context.items():
        if isinstance(value, str) and value.startswith("{"):
            try:
                parsed_context[key] = json.loads(value)
            except json.JSONDecodeError:
                parsed_context[key] = value
        else:
            parsed_context[key] = value

    # Find all {$variable} patterns
    pattern = r"\{\$([^}]+)\}"
    matches = re.findall(pattern, template_str)

    for var_path in matches:
        var_path = var_path.strip()

        # Support nested attribute access like character.tts.voice
        value = parsed_context
        for part in var_path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)

            if value is None:
                raise ValueError(
                    f"Missing required template variable: '{var_path}'. "
                    f"Available: {list(parsed_context.keys())}"
                )

        # Replace the variable in the template
        result = result.replace(f"{{${var_path}}}", str(value))

    return result
