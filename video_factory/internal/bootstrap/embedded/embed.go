package embedded

import (
	"embed"
	"io/fs"
)

// EngineVersion bump when engine package changes (invalidates managed venv).
const EngineVersion = "0.1.0"

// EngineFS contains pyproject.toml + src/video_factory (filled by make prepare-embed).
//
//go:embed engine/*
var EngineFS embed.FS

func EngineSubFS() (fs.FS, error) {
	return fs.Sub(EngineFS, "engine")
}
