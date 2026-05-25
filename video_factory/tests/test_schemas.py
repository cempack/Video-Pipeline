"""Schema and utility tests (no API keys required)."""

from video_factory.models.schemas import ProjectConfig, ScriptPackage, ScenePlan, SceneSpec
from video_factory.utils.text import extract_json_object, words_per_minute_estimate


def test_script_word_count():
    pkg = ScriptPackage(
        title="T",
        hook="H",
        full_script="one two three four five",
    )
    assert pkg.word_count == 5


def test_extract_json_object():
    raw = 'Here is data:\n```json\n{"a": 1}\n```'
    assert extract_json_object(raw) == {"a": 1}


def test_wpm():
    assert words_per_minute_estimate(145) == 60.0


def test_scene_plan():
    plan = ScenePlan(
        scenes=[
            SceneSpec(scene_id="s01", narration="Hello", start_sec=0, end_sec=3),
        ]
    )
    assert len(plan.scenes) == 1


def test_project_config():
    cfg = ProjectConfig(project_id="x", topic="test")
    assert cfg.vertical == "technology"
