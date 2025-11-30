"""Tests for the update command."""

import pytest

from storyboard.cli.update.selector_parser import parse_update_selector
from storyboard.core.load.load import load_scene_graph
from storyboard.core.shapes import Frame, Scene, SceneGraph


@pytest.fixture
def multi_scene_fixture_path(tmp_path, test_image_file):
    """Create fixture with multiple scenes and frames for testing selectors."""
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    main_yaml = f"""characters: ./characters.yaml
image_templates: ./image_templates.yaml
tts_templates: ./tts_templates.yaml
scenes: ./scenes.yaml

config:
  output:
    directory: ./output
    cache:
      images: {cache_dir}/images
      audio: {cache_dir}/audio
"""

    characters_yaml = f"""_test_char:
  name: Test Character
  reference_photo: {test_image_file}
  tts:
    style: "Test style"
    voice: Fenrir
"""

    image_templates_yaml = """_test_template:
  instructions: "Test prompt {{image $character_reference}}"
"""

    tts_templates_yaml = """_test_tts:
  voice_id: "{$character.tts.voice}"
  prompt: "{$content}"
"""

    scenes_yaml = """_scene_one:
  name: Scene One
  frames:
    _frame_a:
      image:
        template: _test_template
        $character_reference: "@characters._test_char.reference_photo"
      tts:
        template: _test_tts
        $character: "@characters._test_char"
        $content: "Dialogue A"
    _frame_b:
      image:
        template: _test_template
        $character_reference: "@characters._test_char.reference_photo"
      tts:
        template: _test_tts
        $character: "@characters._test_char"
        $content: "Dialogue B"
_scene_two:
  name: Scene Two
  frames:
    _frame_c:
      image:
        template: _test_template
        $character_reference: "@characters._test_char.reference_photo"
    _frame_d:
      image:
        template: _test_template
        $character_reference: "@characters._test_char.reference_photo"
      tts:
        template: _test_tts
        $character: "@characters._test_char"
        $content: "Dialogue D"
"""

    (fixtures_dir / "main.yaml").write_text(main_yaml)
    (fixtures_dir / "characters.yaml").write_text(characters_yaml)
    (fixtures_dir / "image_templates.yaml").write_text(image_templates_yaml)
    (fixtures_dir / "tts_templates.yaml").write_text(tts_templates_yaml)
    (fixtures_dir / "scenes.yaml").write_text(scenes_yaml)

    return fixtures_dir / "main.yaml"


class TestSelectorParsing:
    """Test selector parsing with various formats."""

    def test_parse_selector_string_ids(self, multi_scene_fixture_path):
        """Test string ID parsing."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        scene_id, frame_id, asset_types = parse_update_selector(
            "scene_one.frame_a", scene_graph
        )

        assert scene_id == "scene_one"
        assert frame_id == "frame_a"
        assert asset_types == {"image", "audio"}

    def test_parse_selector_image_only(self, multi_scene_fixture_path):
        """Test image-only selector."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        scene_id, frame_id, asset_types = parse_update_selector(
            "scene_one.frame_a.image", scene_graph
        )

        assert scene_id == "scene_one"
        assert frame_id == "frame_a"
        assert asset_types == {"image"}

    def test_parse_selector_tts_alias(self, multi_scene_fixture_path):
        """Test tts alias maps to audio."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        scene_id, frame_id, asset_types = parse_update_selector(
            "scene_one.frame_a.tts", scene_graph
        )

        assert scene_id == "scene_one"
        assert frame_id == "frame_a"
        assert asset_types == {"audio"}

    def test_parse_selector_audio_keyword(self, multi_scene_fixture_path):
        """Test audio keyword."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        scene_id, frame_id, asset_types = parse_update_selector(
            "scene_one.frame_a.audio", scene_graph
        )

        assert asset_types == {"audio"}

    def test_parse_selector_invalid_format_too_many_parts(
        self, multi_scene_fixture_path
    ):
        """Test invalid format with too many parts."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        with pytest.raises(ValueError, match="Invalid selector format"):
            parse_update_selector("1.2.3.4", scene_graph)

    def test_parse_selector_invalid_format_too_few_parts(self, multi_scene_fixture_path):
        """Test invalid format with too few parts."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        with pytest.raises(ValueError, match="Invalid selector format"):
            parse_update_selector("1", scene_graph)

    def test_parse_selector_invalid_asset_type(self, multi_scene_fixture_path):
        """Test invalid asset type."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        with pytest.raises(ValueError, match="Invalid asset type"):
            parse_update_selector("1.1.video", scene_graph)

    def test_parse_selector_nonexistent_scene_id(self, multi_scene_fixture_path):
        """Test nonexistent scene ID."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        with pytest.raises(ValueError, match="Scene not found: 'nonexistent'"):
            parse_update_selector("nonexistent.frame_a", scene_graph)

    def test_parse_selector_nonexistent_frame_id(self, multi_scene_fixture_path):
        """Test nonexistent frame ID."""
        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )

        with pytest.raises(
            ValueError, match="Frame not found in scene 'scene_one': 'nonexistent'"
        ):
            parse_update_selector("scene_one.nonexistent", scene_graph)


class TestSelectiveGeneration:
    """Test selective asset generation with mocked Gemini client."""

    @pytest.mark.asyncio
    async def test_generate_frame_selective_both_assets(
        self, multi_scene_fixture_path, mock_gemini_client, tmp_path
    ):
        """Test generating both assets."""
        from storyboard.cli.run.parallel_generator import ParallelSceneGenerator

        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )
        generator = ParallelSceneGenerator(scene_graph=scene_graph)

        output_path = tmp_path / "output" / "scene_one"
        result, failures = await generator.generate_frame_selective(
            scene_id="scene_one",
            frame_id="frame_a",
            scene_output_path=str(output_path),
            asset_types={"image", "audio"},
            use_cached=False,
        )

        assert result.frame_id == "frame_a"
        assert result.image_asset is not None
        assert result.audio_asset is not None
        assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_generate_frame_selective_image_only(
        self, multi_scene_fixture_path, mock_gemini_client, tmp_path
    ):
        """Test generating only image asset."""
        from storyboard.cli.run.parallel_generator import ParallelSceneGenerator

        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )
        generator = ParallelSceneGenerator(scene_graph=scene_graph)

        output_path = tmp_path / "output" / "scene_one"
        result, failures = await generator.generate_frame_selective(
            scene_id="scene_one",
            frame_id="frame_a",
            scene_output_path=str(output_path),
            asset_types={"image"},
            use_cached=False,
        )

        assert result.frame_id == "frame_a"
        assert result.image_asset is not None
        assert result.audio_asset is None
        assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_generate_frame_selective_audio_only(
        self, multi_scene_fixture_path, mock_gemini_client, tmp_path
    ):
        """Test generating only audio asset."""
        from storyboard.cli.run.parallel_generator import ParallelSceneGenerator

        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )
        generator = ParallelSceneGenerator(scene_graph=scene_graph)

        output_path = tmp_path / "output" / "scene_one"
        result, failures = await generator.generate_frame_selective(
            scene_id="scene_one",
            frame_id="frame_a",
            scene_output_path=str(output_path),
            asset_types={"audio"},
            use_cached=False,
        )

        assert result.frame_id == "frame_a"
        assert result.image_asset is None
        assert result.audio_asset is not None
        assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_generate_frame_nonexistent_scene(
        self, multi_scene_fixture_path, tmp_path
    ):
        """Test error when scene doesn't exist."""
        from storyboard.cli.run.parallel_generator import ParallelSceneGenerator

        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )
        generator = ParallelSceneGenerator(scene_graph=scene_graph)

        with pytest.raises(ValueError, match="Scene not found: nonexistent"):
            await generator.generate_frame_selective(
                scene_id="nonexistent",
                frame_id="frame_a",
                scene_output_path=str(tmp_path),
            )

    @pytest.mark.asyncio
    async def test_generate_frame_nonexistent_frame(
        self, multi_scene_fixture_path, tmp_path
    ):
        """Test error when frame doesn't exist."""
        from storyboard.cli.run.parallel_generator import ParallelSceneGenerator

        scene_graph = load_scene_graph(
            multi_scene_fixture_path, multi_scene_fixture_path.parent
        )
        generator = ParallelSceneGenerator(scene_graph=scene_graph)

        with pytest.raises(
            ValueError, match="Frame not found in scene scene_one: nonexistent"
        ):
            await generator.generate_frame_selective(
                scene_id="scene_one",
                frame_id="nonexistent",
                scene_output_path=str(tmp_path),
            )
