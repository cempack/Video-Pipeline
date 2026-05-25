package bootstrap

import (
	"archive/tar"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
)

// pythonBuildStandalone release (install_only archives).
const pythonReleaseTag = "20241016"

func pythonArchiveName() (string, error) {
	switch runtime.GOOS {
	case "linux":
		switch runtime.GOARCH {
		case "amd64":
			return "cpython-3.12.7+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz", nil
		case "arm64":
			return "cpython-3.12.7+20241016-aarch64-unknown-linux-gnu-install_only.tar.gz", nil
		}
	case "darwin":
		switch runtime.GOARCH {
		case "arm64":
			return "cpython-3.12.7+20241016-aarch64-apple-darwin-install_only.tar.gz", nil
		case "amd64":
			return "cpython-3.12.7+20241016-x86_64-apple-darwin-install_only.tar.gz", nil
		}
	case "windows":
		if runtime.GOARCH == "amd64" {
			return "cpython-3.12.7+20241016-x86_64-pc-windows-msvc-install_only.tar.gz", nil
		}
	}
	return "", fmt.Errorf("unsupported platform %s/%s", runtime.GOOS, runtime.GOARCH)
}

func downloadEmbeddedPython(destDir string, onStatus func(string)) error {
	name, err := pythonArchiveName()
	if err != nil {
		return err
	}
	url := fmt.Sprintf("https://github.com/indygreg/python-build-standalone/releases/download/%s/%s", pythonReleaseTag, name)
	if onStatus != nil {
		onStatus("Downloading Python runtime (" + runtime.GOOS + "/" + runtime.GOARCH + ")…")
	}
	client := &http.Client{Timeout: 0} // large download; no short timeout
	resp, err := client.Get(url)      //nolint:noctx
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("python download HTTP %d", resp.StatusCode)
	}
	tmp, err := os.CreateTemp("", "vf-python-*.tar.gz")
	if err != nil {
		return err
	}
	tmpPath := tmp.Name()
	defer os.Remove(tmpPath)
	if _, err := io.Copy(tmp, resp.Body); err != nil {
		return err
	}
	tmp.Close()
	return extractInstallOnlyTarGz(tmpPath, destDir)
}

func extractInstallOnlyTarGz(archivePath, destDir string) error {
	f, err := os.Open(archivePath)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		target := filepath.Join(destDir, hdr.Name)
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, os.FileMode(hdr.Mode))
			if err != nil {
				return err
			}
			if _, err := io.Copy(out, tr); err != nil {
				out.Close()
				return err
			}
			out.Close()
		}
	}
	return nil
}

func embeddedPythonBin(pythonRoot string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(pythonRoot, "python", "python.exe")
	}
	return filepath.Join(pythonRoot, "python", "bin", "python3")
}

