# Video Factory

Python pipeline for short-form video + **Go control plane** (small ~6MB binary, web UI, intuitive CLI).

## Two ways to run

| | **Go app (recommended)** | Python CLI (legacy) |
|---|------------------------|---------------------|
| Install | `make build` → `dist/video-factory` | `pip install -e .` |
| Command | `./dist/video-factory` | `video-factory-py` |
| Web UI | `./dist/video-factory serve` | — |
| Config | `video-factory config wizard` | `.env` file |

The Go binary orchestrates the same Python engine — **no features removed**.

## Quick start

```bash
cd video_factory
make build          # compiles dist/video-factory
pip install -e .    # Python engine (required once)

./dist/video-factory config wizard   # Gemini + ElevenLabs keys
./dist/video-factory doctor          # verify setup

./dist/video-factory init my-demo -t "Your topic"
./dist/video-factory serve           # open http://127.0.0.1:3847

# Or CLI-only:
./dist/video-factory run all my-demo --resume
```

## Go CLI (intuitive commands)

```bash
video-factory init <id> -t "Topic"     # create project
video-factory status <id>              # pipeline progress
video-factory run <stage> <id>         # run one stage
video-factory run all <id>             # full pipeline (--resume default)
video-factory pick <id> s01 -v v02     # select image variant
video-factory approve script <id>      # human gate
video-factory candidates <id>          # list variants
video-factory library add img.png -d "description"

video-factory config wizard            # interactive API setup
video-factory config set gemini-api-key <key>
video-factory config set-secret gemini-api-key   # hidden input
video-factory config get
video-factory doctor
video-factory serve                    # web UI
```

Stages: `research`, `script`, `scenes`, `prompts`, `character`, `images`, `narration`, `subtitles`, `timeline`, `render`, `qa`

## Web UI

Cursor-inspired dark interface:

- **Projects** — create, select, run any stage, run all, approve script
- **Settings** — Gemini & ElevenLabs keys (saved to `~/.config/video-factory/config.json` + synced `.env`)
- **Quick guide** — Whisk references workflow

```bash
./dist/video-factory serve --port 3847
```

## Configure Gemini from CLI

```bash
# Interactive
./dist/video-factory config wizard

# Direct
./dist/video-factory config set gemini-api-key YOUR_KEY
./dist/video-factory config set gemini-model gemini-2.0-flash
./dist/video-factory config set gemini-image-model gemini-2.0-flash-exp-image-generation

# No echo
./dist/video-factory config set-secret gemini-api-key
```

Config path: `video-factory config path`

## Whisk-style visual coherence

See previous sections in this README — `inputs/style_reference.png`, `inputs/character_reference.png`, `whisk_local` / `whisk_gemini`, face lock.

## Requirements

- **Go 1.22+** — build the binary
- **Python 3.11+** — pipeline engine
- **FFmpeg** — render
- **API keys** — Gemini (script/images), ElevenLabs (narration)

## Project layout

```
video_factory/
  cmd/video-factory/     # Go entry
  internal/cli/          # Cobra commands
  internal/web/          # Embedded web UI
  internal/config/       # API key store
  dist/video-factory     # compiled binary (after make build)
  src/video_factory/     # Python pipeline
  projects/
```

## Python tests

```bash
PYTHONPATH=src python3 -m pytest -q
```

## All features preserved

- 11 pipeline stages including character sheet & Whisk images
- 4 image variants + `pick` / `candidates`
- Script approval gate
- Asset library
- Silence removal, scene beats, title QA
- Batch prompt file, markdown skill files
- Resume / force flags
