"""Script generation with two-pass draft + compression."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.llm_gemini import GeminiLLMWriter
from video_factory.models.schemas import ProjectConfig, ResearchPack, ScriptPackage, StageName
from video_factory.stages.base import (
    get_settings,
    json_artifact,
    load_state,
    require_stage,
    save_state,
)
from video_factory.stages.research import run_research
from video_factory.utils.files import atomic_write_json, read_json
from video_factory.utils.hash import content_hash
from video_factory.utils.text import words_per_minute_estimate


def run_script(project_dir: Path, *, force: bool = False) -> ScriptPackage:
    state = load_state(project_dir)
    out = json_artifact(project_dir, "script_package.json")
    if not force and state.is_complete(StageName.SCRIPT) and out.exists():
        return ScriptPackage.model_validate(read_json(out))

    from video_factory.stages.base import get_config

    config = get_config(project_dir)
    research_path = json_artifact(project_dir, "research_pack.json")
    research = (
        ResearchPack.model_validate(read_json(research_path))
        if research_path.exists()
        else None
    )
    if research_path.exists() is False:
        run_research(project_dir)
        research = ResearchPack.model_validate(read_json(research_path))

    writer = GeminiLLMWriter(get_settings())
    draft = _draft_script(writer, config, research)
    compressed = _compress_script(writer, config, draft)
    pkg = ScriptPackage.model_validate(compressed)
    if not pkg.word_count:
        pkg = ScriptPackage(
            **{**pkg.model_dump(), "word_count": len(pkg.full_script.split())}
        )
    est = words_per_minute_estimate(pkg.word_count)
    pkg = ScriptPackage(**{**pkg.model_dump(), "estimated_duration_sec": est})

    atomic_write_json(out, pkg.model_dump(mode="json"))
    state.mark_complete(StageName.SCRIPT, content_hash(pkg.model_dump()))
    save_state(project_dir, state)
    return pkg


def _draft_script(writer: GeminiLLMWriter, config: ProjectConfig, research: ResearchPack | None) -> dict:
    vertical_rules = {
        "philosophy": "Avoid empty quote compilations; build one clear argument.",
        "politics": "Mark uncertain or contested claims; do not invent current-event facts.",
        "economics": "Flag numbers, dates, and forecasts for verification.",
        "technology": "Define acronyms on first use; limit jargon density.",
    }
    instruction = (
        "Write a short-form vertical video script as JSON. "
        "Fields: title, hook, full_script, estimated_duration_sec, "
        "claims_requiring_verification, safety_notes, sources. "
        f"Target ~{config.target_duration_sec}s at 145 WPM. "
        f"Vertical: {config.vertical}. Tone: sharp, concrete, no filler intro/outro. "
        f"Hook must land in first 3 seconds. {vertical_rules.get(config.vertical, '')} "
        "Cap sentence length for TTS. Return JSON only."
    )
    payload = {
        "topic": config.topic,
        "language": config.language,
        "research": research.model_dump() if research else {},
    }
    return writer.generate_json(instruction, payload, "ScriptPackage")


def _compress_script(writer: GeminiLLMWriter, config: ProjectConfig, draft: dict) -> dict:
    max_words = int(config.target_duration_sec * 145 / 60) + 5
    instruction = (
        "Compress the script JSON to fit target duration. "
        f"Maximum ~{max_words} words. Keep title and hook. "
        "Preserve claims_requiring_verification. Return JSON only."
    )
    return writer.generate_json(instruction, {"draft": draft, "target_sec": config.target_duration_sec}, "ScriptPackage")
