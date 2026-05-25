"""QA validation and report."""

from __future__ import annotations

from pathlib import Path

from video_factory.adapters.ffmpeg import FFmpegAdapter
from video_factory.models.schemas import ProjectConfig, QAReport, QACheck, RenderTimeline, StageName
from video_factory.stages.base import get_config, get_settings, json_artifact, load_state, outputs_path, require_stage, save_state
from video_factory.stages.character import references_ready
from video_factory.ui.console import get_console
from video_factory.utils.files import atomic_write_json, read_json, require_file
from video_factory.utils.hash import content_hash


def run_qa(project_dir: Path, *, force: bool = False) -> QAReport:
    state = load_state(project_dir)
    report_path = outputs_path(project_dir, "qa_report.json")
    if not force and state.is_complete(StageName.QA) and report_path.exists():
        return QAReport.model_validate(read_json(report_path))

    require_stage(project_dir, StageName.QA, StageName.RENDER)
    config = get_config(project_dir)
    ffmpeg = FFmpegAdapter(get_settings())
    checks: list[QACheck] = []
    warnings: list[str] = []

    video_candidates = [
        outputs_path(project_dir, "final_subtitled.mp4"),
        outputs_path(project_dir, "final_clean.mp4"),
    ]
    video_path = next((p for p in video_candidates if p.is_file()), None)
    if not video_path:
        checks.append(QACheck(name="video_exists", passed=False, message="No output MP4 found"))
        report = QAReport(passed=False, checks=checks, warnings=warnings)
        atomic_write_json(report_path, report.model_dump(mode="json"))
        state.mark_failed(StageName.QA, "missing video")
        save_state(project_dir, state)
        return report

    checks.append(QACheck(name="video_exists", passed=True, message=str(video_path)))
    duration = ffmpeg.probe_duration(video_path)
    tol = 8.0
    dur_ok = abs(duration - config.target_duration_sec) <= tol
    checks.append(
        QACheck(
            name="duration_tolerance",
            passed=dur_ok,
            message=f"duration={duration:.1f}s target={config.target_duration_sec}s",
        )
    )
    if not dur_ok:
        warnings.append(f"Duration {duration:.1f}s outside ±{tol}s of target")

    info = ffmpeg.probe_video_info(video_path)
    vstream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    w = int(vstream.get("width", 0))
    h = int(vstream.get("height", 0))
    res_ok = w > 0 and h > 0
    checks.append(QACheck(name="resolution", passed=res_ok, message=f"{w}x{h}"))

    timeline = RenderTimeline.model_validate(read_json(json_artifact(project_dir, "timeline.json")))
    missing = []
    for scene in timeline.scenes:
        if not (project_dir / scene.image_path).is_file():
            missing.append(scene.image_path)
    checks.append(
        QACheck(
            name="scene_assets",
            passed=len(missing) == 0,
            message="ok" if not missing else f"missing: {missing}",
        )
    )

    srt = project_dir / "work/subtitles/final.srt"
    if srt.is_file():
        text = srt.read_text(encoding="utf-8")
        parse_ok = "-->" in text and len(text.strip()) > 0
        checks.append(QACheck(name="subtitle_parse", passed=parse_ok, message=str(srt)))
        for line in text.splitlines():
            if len(line) > 80:
                warnings.append("Long subtitle line detected")
                break
    else:
        checks.append(QACheck(name="subtitle_parse", passed=False, message="missing SRT"))

    for scene in timeline.scenes:
        if scene.duration_sec < 1.0:
            warnings.append(f"Scene {scene.scene_id} under 1s — may feel rushed")
        if scene.duration_sec > config.scene_beat_sec * 2:
            warnings.append(f"Scene {scene.scene_id} longer than 2× beat ({config.scene_beat_sec}s)")

    refs_ok, missing = references_ready(project_dir)
    checks.append(
        QACheck(
            name="whisk_references",
            passed=refs_ok or not config.enforce_face_lock,
            message="ok" if refs_ok else f"missing: {missing}",
        )
    )
    if config.enforce_face_lock and not (project_dir / "work/json/character_sheet.png").is_file():
        warnings.append("Character sheet missing — face lock may be inconsistent")

    script_meta_path = json_artifact(project_dir, "script_meta.json")
    if script_meta_path.exists():
        meta = read_json(script_meta_path)
        title_ok = bool(meta.get("title_fits_homepage", True))
        checks.append(
            QACheck(
                name="title_homepage_fit",
                passed=title_ok,
                message=meta.get("title_check", ""),
            )
        )
        if not title_ok:
            warnings.append("Title may truncate on YouTube mobile homepage")

    passed = all(c.passed for c in checks)
    report = QAReport(
        passed=passed,
        checks=checks,
        warnings=warnings,
        video_path=str(video_path.relative_to(project_dir)),
        duration_sec=duration,
    )
    atomic_write_json(report_path, report.model_dump(mode="json"))
    if passed:
        state.mark_complete(StageName.QA, content_hash(report.model_dump()))
    else:
        state.mark_failed(StageName.QA, "QA checks failed")
    save_state(project_dir, state)
    get_console().qa_summary(passed, checks, warnings)
    return report
