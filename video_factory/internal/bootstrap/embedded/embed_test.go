package embedded

import (
	"testing"
)

func TestEmbedIncludesPythonInitFiles(t *testing.T) {
	paths := []string{
		"engine/src/video_factory/__init__.py",
		"engine/src/video_factory/stages/__init__.py",
		"engine/src/video_factory/adapters/__init__.py",
	}
	for _, p := range paths {
		if _, err := EngineFS.ReadFile(p); err != nil {
			t.Fatalf("missing embedded %s (run make prepare-embed before tests): %v", p, err)
		}
	}
}
