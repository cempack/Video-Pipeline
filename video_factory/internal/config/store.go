package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// Store holds API keys and tool paths (~/.config/video-factory/config.json).
type Store struct {
	GeminiAPIKey        string `json:"gemini_api_key"`
	ElevenLabsAPIKey    string `json:"elevenlabs_api_key"`
	ElevenLabsVoiceID   string `json:"elevenlabs_voice_id"`
	GeminiModel         string `json:"gemini_model"`
	GeminiImageModel    string `json:"gemini_image_model"`
	FFmpegBin           string `json:"ffmpeg_bin"`
	FFprobeBin          string `json:"ffprobe_bin"`
	ImageBackend        string `json:"image_backend"`
	ProjectsDir         string `json:"projects_dir"`
	PythonBin           string `json:"python_bin"`
	VideoFactoryRoot    string `json:"video_factory_root"`
}

func DefaultStore() Store {
	return Store{
		GeminiModel:      "gemini-2.0-flash",
		GeminiImageModel: "gemini-2.0-flash-exp-image-generation",
		FFmpegBin:        "ffmpeg",
		FFprobeBin:       "ffprobe",
		ImageBackend:     "whisk_local",
		ProjectsDir:      "projects",
		PythonBin:        "python3",
	}
}

func ConfigDir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		home, e := os.UserHomeDir()
		if e != nil {
			return "", e
		}
		base = filepath.Join(home, ".config")
	}
	dir := filepath.Join(base, "video-factory")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	return dir, nil
}

func ConfigPath() (string, error) {
	dir, err := ConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "config.json"), nil
}

func Load() (Store, error) {
	s := DefaultStore()
	path, err := ConfigPath()
	if err != nil {
		return s, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			_ = mergeEnv(&s)
			return s, nil
		}
		return s, err
	}
	if err := json.Unmarshal(data, &s); err != nil {
		return s, err
	}
	_ = mergeEnv(&s)
	return s, nil
}

func Save(s Store) error {
	path, err := ConfigPath()
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o600)
}

func mergeEnv(s *Store) error {
	if v := os.Getenv("GEMINI_API_KEY"); v != "" {
		s.GeminiAPIKey = v
	}
	if v := os.Getenv("ELEVENLABS_API_KEY"); v != "" {
		s.ElevenLabsAPIKey = v
	}
	if v := os.Getenv("ELEVENLABS_VOICE_ID"); v != "" {
		s.ElevenLabsVoiceID = v
	}
	if v := os.Getenv("FFMPEG_BIN"); v != "" {
		s.FFmpegBin = v
	}
	if v := os.Getenv("FFPROBE_BIN"); v != "" {
		s.FFprobeBin = v
	}
	if v := os.Getenv("IMAGE_BACKEND"); v != "" {
		s.ImageBackend = v
	}
	return nil
}

// WriteDotEnv writes video_factory/.env from store (for Python engine).
func (s Store) WriteDotEnv(root string) error {
	envPath := filepath.Join(root, ".env")
	lines := []string{
		"GEMINI_API_KEY=" + s.GeminiAPIKey,
		"ELEVENLABS_API_KEY=" + s.ElevenLabsAPIKey,
		"ELEVENLABS_VOICE_ID=" + s.ElevenLabsVoiceID,
		"GEMINI_MODEL=" + s.GeminiModel,
		"GEMINI_IMAGE_MODEL=" + s.GeminiImageModel,
		"FFMPEG_BIN=" + s.FFmpegBin,
		"FFPROBE_BIN=" + s.FFprobeBin,
		"IMAGE_BACKEND=" + s.ImageBackend,
	}
	return os.WriteFile(envPath, []byte(strings.Join(lines, "\n")+"\n"), 0o600)
}

func MaskSecret(s string) string {
	if len(s) <= 8 {
		if s == "" {
			return "(not set)"
		}
		return "****"
	}
	return s[:4] + "…" + s[len(s)-4:]
}
