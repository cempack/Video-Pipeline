# Video Factory

**One binary** (`video-factory`) with CLI + web UI. The Python pipeline is embedded and installed automatically on first run.

## Install (end users)

Download or build `video-factory` for your OS, then:

```bash
./video-factory setup      # once: installs Python deps into ~/.video-factory (or %LOCALAPPDATA%)
./video-factory config wizard
./video-factory doctor
./video-factory serve
```

No manual `pip install`. FFmpeg must be on PATH (see `doctor` for install hints).

| Platform | Data directory | FFmpeg hint |
|----------|----------------|-------------|
| **macOS** | `~/Library/Application Support/video-factory` | `brew install ffmpeg` |
| **Linux** | `~/.local/share/video-factory` | `apt install ffmpeg` |
| **Windows** | `%LOCALAPPDATA%\video-factory` | `winget install Gyan.FFmpeg` |

### If Python is missing

`setup` downloads a standalone Python 3.12 (~50MB) for your OS/arch (linux/mac/windows amd64/arm64).

### Build from source

```bash
make build    # runs prepare-embed + go build → dist/video-factory
make release  # linux + mac + windows binaries in dist/
```

Developers in the repo can skip the managed bundle: the tool detects `pyproject.toml` + `src/video_factory` and uses the repo directly (still creates a managed venv for deps).

Force managed mode (test export behaviour):

```bash
VIDEO_FACTORY_FORCE_MANAGED=1 ./dist/video-factory setup
```

## CLI

```bash
video-factory init <id> -t "Topic"
video-factory status <id>
video-factory run <stage> <id>
video-factory run all <id> --resume
video-factory pick <id> s01 -v v02
video-factory config wizard
video-factory serve
```

## Web UI

```bash
video-factory serve --port 3847
```

## Whisk visuals

Add `inputs/style_reference.png` and `inputs/character_reference.png` to each project (from Google Whisk).

## Tests (developers)

```bash
pip install -e ".[dev]"
PYTHONPATH=src python3 -m pytest -q
```
