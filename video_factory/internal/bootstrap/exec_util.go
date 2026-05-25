package bootstrap

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func execLookPath(file string) string {
	p, _ := exec.LookPath(file)
	return p
}

func runOutput(name string, args ...string) ([]byte, error) {
	if strings.Contains(name, " ") {
		parts := strings.Fields(name)
		cmd := exec.Command(parts[0], append(parts[1:], args...)...)
		var buf bytes.Buffer
		cmd.Stdout = &buf
		cmd.Stderr = &buf
		err := cmd.Run()
		return buf.Bytes(), err
	}
	cmd := exec.Command(name, args...)
	var buf bytes.Buffer
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	err := cmd.Run()
	return buf.Bytes(), err
}

func runCmd(dir, name string, args []string, env []string) error {
	var cmd *exec.Cmd
	if strings.Contains(name, " ") {
		parts := strings.Fields(name)
		cmd = exec.Command(parts[0], append(parts[1:], args...)...)
	} else {
		cmd = exec.Command(name, args...)
	}
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), env...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func copyEmbedToDir(srcFS interface {
	ReadDir(name string) ([]os.DirEntry, error)
	ReadFile(name string) ([]byte, error)
}, dest string) error {
	// Walk via ReadDir recursive helper
	return copyEmbedRecursive(srcFS, ".", dest)
}

func copyEmbedRecursive(fs interface {
	ReadDir(name string) ([]os.DirEntry, error)
	ReadFile(name string) ([]byte, error)
}, srcRoot, destRoot string) error {
	entries, err := fs.ReadDir(srcRoot)
	if err != nil {
		return err
	}
	for _, e := range entries {
		srcPath := filepath.Join(srcRoot, e.Name())
		dstPath := filepath.Join(destRoot, e.Name())
		if e.IsDir() {
			if err := os.MkdirAll(dstPath, 0o755); err != nil {
				return err
			}
			if err := copyEmbedRecursive(fs, srcPath, dstPath); err != nil {
				return err
			}
		} else {
			data, err := fs.ReadFile(srcPath)
			if err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Dir(dstPath), 0o755); err != nil {
				return err
			}
			if err := os.WriteFile(dstPath, data, 0o644); err != nil {
				return err
			}
		}
	}
	return nil
}
