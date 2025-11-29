from pathlib import Path
from typing import Any

from storyboard.core.load.config import KNOWN_IMAGE_EXTENSIONS
from storyboard.core.shapes import Character, Frame, ImageTemplate, SceneGraph


class ValidationError(Exception):
    """Exception raised when SceneGraph validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = "SceneGraph validation failed:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(message)


def validate_scene_graph(
    scene_graph: SceneGraph, base_path: Path | None = None
) -> None:
    if base_path is None:
        base_path = Path.cwd()

    errors: list[str] = []

    # Validate character reference photos
    errors.extend(_validate_character_references(scene_graph.characters, base_path))

    # Validate image templates
    errors.extend(_validate_image_templates(scene_graph.assets.images, base_path))

    # Validate frame references
    errors.extend(_validate_frame_references(scene_graph, base_path))

    if errors:
        raise ValidationError(errors)


def _is_potential_file_path(value: str) -> bool:
    """Check if a string looks like a file path."""
    if not isinstance(value, str):
        return False

    # Skip entity references
    if value.startswith("@"):
        return False

    # Skip template variables
    if "{" in value and "}" in value:
        return False

    # Skip multiline strings (file paths should be single line)
    if "\n" in value or "\r" in value:
        return False

    # Check if it has a path separator or ends with a known extension
    return "/" in value or any(value.endswith(ext) for ext in KNOWN_IMAGE_EXTENSIONS)


def _validate_file_path(
    path: str, context: str, base_path: Path, error_suffix: str = ""
) -> list[str]:
    errors = []
    resolved_path = _resolve_path(path, base_path)

    if not error_suffix:
        error_suffix = "not found"

    if not resolved_path.exists():
        errors.append(f"{context} {error_suffix} at '{path}'")
    elif resolved_path.suffix.lower() not in KNOWN_IMAGE_EXTENSIONS:
        errors.append(
            f"{context} has invalid extension '{resolved_path.suffix}' "
            f"(expected one of: {', '.join(KNOWN_IMAGE_EXTENSIONS)})"
        )

    return errors


def _extract_file_paths_from_value(value: Any) -> list[str]:
    paths: list[str] = []

    if isinstance(value, str):
        if _is_potential_file_path(value):
            paths.append(value)
    elif isinstance(value, list):
        for item in value:
            paths.extend(_extract_file_paths_from_value(item))
    elif isinstance(value, dict):
        for v in value.values():
            paths.extend(_extract_file_paths_from_value(v))

    return paths


def _validate_character_references(
    characters: list[Character], base_path: Path
) -> list[str]:
    errors = []

    for character in characters:
        # Extract all file paths from all character attributes
        character_data = character.model_dump()
        file_paths = _extract_file_paths_from_value(character_data)

        for file_path in file_paths:
            # Try to find which field this file_path came from for better error messages
            field_name = None
            for field, value in character_data.items():
                if value == file_path:
                    field_name = field
                    break

            if field_name:
                context = f"Character '{character.id}': {field_name}"
            else:
                context = f"Character '{character.id}'"

            errors.extend(
                _validate_file_path(
                    file_path, context, base_path, error_suffix="not found"
                )
            )

    return errors


def _validate_image_templates(
    images: dict[str, list[ImageTemplate]], base_path: Path
) -> list[str]:
    errors = []

    for category, templates in images.items():
        for template in templates:
            # Validate file paths in image parts
            for part in template.parts:
                if part.type == "image" and part.content and not part.key:
                    # Static image reference - validate it exists
                    context = f"Image template '{template.id}' (category '{category}'): reference"
                    errors.extend(
                        _validate_file_path(
                            part.content, context, base_path, error_suffix="not found"
                        )
                    )

    return errors


def _validate_frame_references(scene_graph: SceneGraph, base_path: Path) -> list[str]:
    errors = []

    # Build a set of all available template IDs and map for lookup
    template_ids = set()
    template_map = {}
    for templates in scene_graph.assets.images.values():
        for template in templates:
            template_ids.add(template.id)
            template_map[template.id] = template

    # Build a dict of character IDs for quick lookup
    character_map = {char.id: char for char in scene_graph.characters}

    for scene in scene_graph.scenes:
        for frame in scene.frames:
            # Validate template reference
            if frame.image.template not in template_ids:
                errors.append(
                    f"Frame '{frame.id}' in scene '{frame.scene_id}': "
                    f"template '{frame.image.template}' not found in assets"
                )
            else:
                # Validate template variables are provided
                template = template_map[frame.image.template]
                errors.extend(
                    _validate_template_variables(
                        frame, template, character_map, base_path
                    )
                )

            # Validate scene_id matches parent scene
            if frame.scene_id != scene.id:
                errors.append(
                    f"Frame '{frame.id}': scene_id '{frame.scene_id}' does not match "
                    f"parent scene id '{scene.id}'"
                )

            # Validate entity references in ImageConfig extra fields
            errors.extend(
                _validate_entity_references_in_frame(frame, scene_graph, base_path)
            )

    return errors


def _validate_template_variables(
    frame: Frame,
    template: ImageTemplate,
    character_map: dict[str, Character],
    base_path: Path,
) -> list[str]:
    errors = []

    # Extract all variables from template parts
    required_vars = _extract_template_variables(template)

    # Get provided variables from ImageConfig (excluding 'template' field)
    image_data = frame.image.model_dump(exclude={"template"})
    provided_vars = set(image_data.keys())

    # Check for missing variables
    missing_vars = required_vars - provided_vars
    if missing_vars:
        errors.append(
            f"Frame '{frame.id}': missing required template variables for template '{template.id}': "
            f"{sorted(missing_vars)}"
        )

    # Validate file paths in variable values
    file_paths = _extract_file_paths_from_value(image_data)
    for file_path in file_paths:
        context = f"Frame '{frame.id}': variable"
        errors.extend(
            _validate_file_path(
                file_path,
                context,
                base_path,
                error_suffix="points to non-existent file",
            )
        )

    return errors


def _extract_template_variables(template: ImageTemplate) -> set[str]:
    variables: set[str] = set()

    # Extract from all parts with keys
    for part in template.parts:
        if part.key:
            variables.add(part.key)

    return variables


def _validate_entity_references_in_frame(
    frame: Frame, scene_graph: SceneGraph, base_path: Path
) -> list[str]:
    errors = []

    # Get all fields from ImageConfig
    image_data = frame.image.model_dump()

    # Get frame data for @parent references
    frame_data = frame.model_dump()

    for field_name, field_value in image_data.items():
        if field_name == "template":
            continue

        if not isinstance(field_value, str):
            continue

        # Check if this is an entity reference
        if field_value.startswith("@"):
            # Validate the reference path
            ref_errors = _validate_reference_path(
                field_value,
                scene_graph,
                frame.id,
                parent_data=frame_data,
                self_data=image_data,
            )
            errors.extend(ref_errors)

    return errors


def _validate_reference_path(
    reference: str,
    scene_graph: SceneGraph,
    frame_id: str,
    parent_data: dict[str, Any] | None = None,
    self_data: dict[str, Any] | None = None,
) -> list[str]:
    errors = []

    # Strip the @ prefix
    if not reference.startswith("@"):
        return [f"Frame '{frame_id}': reference must start with @: '{reference}'"]

    path = reference[1:]  # Remove @

    if not path:
        return [f"Frame '{frame_id}': reference cannot be empty after @"]

    # Split the path into parts
    parts = path.split(".")

    if len(parts) < 1:
        return [
            f"Frame '{frame_id}': invalid reference '{reference}' "
            f"(expected format: @section.id.attribute or @section.id)"
        ]

    # Get the root section name
    root_section = parts[0]

    # Handle special context references
    if root_section == "self":
        if self_data is None:
            return [
                f"Frame '{frame_id}': @self reference '{reference}' used without self context"
            ]
        if len(parts) >= 2:
            field = parts[1]
            if field not in self_data:
                return [
                    f"Frame '{frame_id}': @self reference '{reference}' - field '{field}' not found in self context"
                ]
        # @self references are valid
        return []

    elif root_section == "parent":
        if parent_data is None:
            return [
                f"Frame '{frame_id}': @parent reference '{reference}' used without parent context"
            ]
        if len(parts) >= 2:
            field = parts[1]
            if field not in parent_data:
                return [
                    f"Frame '{frame_id}': @parent reference '{reference}' - field '{field}' not found in parent context"
                ]
        # @parent references are valid
        return []

    # Validate the root section exists
    valid_sections = ["characters", "assets", "scenes"]
    if root_section not in valid_sections:
        return [
            f"Frame '{frame_id}': invalid section '{root_section}' in reference '{reference}' "
            f"(valid sections: {', '.join(valid_sections)})"
        ]

    # For characters section, validate character exists and attribute is accessible
    if root_section == "characters":
        if len(parts) < 2:
            return [
                f"Frame '{frame_id}': invalid characters reference '{reference}' "
                f"(expected format: @characters.character_id.attribute)"
            ]

        character_id = parts[1]
        character_map = {char.id: char for char in scene_graph.characters}

        if character_id not in character_map:
            return [
                f"Frame '{frame_id}': character '{character_id}' not found "
                f"in reference '{reference}'"
            ]

        # If there's an attribute specified, validate it exists
        if len(parts) >= 3:
            attribute = parts[2]
            character = character_map[character_id]

            # Check if the attribute exists on the character
            if not hasattr(character, attribute):
                # Get valid attributes from the model's fields
                valid_attrs = list(character.__class__.model_fields.keys())
                return [
                    f"Frame '{frame_id}': invalid attribute '{attribute}' "
                    f"in reference '{reference}' (valid attributes: {', '.join(valid_attrs)})"
                ]

    # For assets section, validate structure
    elif root_section == "assets":
        if len(parts) < 2:
            return [
                f"Frame '{frame_id}': invalid assets reference '{reference}' "
                f"(expected format: @assets.subsection.id or @assets.images.category.template_id)"
            ]

        subsection = parts[1]
        if subsection != "images":
            return [
                f"Frame '{frame_id}': invalid assets subsection '{subsection}' in reference '{reference}' "
                f"(only 'images' is currently supported)"
            ]

        # For assets.images, need at least category and template_id
        if len(parts) >= 4:
            category = parts[2]
            template_id = parts[3]

            if category not in scene_graph.assets.images:
                return [
                    f"Frame '{frame_id}': image category '{category}' not found "
                    f"in reference '{reference}'"
                ]

            # Check if template exists in this category
            templates = scene_graph.assets.images[category]
            template_ids = [t.id for t in templates]

            if template_id not in template_ids:
                return [
                    f"Frame '{frame_id}': template '{template_id}' not found in category '{category}' "
                    f"in reference '{reference}'"
                ]

    return errors


def _resolve_path(path_str: str, base_path: Path) -> Path:
    path = Path(path_str)

    # If path starts with './', make it relative to base_path
    if path_str.startswith("./"):
        return base_path / path_str[2:]

    # If path is already absolute, return as-is
    if path.is_absolute():
        return path

    # Otherwise, resolve relative to base_path
    return base_path / path
