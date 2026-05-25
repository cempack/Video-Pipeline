"""Human approval gates between automated stages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from video_factory.models.schemas import ApprovalStatus, StageApproval, StageName
from video_factory.utils.files import atomic_write_json, read_json


def approval_path(project_dir: Path, stage: StageName) -> Path:
    return project_dir / "work" / "json" / f"approval_{stage.value}.json"


def load_approval(project_dir: Path, stage: StageName) -> StageApproval | None:
    path = approval_path(project_dir, stage)
    if not path.exists():
        return None
    return StageApproval.model_validate(read_json(path))


def save_approval(project_dir: Path, approval: StageApproval) -> None:
    stage = StageName(approval.stage)
    atomic_write_json(approval_path(project_dir, stage), approval.model_dump(mode="json"))


def require_approved(project_dir: Path, stage: StageName) -> None:
    rec = load_approval(project_dir, stage)
    if not rec or rec.status != ApprovalStatus.APPROVED:
        raise RuntimeError(
            f"Stage '{stage.value}' requires human approval. "
            f"Run: video-factory approve {stage.value} <project_id>"
        )


def set_approval(
    project_dir: Path,
    stage: StageName,
    status: ApprovalStatus,
    notes: str = "",
) -> StageApproval:
    rec = StageApproval(
        stage=stage.value,
        status=status,
        notes=notes,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    save_approval(project_dir, rec)
    return rec
