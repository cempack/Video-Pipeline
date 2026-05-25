package python

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	appcfg "github.com/cempack/video-pipeline/video_factory/internal/config"
	"github.com/cempack/video-pipeline/video_factory/internal/bootstrap"
)

// Runner invokes the Python pipeline engine.
type Runner struct {
	Root        string
	PythonBin   string
	ProjectsDir string
}

func NewRunner(store appcfg.Store) (*Runner, error) {
	env, err := bootstrap.Ensure(func(msg string) { fmt.Fprintln(os.Stderr, msg) })
	if err != nil {
		return nil, err
	}
	return fromStoreAndEnv(store, env)
}

func fromStoreAndEnv(store appcfg.Store, env *bootstrap.Env) (*Runner, error) {
	root := env.Root
	if store.VideoFactoryRoot != "" {
		root = store.VideoFactoryRoot
	}
	if err := store.WriteDotEnv(root); err != nil {
		return nil, err
	}
	projects := env.ProjectsDir
	if store.ProjectsDir != "" {
		projects = store.ProjectsDir
		if !filepath.IsAbs(projects) {
			projects = filepath.Join(root, projects)
		}
	}
	py := env.PythonBin
	if store.PythonBin != "" {
		py = store.PythonBin
	}
	return &Runner{Root: root, PythonBin: py, ProjectsDir: projects}, nil
}

func (r *Runner) Run(args ...string) (stdout, stderr string, err error) {
	cmdArgs := append([]string{"-m", "video_factory.engine"}, args...)
	cmd := exec.Command(r.PythonBin, cmdArgs...)
	cmd.Dir = r.Root
	src := filepath.Join(r.Root, "src")
	cmd.Env = append(os.Environ(), "PYTHONPATH="+src)
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
	if err := bootstrap.CheckFFmpeg(); err != nil {
		return err
	}
	_, stderr, err := r.Run("ping")
	if err != nil {
		if strings.Contains(stderr, "No module named") {
			return fmt.Errorf("engine not installed — run: video-factory setup (%s)", stderr)
		}
		return fmt.Errorf("engine check failed: %s", stderr)
	}
	return nil
}
