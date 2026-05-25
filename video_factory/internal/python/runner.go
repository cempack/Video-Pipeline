package python

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	appcfg "github.com/cempack/video-pipeline/video_factory/internal/config"
)

// Runner invokes the Python pipeline engine.
type Runner struct {
	Root       string
	PythonBin  string
	ProjectsDir string
}

func NewRunner(store appcfg.Store) (*Runner, error) {
	root := store.VideoFactoryRoot
	if root == "" {
		root = findVideoFactoryRoot()
	}
	if root == "" {
		return nil, fmt.Errorf("video_factory root not found; run from repo or set video_factory_root in config")
	}
	if err := store.WriteDotEnv(root); err != nil {
		return nil, err
	}
	py := store.PythonBin
	if py == "" {
		py = "python3"
	}
	projects := store.ProjectsDir
	if projects == "" {
		projects = "projects"
	}
	if !filepath.IsAbs(projects) {
		projects = filepath.Join(root, projects)
	}
	return &Runner{Root: root, PythonBin: py, ProjectsDir: projects}, nil
}

func findVideoFactoryRoot() string {
	cwd, _ := os.Getwd()
	for dir := cwd; dir != "/" && dir != "."; dir = filepath.Dir(dir) {
		if _, err := os.Stat(filepath.Join(dir, "pyproject.toml")); err == nil {
			if _, err := os.Stat(filepath.Join(dir, "src", "video_factory")); err == nil {
				return dir
			}
		}
	}
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	dir := filepath.Dir(exe)
	for i := 0; i < 6; i++ {
		if _, err := os.Stat(filepath.Join(dir, "src", "video_factory")); err == nil {
			return dir
		}
		dir = filepath.Dir(dir)
	}
	return ""
}

func (r *Runner) Run(args ...string) (stdout, stderr string, err error) {
	cmdArgs := append([]string{"-m", "video_factory.engine"}, args...)
	cmd := exec.Command(r.PythonBin, cmdArgs...)
	cmd.Dir = r.Root
	cmd.Env = append(os.Environ(),
		"PYTHONPATH="+filepath.Join(r.Root, "src"),
		"VF_HEADLESS=1",
	)
	var outBuf, errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err = cmd.Run()
	return outBuf.String(), errBuf.String(), err
}

func (r *Runner) ProjectsFlag() []string {
	return []string{"--projects-dir", r.ProjectsDir}
}

func (r *Runner) CheckPython() error {
	cmd := exec.Command(r.PythonBin, "--version")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("python not found (%s): install Python 3.11+ and pip install -e video_factory", r.PythonBin)
	}
	_, stderr, err := r.Run("ping")
	if err != nil {
		if strings.Contains(stderr, "No module named") {
			return fmt.Errorf("video_factory package not installed: cd %s && pip install -e .", r.Root)
		}
		return fmt.Errorf("engine check failed: %s", stderr)
	}
	return nil
}
