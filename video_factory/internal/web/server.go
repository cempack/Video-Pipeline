package web

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"path/filepath"
	"strings"

	appcfg "github.com/cempack/video-pipeline/video_factory/internal/config"
	"github.com/cempack/video-pipeline/video_factory/internal/python"
)

//go:embed static/*
var staticFS embed.FS

type Server struct {
	runner *python.Runner
	store  appcfg.Store
}

func Serve(addr string, runner *python.Runner, store appcfg.Store) error {
	s := &Server{runner: runner, store: store}
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/config", s.handleConfig)
	mux.HandleFunc("/api/projects", s.handleProjects)
	mux.HandleFunc("/api/project/", s.handleProject)
	mux.Handle("/static/", http.FileServer(http.FS(staticFS)))
	return http.ListenAndServe(addr, mux)
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	data, err := staticFS.ReadFile("static/index.html")
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(data)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{"ok": true})
}

func (s *Server) handleConfig(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		st, _ := appcfg.Load()
		jsonOK(w, map[string]any{
			"gemini_set":     st.GeminiAPIKey != "",
			"elevenlabs_set": st.ElevenLabsAPIKey != "",
			"gemini_model":   st.GeminiModel,
			"image_backend":  st.ImageBackend,
			"projects_dir":   s.runner.ProjectsDir,
		})
	case http.MethodPost:
		var body struct {
			GeminiAPIKey      string `json:"gemini_api_key"`
			ElevenLabsAPIKey  string `json:"elevenlabs_api_key"`
			ElevenLabsVoiceID string `json:"elevenlabs_voice_id"`
			GeminiModel       string `json:"gemini_model"`
			GeminiImageModel  string `json:"gemini_image_model"`
			ImageBackend      string `json:"image_backend"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			jsonErr(w, err.Error(), 400)
			return
		}
		st, err := appcfg.Load()
		if err != nil {
			jsonErr(w, err.Error(), 500)
			return
		}
		if body.GeminiAPIKey != "" {
			st.GeminiAPIKey = body.GeminiAPIKey
		}
		if body.ElevenLabsAPIKey != "" {
			st.ElevenLabsAPIKey = body.ElevenLabsAPIKey
		}
		if body.ElevenLabsVoiceID != "" {
			st.ElevenLabsVoiceID = body.ElevenLabsVoiceID
		}
		if body.GeminiModel != "" {
			st.GeminiModel = body.GeminiModel
		}
		if body.GeminiImageModel != "" {
			st.GeminiImageModel = body.GeminiImageModel
		}
		if body.ImageBackend != "" {
			st.ImageBackend = body.ImageBackend
		}
		if err := appcfg.Save(st); err != nil {
			jsonErr(w, err.Error(), 500)
			return
		}
		_ = st.WriteDotEnv(s.runner.Root)
		jsonOK(w, map[string]any{"ok": true})
	default:
		http.Error(w, "method not allowed", 405)
	}
}

func (s *Server) handleProjects(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		out, stderr, err := s.runner.Run(append([]string{"list_projects"}, s.runner.ProjectsFlag()...)...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	case http.MethodPost:
		var body struct {
			ID       string `json:"id"`
			Topic    string `json:"topic"`
			Vertical string `json:"vertical"`
			Duration int    `json:"duration"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			jsonErr(w, err.Error(), 400)
			return
		}
		if body.ID == "" || body.Topic == "" {
			jsonErr(w, "id and topic required", 400)
			return
		}
		if body.Vertical == "" {
			body.Vertical = "technology"
		}
		if body.Duration == 0 {
			body.Duration = 45
		}
		args := []string{
			"init_project", body.ID,
			"--topic", body.Topic,
			"--vertical", body.Vertical,
			"--duration", fmt.Sprintf("%d", body.Duration),
		}
		args = append(args, s.runner.ProjectsFlag()...)
		out, stderr, err := s.runner.Run(args...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	default:
		http.Error(w, "method not allowed", 405)
	}
}

func (s *Server) handleProject(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/api/project/")
	parts := strings.Split(strings.Trim(rest, "/"), "/")
	if len(parts) < 1 || parts[0] == "" {
		jsonErr(w, "project id required", 400)
		return
	}
	id := parts[0]
	base := append([]string{id}, s.runner.ProjectsFlag()...)

	if len(parts) == 1 {
		if r.Method != http.MethodGet {
			http.Error(w, "method not allowed", 405)
			return
		}
		out, stderr, err := s.runner.Run(append([]string{"status"}, base...)...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
		return
	}

	switch parts[1] {
	case "run":
		if len(parts) < 3 {
			jsonErr(w, "stage required", 400)
			return
		}
		stage := parts[2]
		force := r.URL.Query().Get("force") == "1"
		args := []string{"run_stage", stage, id}
		args = append(args, s.runner.ProjectsFlag()...)
		if force {
			args = append(args, "--force")
		}
		if stage == "all" && r.URL.Query().Get("resume") != "0" {
			// default resume on
		} else if stage == "all" {
			args = append(args, "--no-resume")
		}
		out, stderr, err := s.runner.Run(args...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	case "approve":
		if len(parts) < 3 {
			jsonErr(w, "stage required", 400)
			return
		}
		out, stderr, err := s.runner.Run(append([]string{"approve", parts[2], id}, s.runner.ProjectsFlag()...)...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	case "candidates":
		out, stderr, err := s.runner.Run(append([]string{"candidates", id}, s.runner.ProjectsFlag()...)...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	case "select-image":
		if r.Method != http.MethodPost {
			http.Error(w, "POST required", 405)
			return
		}
		var body struct {
			SceneID string `json:"scene_id"`
			Variant string `json:"variant"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			jsonErr(w, err.Error(), 400)
			return
		}
		args := append([]string{"select_image", id, body.SceneID, body.Variant}, s.runner.ProjectsFlag()...)
		out, stderr, err := s.runner.Run(args...)
		if err != nil {
			jsonErr(w, stderr+err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(out))
	case "asset":
		if len(parts) < 3 {
			jsonErr(w, "path required", 400)
			return
		}
		s.serveAsset(w, r, id, parts[2])
	default:
		jsonErr(w, "unknown action", 404)
	}
}

func (s *Server) serveAsset(w http.ResponseWriter, r *http.Request, projectID, rel string) {
	root := filepath.Join(s.runner.ProjectsDir, projectID)
	path := filepath.Join(root, filepath.Clean("/"+rel))
	if !strings.HasPrefix(path, root) {
		http.Error(w, "forbidden", 403)
		return
	}
	http.ServeFile(w, r, path)
}

func jsonOK(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func jsonErr(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func readBody(r *http.Request) ([]byte, error) {
	return io.ReadAll(r.Body)
}
