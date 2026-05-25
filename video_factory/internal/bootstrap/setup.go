package bootstrap

import (
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/cempack/video-pipeline/video_factory/internal/bootstrap/embedded"
)

// Env is a ready-to-run Python engine environment.
type Env struct {
	Root       string // directory with pyproject.toml (engine source / install root)
	PythonBin  string // venv python executable
	ProjectsDir string
	VenvDir    string
}

// Ensure installs or reuses managed engine under the user data dir.
// Exported binaries embed the Python package and install deps into ~/.video-factory/venv.
func Ensure(onStatus func(string)) (*Env, error) {
	if onStatus == nil {
		onStatus = func(string) {}
	}

	dataDir, err := DataDir()
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		return nil, err
	}

	engineDir, err := materializeEngine(dataDir, onStatus)
	if err != nil {
		return nil, err
	}

	venvDir := filepath.Join(dataDir, "venv")
	stamp := filepath.Join(dataDir, "engine-"+embedded.EngineVersion+".ready")
	needInstall := true
	if _, err := os.Stat(stamp); err == nil {
		if _, err := os.Stat(venvPython(venvDir)); err == nil {
			needInstall = false
		}
	}

	if needInstall {
		onStatus("Setting up Python environment (first run may take a few minutes)…")
		pyCmd, err := pythonCommand(onStatus)
		if err != nil {
			return nil, err
		}
		if err := os.RemoveAll(venvDir); err != nil && !os.IsNotExist(err) {
			return nil, err
		}
		if err := createVenv(engineDir, pyCmd, venvDir, onStatus); err != nil {
			return nil, err
		}
		venvPy := venvPython(venvDir)
		if err := runCmd(engineDir, venvPy, []string{"-m", "pip", "install", "--upgrade", "pip"}, nil); err != nil {
			return nil, fmt.Errorf("upgrade pip: %w", err)
		}
		onStatus("Installing pipeline dependencies…")
		reqFile := filepath.Join(engineDir, "requirements.txt")
		if _, err := os.Stat(reqFile); err != nil {
			return nil, fmt.Errorf("missing requirements.txt in engine bundle")
		}
		if err := runCmd(engineDir, venvPy, []string{"-m", "pip", "install", "-r", reqFile}, nil); err != nil {
			return nil, fmt.Errorf("pip install dependencies: %w", err)
		}
		_ = os.WriteFile(stamp, []byte(embedded.EngineVersion), 0o644)
		onStatus("Python environment ready.")
	}

	projects := filepath.Join(dataDir, "projects")
	_ = os.MkdirAll(projects, 0o755)
	if dev := findDevEngineRoot(); dev != "" {
		projects = filepath.Join(dev, "projects")
		_ = os.MkdirAll(projects, 0o755)
	}

	return &Env{
		Root:        engineDir,
		PythonBin:   venvPython(venvDir),
		ProjectsDir: projects,
		VenvDir:     venvDir,
	}, nil
}

func materializeEngine(dataDir string, onStatus func(string)) (string, error) {
	if dev := findDevEngineRoot(); dev != "" {
		onStatus("Using development engine: " + dev)
		return dev, nil
	}
	target := filepath.Join(dataDir, "engine-src-"+embedded.EngineVersion)
	stamp := filepath.Join(target, ".extracted")
	if _, err := os.Stat(stamp); err == nil {
		return target, nil
	}
	onStatus("Extracting embedded engine…")
	if err := os.RemoveAll(target); err != nil && !os.IsNotExist(err) {
		return "", err
	}
	if err := os.MkdirAll(target, 0o755); err != nil {
		return "", err
	}
	sub, err := embedded.EngineSubFS()
	if err != nil {
		return "", err
	}
	if err := copyFS(sub, ".", target); err != nil {
		return "", err
	}
	_ = os.WriteFile(stamp, []byte("ok"), 0o644)
	return target, nil
}

func copyFS(fsys fs.FS, src, dest string) error {
	return fs.WalkDir(fsys, src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel := strings.TrimPrefix(path, src)
		rel = strings.TrimPrefix(rel, "/")
		if rel == "" || rel == "." {
			return nil
		}
		dst := filepath.Join(dest, rel)
		if d.IsDir() {
			return os.MkdirAll(dst, 0o755)
		}
		data, err := fs.ReadFile(fsys, path)
		if err != nil {
			return err
		}
		return os.WriteFile(dst, data, 0o644)
	})
}

func findDevEngineRoot() string {
	cwd, _ := os.Getwd()
	for dir := cwd; dir != "/" && dir != "."; dir = filepath.Dir(dir) {
		if isEngineRoot(dir) {
			return dir
		}
	}
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	dir := filepath.Dir(exe)
	for i := 0; i < 8; i++ {
		if isEngineRoot(dir) {
			return dir
		}
		dir = filepath.Dir(dir)
	}
	return ""
}

func isEngineRoot(dir string) bool {
	if os.Getenv("VIDEO_FACTORY_FORCE_MANAGED") == "1" {
		return false
	}
	_, err1 := os.Stat(filepath.Join(dir, "pyproject.toml"))
	_, err2 := os.Stat(filepath.Join(dir, "src", "video_factory", "engine.py"))
	return err1 == nil && err2 == nil
}

func createVenv(engineDir string, pyCmd []string, venvDir string, onStatus func(string)) error {
	err := runCmd(engineDir, pyCmd[0], append(pyCmd[1:], "-m", "venv", venvDir), nil)
	if err == nil {
		return nil
	}
	onStatus("System Python cannot create venv — switching to standalone Python runtime…")
	dataDir, derr := DataDir()
	if derr != nil {
		return fmt.Errorf("create venv: %w", derr)
	}
	embeddedRoot := filepath.Join(dataDir, "python-runtime")
	bin, derr := ensureEmbeddedPython(embeddedRoot, onStatus)
	if derr != nil {
		return fmt.Errorf("create venv: %w (also failed to download standalone Python: %v)", err, derr)
	}
	_ = os.RemoveAll(venvDir)
	abs, _ := filepath.Abs(bin)
	return runCmd(engineDir, abs, []string{"-m", "venv", venvDir}, nil)
}

func pythonCommand(onStatus func(string)) ([]string, error) {
	if p := os.Getenv("VIDEO_FACTORY_PYTHON"); p != "" {
		return []string{p}, nil
	}
	for _, name := range []string{"python3", "python"} {
		if path, err := exec.LookPath(name); err == nil {
			if versionOK(path) {
				return []string{path}, nil
			}
		}
	}
	if goosWindows() {
		for _, ver := range []string{"-3.13", "-3.12", "-3.11"} {
			if py, err := exec.LookPath("py"); err == nil {
				if versionOKPy(py, ver) {
					return []string{py, ver}, nil
				}
			}
		}
	}
	onStatus("No system Python found — downloading standalone runtime…")
	dataDir, err := DataDir()
	if err != nil {
		return nil, err
	}
	embeddedRoot := filepath.Join(dataDir, "python-runtime")
	bin, err := ensureEmbeddedPython(embeddedRoot, onStatus)
	if err != nil {
		return nil, err
	}
	return []string{bin}, nil
}

func ensureEmbeddedPython(root string, onStatus func(string)) (string, error) {
	if bin := findPythonInTree(root); bin != "" {
		return bin, nil
	}
	if err := os.MkdirAll(root, 0o755); err != nil {
		return "", err
	}
	if err := downloadEmbeddedPython(root, onStatus); err != nil {
		return "", err
	}
	if bin := findPythonInTree(root); bin != "" {
		return bin, nil
	}
	return "", fmt.Errorf("embedded python not found under %s after extract", root)
}

func findPythonInTree(root string) string {
	candidates := []string{
		filepath.Join(root, "python", "bin", "python3"),
		filepath.Join(root, "python", "bin", "python3.12"),
		filepath.Join(root, "python", "bin", "python.exe"),
	}
	for _, c := range candidates {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			abs, _ := filepath.Abs(c)
			return abs
		}
	}
	return ""
}

func versionOK(py string) bool {
	out, err := runOutput(py, "--version")
	return err == nil && (strings.Contains(string(out), "3.11") ||
		strings.Contains(string(out), "3.12") || strings.Contains(string(out), "3.13"))
}

func versionOKPy(py, ver string) bool {
	out, err := runOutput(py, ver, "--version")
	return err == nil && strings.Contains(string(out), "Python 3.")
}

func goosWindows() bool {
	return runtime.GOOS == "windows"
}

// CheckFFmpeg verifies ffmpeg is available.
func CheckFFmpeg() error {
	if p, err := exec.LookPath("ffmpeg"); err == nil && p != "" {
		return nil
	}
	return fmt.Errorf("ffmpeg not found — %s", ffmpegInstallHint())
}

func ffmpegInstallHint() string {
	switch runtime.GOOS {
	case "windows":
		return "install: winget install Gyan.FFmpeg  OR  choco install ffmpeg"
	case "darwin":
		return "install: brew install ffmpeg"
	default:
		return "install: sudo apt install ffmpeg  OR  sudo dnf install ffmpeg"
	}
}
