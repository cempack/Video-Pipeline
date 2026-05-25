#!/usr/bin/env bash
# Heavy integration test: pytest, fresh managed bootstrap, CLI, engine, web API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BIN="${BIN:-$ROOT/dist/video-factory}"
FAIL=0
PASS=0
TMP_ROOT="$(mktemp -d)"
export VIDEO_FACTORY_FORCE_MANAGED=1
export XDG_DATA_HOME="${TMP_ROOT}/data"
export XDG_CONFIG_HOME="${TMP_ROOT}/config"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME"
DATA_DIR="$XDG_DATA_HOME/video-factory"
PROJECTS_FLAG=(--projects "$DATA_DIR/projects")
# Keep real HOME so go toolchain cache is not written under a temp tree we delete.

log() { echo ""; echo "════════════════════════════════════════"; echo "▶ $*"; echo "════════════════════════════════════════"; }
ok() { PASS=$((PASS + 1)); echo "  ✓ $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  ✗ $*" >&2; }

run() {
  echo "  $ $*"
  if "$@"; then ok "$*"; else fail "$*"; return 1; fi
}

assert_file() {
  if [[ -f "$1" ]]; then ok "exists: $1"; else fail "missing: $1"; return 1; fi
}

assert_contains() {
  if echo "$1" | grep -qF "$2"; then ok "output contains: $2"; else fail "expected output to contain: $2"; echo "$1" >&2; return 1; fi
}

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

log "1) Python unit tests (verbose)"
run pip install -q -e ".[dev]" 2>/dev/null || run pip install -q -e .
run env PYTHONPATH=src python3 -m pytest -v --tb=short -ra

log "2) Go vet + release build"
run go vet ./...
run make build
assert_file "$BIN"
run "$BIN" --help
run "$BIN" "${PROJECTS_FLAG[@]}" setup --help

log "3) Fresh managed data dir (simulate first install)"
rm -rf "$DATA_DIR"
run "$BIN" "${PROJECTS_FLAG[@]}" setup
assert_file "$DATA_DIR/venv/bin/python3"
assert_file "$DATA_DIR/engine-src-0.1.1/src/video_factory/engine.py"
assert_file "$DATA_DIR/engine-src-0.1.1/requirements.txt"
assert_file "$DATA_DIR/engine-src-0.1.1/src/video_factory/stages/__init__.py"

log "4) Idempotent second setup"
run "$BIN" "${PROJECTS_FLAG[@]}" setup

log "5) Doctor + engine ping"
OUT="$("$BIN" "${PROJECTS_FLAG[@]}" doctor 2>&1)" || { fail doctor; echo "$OUT"; }
assert_contains "$OUT" "Python engine OK"
PY="$DATA_DIR/venv/bin/python3"
ENG_ROOT="$DATA_DIR/engine-src-0.1.1"
PING="$(cd "$ENG_ROOT" && PYTHONPATH=src "$PY" -m video_factory.engine ping)"
assert_contains "$PING" '"ok": true'

log "6) CLI project lifecycle (offline-seeded)"
PROJ_ID="heavy-test-$(date +%s)"
PROJ_DIR="$DATA_DIR/projects/$PROJ_ID"
run "$BIN" "${PROJECTS_FLAG[@]}" init "$PROJ_ID" -t "Heavy integration test topic" -v technology -d 30
assert_file "$PROJ_DIR/config.yaml"

# Seed artifacts (same shape as tests/test_placeholder_pipeline.py) — no API keys
run env PYTHONPATH="$ROOT/src" python3 - <<PY
from pathlib import Path
from PIL import Image
from video_factory.config import ensure_project_layout, save_project_config, default_project_config
from video_factory.models.schemas import (
    AssetManifest, ImageAsset, ScenePlan, SceneSpec, ScriptPackage,
    StageName, StyleBible, VisualPromptDetail,
)
from video_factory.stages.base import load_state, save_state, json_artifact
from video_factory.utils.files import atomic_write_json

project_dir = Path("$PROJ_DIR")
ensure_project_layout(project_dir)
cfg = default_project_config("$PROJ_ID", "Heavy integration test topic")
cfg.target_duration_sec = 30
save_project_config(project_dir, cfg)
Image.new("RGB", (200, 300), (255, 240, 220)).save(project_dir / "inputs" / "style_reference.png")
Image.new("RGBA", (200, 300), (255, 200, 150, 255)).save(project_dir / "inputs" / "character_reference.png")

script = ScriptPackage(
    title="Heavy Test",
    hook="Quick hook for integration.",
    full_script="Line one. Line two.",
    word_count=6,
    estimated_duration_sec=4.0,
)
atomic_write_json(json_artifact(project_dir, "script_package.json"), script.model_dump(mode="json"))
scenes = ScenePlan(
    scenes=[
        SceneSpec(scene_id="s01", narration="Line one.", start_sec=0, end_sec=2,
                  visual_prompt="abstract tech", image_prompt="abstract tech illustration"),
        SceneSpec(scene_id="s02", narration="Line two.", start_sec=2, end_sec=4,
                  visual_prompt="team planning", image_prompt="team planning editorial"),
    ]
)
atomic_write_json(json_artifact(project_dir, "scene_plan.json"), scenes.model_dump(mode="json"))
style = StyleBible(visual_style="editorial illustration")
atomic_write_json(json_artifact(project_dir, "style_bible.json"), style.model_dump(mode="json"))
prompts = [
    VisualPromptDetail(scene_id="s01", full_prompt="tech abstract", subject="chips"),
    VisualPromptDetail(scene_id="s02", full_prompt="team at board", subject="team"),
]
atomic_write_json(
    json_artifact(project_dir, "visual_prompts.json"),
    {"prompts": [p.model_dump() for p in prompts]},
)
state = load_state(project_dir)
for stage in (StageName.SCRIPT, StageName.SCENES, StageName.PROMPTS):
    state.mark_complete(stage)
save_state(project_dir, state)
print("seeded", project_dir)
PY

log "7) Pipeline CLI stages (offline images → timeline)"
run "$BIN" "${PROJECTS_FLAG[@]}" status "$PROJ_ID"
run "$BIN" "${PROJECTS_FLAG[@]}" run images "$PROJ_ID"
assert_file "$PROJ_DIR/work/json/image_candidates.json"
run "$BIN" "${PROJECTS_FLAG[@]}" candidates "$PROJ_ID"
run "$BIN" "${PROJECTS_FLAG[@]}" pick "$PROJ_ID" s01 -v v01
# Fake narration durations for timeline
run env PYTHONPATH="$ROOT/src" python3 - <<PY
from pathlib import Path
from video_factory.stages.base import json_artifact, load_state, save_state
from video_factory.models.schemas import StageName
from video_factory.utils.files import atomic_write_json

p = Path("$PROJ_DIR")
atomic_write_json(json_artifact(p, "audio_durations.json"), {"s01": 2.0, "s02": 2.0})
st = load_state(p)
st.mark_complete(StageName.NARRATION)
st.mark_complete(StageName.SUBTITLES)
save_state(p, st)
PY
run "$BIN" "${PROJECTS_FLAG[@]}" run subtitles "$PROJ_ID"
run "$BIN" "${PROJECTS_FLAG[@]}" run timeline "$PROJ_ID"
assert_file "$PROJ_DIR/work/json/timeline.json"
run "$BIN" "${PROJECTS_FLAG[@]}" status "$PROJ_ID"

log "8) Config CLI"
run "$BIN" "${PROJECTS_FLAG[@]}" config path
run "$BIN" "${PROJECTS_FLAG[@]}" config set image-backend whisk_local
CFG_OUT="$("$BIN" "${PROJECTS_FLAG[@]}" config get 2>&1)"
assert_contains "$CFG_OUT" "whisk_local"

log "9) Research stage (offline, no LLM)"
PROJ2="heavy-research-$(date +%s)"
run "$BIN" "${PROJECTS_FLAG[@]}" init "$PROJ2" -t "Research only test"
echo "# Notes for research pack" > "$DATA_DIR/projects/$PROJ2/inputs/notes.md"
run "$BIN" "${PROJECTS_FLAG[@]}" run research "$PROJ2"
assert_file "$DATA_DIR/projects/$PROJ2/work/json/research_pack.json"

log "10) Web API smoke (background server)"
PORT=39551
SESSION="vf-heavy-web"
tmux -f /exec-daemon/tmux.portal.conf has-session -t "=$SESSION" 2>/dev/null && tmux -f /exec-daemon/tmux.portal.conf kill-session -t "$SESSION" || true
tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "$SESSION" -c "$ROOT" -- "${SHELL:-bash}" -l
tmux -f /exec-daemon/tmux.portal.conf send-keys -t "$SESSION:0.0" \
  "VIDEO_FACTORY_FORCE_MANAGED=1 XDG_DATA_HOME='$XDG_DATA_HOME' XDG_CONFIG_HOME='$XDG_CONFIG_HOME' $BIN --projects '$DATA_DIR/projects' --port $PORT --no-open" C-m
sleep 2
H="$(curl -sf "http://127.0.0.1:$PORT/api/health")" && assert_contains "$H" '"ok":true'
C="$(curl -sf "http://127.0.0.1:$PORT/api/config")" && assert_contains "$C" "image_backend"
P="$(curl -sf "http://127.0.0.1:$PORT/api/projects")" && assert_contains "$P" "projects"
HTML="$(curl -sf "http://127.0.0.1:$PORT/")"
assert_contains "$HTML" "Video Factory"
tmux -f /exec-daemon/tmux.portal.conf kill-session -t "$SESSION" 2>/dev/null || true
ok "web server API"

log "11) Isolated cwd (binary not in repo — export simulation)"
ISO="$(mktemp -d)"
cp "$BIN" "$ISO/vf"
cd "$ISO"
run env VIDEO_FACTORY_FORCE_MANAGED=1 XDG_DATA_HOME="$XDG_DATA_HOME" XDG_CONFIG_HOME="$XDG_CONFIG_HOME" ./vf --projects "$DATA_DIR/projects" setup
run env VIDEO_FACTORY_FORCE_MANAGED=1 XDG_DATA_HOME="$XDG_DATA_HOME" XDG_CONFIG_HOME="$XDG_CONFIG_HOME" ./vf --projects "$DATA_DIR/projects" doctor
cd "$ROOT"

log "12) prepare-embed + rebuild integrity"
run bash scripts/prepare-embed.sh
assert_file internal/bootstrap/embedded/engine/src/video_factory/engine.py
run go build -ldflags="-s -w" -o dist/video-factory-verify ./cmd/video-factory
run env VIDEO_FACTORY_FORCE_MANAGED=1 XDG_DATA_HOME="$XDG_DATA_HOME" XDG_CONFIG_HOME="$XDG_CONFIG_HOME" ./dist/video-factory-verify --projects "$DATA_DIR/projects" doctor

echo ""
echo "════════════════════════════════════════"
echo "Heavy test summary: $PASS passed, $FAIL failed"
echo "════════════════════════════════════════"
[[ "$FAIL" -eq 0 ]]
