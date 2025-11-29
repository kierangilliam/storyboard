"""Generic reference resolution system for scene graphs.

References use the @ symbol followed by a dot-separated path:
- @characters.chris.name -> characters[chris].name
- @assets.images.template_id.prompt -> assets.images[template_id].prompt
- @self.field -> field in the current object
- @parent.field -> field in the parent object

Supports:
- Arbitrary nesting depth
- Recursive resolution (references within references)
- Complex object serialization (dicts/lists -> JSON)
- Circular reference detection
- Context-aware resolution (@self, @parent)
"""

import json
from typing import Any

from storyboard.core.shapes import SceneGraph


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected."""


def resolve_references(scene_graph: SceneGraph) -> SceneGraph:
    # Convert to dict for easy manipulation
    data = scene_graph.model_dump()

    # Resolve all references, tracking visited to detect cycles
    # Pass None for parent and self since we're at the root
    resolved_data = scan_and_resolve(data, scene_graph, set(), parent=None, self_obj=None)

    # Rebuild the scene graph with resolved values
    return SceneGraph(**resolved_data)


def scan_and_resolve(
    obj: Any,
    scene_graph: SceneGraph,
    visited: set[str],
    parent: Any | None = None,
    self_obj: Any | None = None,
) -> Any:
    if isinstance(obj, str):
        # Check if this is a reference
        if obj.startswith("@"):
            return resolve_reference(obj, scene_graph, visited, parent, None)
        return obj

    elif isinstance(obj, dict):
        # For dicts, we need to handle @self and @parent references carefully
        # @self references need access to sibling fields in the same dict
        # @parent references need access to the parent dict

        # Strategy:
        # 1. First pass - resolve all non-context references
        # 2. Second pass - resolve @self references against the partially-resolved dict
        # 3. @parent references use the parent passed in

        temp = {}
        self_refs = {}

        # First pass: resolve non-@self references
        for key, value in obj.items():
            if isinstance(value, str) and value.startswith("@self"):
                # Defer @self references to second pass
                self_refs[key] = value
                temp[key] = value  # Placeholder
            else:
                # For nested dicts, pass current dict as parent
                # For nested non-dicts, pass parent through
                if isinstance(value, dict):
                    temp[key] = scan_and_resolve(value, scene_graph, visited, parent=obj, self_obj=None)
                else:
                    temp[key] = scan_and_resolve(value, scene_graph, visited, parent=parent, self_obj=None)

        # Second pass: resolve @self references with access to partially resolved dict
        for key, ref_string in self_refs.items():
            temp[key] = resolve_reference(ref_string, scene_graph, visited, parent=parent, self_obj=temp)

        return temp

    elif isinstance(obj, list):
        # For lists, resolve each item with same parent context
        return [
            scan_and_resolve(item, scene_graph, visited, parent, None)
            for item in obj
        ]

    else:
        # Primitive value, return as-is
        return obj


def resolve_reference(
    ref_string: str,
    scene_graph: SceneGraph,
    visited: set[str],
    parent: Any | None = None,
    self_obj: Any | None = None,
) -> Any:
    # Check for circular references
    if ref_string in visited:
        raise CircularReferenceError(f"Circular reference detected: {ref_string}")

    # Add to visited set
    visited = visited | {ref_string}

    # Strip the @ prefix
    if not ref_string.startswith("@"):
        raise ValueError(f"Reference must start with @: {ref_string}")

    path = ref_string[1:]  # Remove @

    if not path:
        raise ValueError("Reference cannot be empty after @")

    # Split the path into parts
    parts = path.split(".")

    if len(parts) < 1:
        raise ValueError(f"Invalid reference path: {ref_string}")

    # Get the root section name
    root_section = parts[0]

    # Handle special context references
    if root_section == "self":
        if self_obj is None:
            raise ValueError(f"Cannot use @self reference '{ref_string}' without a context")
        # Navigate from self_obj
        if len(parts) == 1:
            value = self_obj
        else:
            value = get_nested_attribute(self_obj, parts[1:])
    elif root_section == "parent":
        if parent is None:
            raise ValueError(f"Cannot use @parent reference '{ref_string}' without a parent context")
        # Navigate from parent
        if len(parts) == 1:
            value = parent
        else:
            value = get_nested_attribute(parent, parts[1:])
    else:
        # Navigate from scene_graph
        value = get_nested_attribute(scene_graph, parts)

    # If the value itself contains references, resolve them recursively
    resolved_value = scan_and_resolve(value, scene_graph, visited, parent, self_obj)

    # If the resolved value is a complex object (dict, list, or Pydantic model), serialize it
    if isinstance(resolved_value, (dict, list)):
        return json.dumps(resolved_value)
    elif hasattr(resolved_value, "model_dump"):
        # Pydantic model - serialize to JSON
        return json.dumps(resolved_value.model_dump())

    return resolved_value


def get_nested_attribute(root: Any, path: list[str]) -> Any:
    current = root
    current_path = []

    for part in path:
        current_path.append(part)
        path_str = ".".join(current_path)

        # Try attribute access first (for Pydantic models)
        if hasattr(current, part):
            current = getattr(current, part)

        # Try dict access
        elif isinstance(current, dict):
            if part not in current:
                raise ValueError(f"Key '{part}' not found in dict at path: {path_str}")
            current = current[part]

        # Try list access (by finding item with matching id)
        elif isinstance(current, list):
            # Look for an item with matching id
            found = False

            # Strip _ prefix if present for ID lookup
            lookup_part = part[1:] if part.startswith("_") else part

            for item in current:
                # Check if item has an 'id' attribute matching this part
                if hasattr(item, "id") and item.id == lookup_part:
                    current = item
                    found = True
                    break
                # Or if item is a dict with 'id' key
                elif isinstance(item, dict) and item.get("id") == lookup_part:
                    current = item
                    found = True
                    break

            if not found:
                raise ValueError(
                    f"No item with id='{lookup_part}' found in list at path: {path_str}"
                )

        else:
            raise ValueError(
                f"Cannot access '{part}' on {type(current).__name__} at path: {path_str}"
            )

    return current
