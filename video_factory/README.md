# Video Factory

## Use it (normal)

```bash
make build
./dist/video-factory
```

Your browser opens to **http://127.0.0.1:3847** with a setup wizard:

1. Welcome (dependencies install on first run)
2. Paste your **Gemini API key** ([get one](https://aistudio.google.com/apikey))
3. Create your first project

Then use the **Projects** screen: **Run all** runs the pipeline. Add Whisk reference images under `projects/<id>/inputs/` when you want stronger visual consistency.

Press **Ctrl+C** in the terminal to stop the app.

### Options

```bash
./dist/video-factory --no-open    # don't launch browser automatically
./dist/video-factory --port 8080  # different port
```

### FFmpeg

Only needed for the final **render** step. The wizard warns you if it’s missing:

- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`
- **Windows:** `winget install Gyan.FFmpeg`

## Developers

```bash
make build
make test
make heavy-test
PYTHONPATH=src python3 -m pytest -q
```
