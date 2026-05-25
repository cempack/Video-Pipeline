package embedded

import (
	"embed"
	"io/fs"
)

// EngineVersion bump when engine package changes (invalidates managed venv).
const EngineVersion = "0.1.1"

// EngineFS contains pyproject.toml + src/video_factory (filled by make prepare-embed).
// "all:" includes Python __init__.py files (default embed skips names starting with _).
//
//go:embed all:engine/*
var EngineFS embed.FS

func EngineSubFS() (fs.FS, error) {
	return fs.Sub(EngineFS, "engine")
}
