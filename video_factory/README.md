# Video Factory

Short-form video pipeline: **Go app** (CLI + web UI) + **Python engine** (render pipeline).

## Install

```bash
cd video_factory
make build                 # → dist/video-factory (~6MB)
pip install -e .           # Python engine (required)
```

## Quick start

```bash
./dist/video-factory config wizard
./dist/video-factory doctor
./dist/video-factory init my-demo -t "Your topic"
./dist/video-factory serve    # http://127.0.0.1:3847
```

## CLI

```bash
video-factory init <id> -t "Topic"
video-factory status <id>
video-factory run <stage> <id>      # research, script, scenes, …
video-factory run all <id> --resume
video-factory pick <id> s01 -v v02
video-factory approve script <id>
video-factory candidates <id>
video-factory library add img.png -d "description"

video-factory config wizard
video-factory config set gemini-api-key <key>
video-factory config set-secret gemini-api-key
video-factory doctor
video-factory serve
```

## Web UI

Dark, minimal interface — projects, per-stage runs, API settings.

```bash
./dist/video-factory serve --port 3847
```

## Configure Gemini

```bash
./dist/video-factory config wizard
# or
./dist/video-factory config set gemini-api-key YOUR_KEY
```

Stored in `~/.config/video-factory/config.json` and synced to `video_factory/.env`.

## Whisk-style visuals

Add `inputs/style_reference.png` and `inputs/character_reference.png` (from Google Whisk).  
Set `image_backend: whisk_local` or `whisk_gemini` in project `config.yaml`.

## Requirements

- Go 1.22+ (build)
- Python 3.11+ (`pip install -e .`)
- FFmpeg
- Gemini + ElevenLabs API keys

## Layout

```
video_factory/
  cmd/video-factory/       # Go binary source
  dist/video-factory       # compiled CLI + web
  internal/                # Go: cli, web, config
  src/video_factory/       # Python engine only
    engine.py              # entry for Go
    pipeline.py            # stages registry
  projects/
```

## Tests

```bash
PYTHONPATH=src python3 -m pytest -q
```
