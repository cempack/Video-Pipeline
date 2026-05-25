# Video Factory

Python-first pipeline that turns a topic prompt into a short-form vertical video: research pack, script, scene plan, visuals, voiceover, subtitles, and FFmpeg render. Each stage is a separate, rerunnable CLI command with persisted JSON artifacts.

## Requirements

- Python 3.11+
- FFmpeg and ffprobe on `PATH` (subtitle burn-in needs libass-enabled builds)
- API keys (for full pipeline): `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`

## Install

```bash
cd video_factory
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your keys
```

## Quick start

```bash
video-factory init-project my-video --topic "Stoicism for busy engineers" --vertical philosophy

# Optional: edit projects/my-video/inputs/notes.md and sources.txt

video-factory run research my-video
video-factory run script my-video
video-factory run scenes my-video
video-factory run prompts my-video
video-factory run images my-video
video-factory run narration my-video
video-factory run subtitles my-video
video-factory run timeline my-video
video-factory run render my-video
video-factory run qa my-video

# Or resume from last completed stage:
video-factory run all my-video --resume
```

## Project layout

Each project lives under `projects/<project_id>/`:

| Path | Purpose |
|------|---------|
| `config.yaml` | Creative settings (topic, duration, vertical, voice) |
| `inputs/` | Notes, sources, manual briefs |
| `work/` | JSON plans, images, audio, subtitles |
| `outputs/` | `final_clean.mp4`, `final_subtitled.mp4`, `qa_report.json` |
| `logs/` | Pipeline log |
| `state.json` | Stage completion and artifact hashes |

## Stages

1. **research** — Normalize `inputs/notes.md` into `research_pack.json`
2. **script** — Gemini draft + compression pass → `script_package.json`
3. **scenes** — Visual beat segmentation → `scene_plan.json`
4. **prompts** — Per-scene image prompts + `style_bible.json`
5. **images** — Placeholder or custom image backend → `work/images/`
6. **narration** — ElevenLabs per-scene TTS + concatenated voiceover
7. **subtitles** — SRT/VTT from measured audio durations
8. **timeline** — `timeline.json` render manifest
9. **render** — FFmpeg Ken Burns clips, concat, mux, optional subtitle burn-in
10. **qa** — Duration, resolution, asset, and subtitle checks

## Adapters

| Adapter | Env | Role |
|---------|-----|------|
| `GeminiLLMWriter` | `GEMINI_API_KEY`, `GEMINI_MODEL` | Script, scenes, prompts |
| `ElevenLabsNarrationProvider` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | TTS |
| `PlaceholderImageProvider` | `IMAGE_BACKEND=placeholder` | Local dev images |
| `FFmpegAdapter` | `FFMPEG_BIN`, `FFPROBE_BIN` | Probe, render, subtitles |

Swap providers by implementing the `LLMWriter`, `NarrationProvider`, and `ImageProvider` protocols without changing stage orchestration.

## Offline / CI testing

Placeholder images and unit tests run without API keys:

```bash
pytest -q
```

## Design notes

- **Deterministic artifacts**: Every stage writes JSON under `work/` or `outputs/`.
- **Resumable**: `state.json` tracks completion; `run all --resume` skips finished stages.
- **Fail loudly**: Stages validate prerequisites via `require_stage`.
- **No publishing**: Outputs are local MP4 files only.

## Whisk-style visual coherence

The pipeline mimics [Google Whisk](https://labs.google/fx/tools/whisk): **style board + character subject + scene prompt**.

1. Export from Whisk (or paint in MS Paint) into:
   - `inputs/style_reference.png` — full style board (palette, line weight, texture)
   - `inputs/character_reference.png` — canonical character (face + outfit)
2. Set in `config.yaml`:
   ```yaml
   image_backend: whisk_local   # offline: palette lock + face composite
   # image_backend: whisk_gemini  # API: Gemini image + same postprocess
   enforce_face_lock: true
   style_reference: inputs/style_reference.png
   character_reference: inputs/character_reference.png
   ```
3. `whisk_local` applies palette harmonization, style texture blend, and **automated face lock** (same character anchor every scene — Bog’s Premiere fix, built-in).
4. `whisk_gemini` sends both reference images to Gemini with strict “do not change the face” prompts, then runs the same post-pass.

Replace template PNGs from `init-project` with your real Whisk exports for production quality.

## Faceless-channel production techniques

Inspired by real AI YouTube workflows (e.g. static-illustration channels using ElevenLabs + batch image gen):

| Technique | Config / CLI | What it does |
|-----------|--------------|--------------|
| **~3s still frames** | `scene_beat_sec: 3.0` | Scene planner targets one image every ~3 seconds |
| **4-up image review** | `image_variants_per_scene: 4` | Saves `s01_v01.png`…`s01_v04.png`; pick with `video-factory select-image PROJECT s01 --variant v02` |
| **Variant listing** | `video-factory candidates PROJECT` | Table of scenes and variants |
| **Remove TTS silence** | `remove_silence: true` | FFmpeg `silenceremove` on each scene clip (clean AI gaps) |
| **ElevenLabs continuity** | (built-in) | `previous_text` / `next_text` across scene chunks |
| **Style lock** | `inputs/style_reference.png` + `style_reference` in config | Prompts + placeholder strip mimic Whisk-style consistency |
| **Character reference** | `character_reference` in config | Instructions lock face/expression across scenes |
| **Batch prompts file** | `inputs/batch_image_prompts.txt` | One prompt per line (auto-whisk style batch) |
| **Asset library** | `library/` + `use_asset_library` | Reuse indexed images; `video-factory library-add img.png --desc "..."` |
| **Script approval gate** | `require_script_approval: true` | `video-factory approve script PROJECT` before scenes |
| **Project skill files** | `inputs/script.md`, `inputs/scenes.md` | Markdown instructions merged into Gemini prompts (improves over time as you edit) |
| **Title length QA** | `max_title_chars: 60` | Checks title fits mobile homepage in QA |
| **Optional loudness drift** | `audio_loudness_variation: true` | Subtle per-scene level variation |

Example quality-first workflow:

```bash
video-factory run script my-video
# Edit work/json/script_package.json, then:
video-factory approve script my-video
video-factory run scenes my-video
video-factory run images my-video
video-factory candidates my-video
video-factory select-image my-video s03 --variant v02
video-factory run narration my-video
video-factory run all my-video --resume
```

## Example project

See `projects/2026-05-23-example-topic/` for a starter config, `inputs/script.md`, and research notes.
