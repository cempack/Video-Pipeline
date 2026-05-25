"""Pydantic schemas for every pipeline artifact."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Vertical = Literal["technology", "politics", "economics", "philosophy"]
AspectRatio = Literal["9:16", "16:9", "1:1"]
SubtitleStyle = Literal["burned_in", "sidecar", "both"]


class ProjectConfig(BaseModel):
    project_id: str
    topic: str
    vertical: Vertical = "technology"
    target_duration_sec: int = Field(default=45, ge=15, le=180)
    aspect_ratio: AspectRatio = "9:16"
    language: str = "en"
    voice: str = "default"
    visual_style: str = "editorial illustration"
    subtitle_style: SubtitleStyle = "burned_in"
    # Production techniques (faceless AI channel workflows)
    scene_beat_sec: float = Field(
        default=3.0,
        ge=1.5,
        le=6.0,
        description="Target seconds per still frame (~3s matches common faceless edits)",
    )
    image_variants_per_scene: int = Field(default=4, ge=1, le=8)
    auto_select_first_variant: bool = True
    remove_silence: bool = True
    silence_threshold_db: float = -40.0
    silence_min_duration_sec: float = 0.15
    audio_loudness_variation: bool = False
    require_script_approval: bool = False
    use_asset_library: bool = True
    style_reference: str = ""
    character_reference: str = ""
    max_title_chars: int = 60
    image_backend: Literal["whisk_local", "whisk_gemini", "placeholder"] = "whisk_local"
    enforce_face_lock: bool = True
    palette_lock_strength: float = Field(default=0.55, ge=0.0, le=1.0)
    gemini_image_model: str = ""


class ResearchSource(BaseModel):
    title: str = ""
    url: str = ""
    excerpt: str = ""


class ResearchPack(BaseModel):
    topic: str
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    notes: str = ""
    grounding_required: bool = True


class ScriptPackage(BaseModel):
    title: str
    hook: str
    full_script: str
    word_count: int = 0
    estimated_duration_sec: float = 0.0
    safety_notes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    claims_requiring_verification: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fill_word_count(self) -> ScriptPackage:
        if not self.word_count and self.full_script:
            object.__setattr__(self, "word_count", len(self.full_script.split()))
        return self


class SceneSpec(BaseModel):
    scene_id: str
    narration: str
    start_sec: float = 0.0
    end_sec: float = 0.0
    visual_prompt: str = ""
    on_screen_text: str = ""
    transition_hint: str = "cut"
    image_prompt: str = ""


class ScenePlan(BaseModel):
    scenes: list[SceneSpec] = Field(default_factory=list)


class VisualPromptDetail(BaseModel):
    scene_id: str
    subject: str = ""
    setting: str = ""
    composition: str = ""
    lighting: str = ""
    mood: str = ""
    palette: str = ""
    camera_framing: str = ""
    negative_prompt: str = ""
    aspect_ratio: str = "9:16"
    full_prompt: str = ""


class StyleBible(BaseModel):
    visual_style: str
    palette: str = ""
    lighting: str = ""
    composition_rules: str = ""
    negative_global: str = "text, watermark, blurry, low quality"


class ImageAsset(BaseModel):
    scene_id: str
    prompt: str
    path: str
    seed: int | None = None
    model: str = ""
    width: int = 0
    height: int = 0
    variant_id: str = ""
    from_library: bool = False


class ImageVariant(BaseModel):
    variant_id: str
    path: str
    seed: int | None = None


class ImageCandidateSet(BaseModel):
    scene_id: str
    prompt: str
    variants: list[ImageVariant] = Field(default_factory=list)
    selected_variant_id: str | None = None


class ImageSelectionManifest(BaseModel):
    scenes: list[ImageCandidateSet] = Field(default_factory=list)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StageApproval(BaseModel):
    stage: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    notes: str = ""
    reviewed_at: str | None = None


class LibraryAsset(BaseModel):
    asset_id: str
    description: str
    path: str
    tags: list[str] = Field(default_factory=list)
    style: str = ""


class LibraryIndex(BaseModel):
    assets: list[LibraryAsset] = Field(default_factory=list)


class AudioManifest(BaseModel):
    voiceover_path: str = ""
    scene_paths: dict[str, str] = Field(default_factory=dict)


class SubtitleManifest(BaseModel):
    srt_path: str = ""
    vtt_path: str = ""
    segments_path: str = ""


class AssetManifest(BaseModel):
    images: list[ImageAsset] = Field(default_factory=list)
    audio: AudioManifest = Field(default_factory=AudioManifest)
    subtitles: SubtitleManifest = Field(default_factory=SubtitleManifest)


class SubtitleCue(BaseModel):
    index: int
    start_sec: float
    end_sec: float
    text: str


class SubtitleSegments(BaseModel):
    cues: list[SubtitleCue] = Field(default_factory=list)


class MotionSpec(BaseModel):
    type: Literal["ken_burns", "static", "pan"] = "ken_burns"
    zoom: float = 1.08


class TimelineScene(BaseModel):
    scene_id: str
    image_path: str
    audio_path: str = ""
    start_sec: float = 0.0
    duration_sec: float = 0.0
    motion: MotionSpec = Field(default_factory=MotionSpec)
    transition_out: Literal["fade", "cut", "dissolve"] = "fade"


class RenderTimeline(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    scenes: list[TimelineScene] = Field(default_factory=list)


class QACheck(BaseModel):
    name: str
    passed: bool
    message: str = ""


class QAReport(BaseModel):
    passed: bool = False
    checks: list[QACheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    video_path: str = ""
    duration_sec: float = 0.0


class StageName(str, Enum):
    RESEARCH = "research"
    CHARACTER = "character"
    SCRIPT = "script"
    SCENES = "scenes"
    PROMPTS = "prompts"
    IMAGES = "images"
    NARRATION = "narration"
    SUBTITLES = "subtitles"
    TIMELINE = "timeline"
    RENDER = "render"
    QA = "qa"


class StageRecord(BaseModel):
    completed_at: str | None = None
    artifact_hash: str | None = None
    error: str | None = None


class ProjectState(BaseModel):
    stages: dict[str, StageRecord] = Field(default_factory=dict)
    last_run: str | None = None

    def mark_complete(self, stage: StageName, artifact_hash: str | None = None) -> None:
        self.stages[stage.value] = StageRecord(
            completed_at=datetime.now(timezone.utc).isoformat(),
            artifact_hash=artifact_hash,
            error=None,
        )

    def mark_failed(self, stage: StageName, error: str) -> None:
        self.stages[stage.value] = StageRecord(
            completed_at=datetime.now(timezone.utc).isoformat(),
            artifact_hash=None,
            error=error,
        )

    def is_complete(self, stage: StageName) -> bool:
        rec = self.stages.get(stage.value)
        return bool(rec and rec.completed_at and not rec.error)
