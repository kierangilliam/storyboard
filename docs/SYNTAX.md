# Storyboard: Scene description syntax

### Identifiers
`_` prefix defines reusable objects (characters, scenes, templates):

```yaml
_nick:
  name: Nick
  reference_photo: ./assets/nick.png
```

### Variables
`$` prefix for template variables:

```yaml
# Definition
$backdrop: A medieval tavern

# Reference in text
"The backdrop should be: {$backdrop}"
```

### Cross-References
`@` references other configuration parts:

```yaml
character: "@characters._chris"              # Entire object
name: "@characters._nick.name"               # Nested property
dialogue: "@parent.tts.content"              # Parent reference
```

### Image Templates
Templates with inline images and variable substitution:

```yaml
_oblivion_dialogue:
  instructions: |
    Transform {image $character_reference} into Oblivion style.
    Reference style: {image ./assets/oblivion.webp}
    Name: '{$character_name}'. Backdrop: {$backdrop}.
```

**Syntax:**
- `{image $variable}` - Variable containing image path
- `{image ./path/to/file.jpg}` - Static image file
- `{$variable}` - Text variable substitution

**Using templates:**

```yaml
image:
  template: _oblivion_dialogue
  $character_reference: "@characters._chris.reference_photo"
  $character_name: "@characters._chris.name"
  $backdrop: "A medieval tavern"
```

