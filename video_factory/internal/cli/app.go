package cli

import (
	"fmt"
	"net"
	"os"

	"github.com/cempack/video-pipeline/video_factory/internal/bootstrap"
	"github.com/cempack/video-pipeline/video_factory/internal/web"
)

// RunApp installs dependencies if needed, starts the web UI, and opens the browser.
func RunApp(port int, noOpen bool) error {
	fmt.Println()
	fmt.Println("  Video Factory")
	fmt.Println("  Starting… (first launch may install Python dependencies)")
	fmt.Println()

	store, err := loadStore()
	if err != nil {
		return err
	}
	if projectsDirFlag != "" {
		store.ProjectsDir = projectsDirFlag
	}

	onStatus := func(msg string) { fmt.Fprintln(os.Stderr, " ", msg) }
	if _, err := bootstrap.Ensure(onStatus); err != nil {
		return fmt.Errorf("setup failed: %w", err)
	}

	r, err := newRunner()
	if err != nil {
		return err
	}
	if err := r.CheckPython(); err != nil {
		fmt.Fprintln(os.Stderr, "  Warning:", err)
	}

	addr := fmt.Sprintf("127.0.0.1:%d", port)
	url := "http://" + addr

	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("listen %s: %w", addr, err)
	}

	if !noOpen {
		go func() { _ = OpenBrowser(url) }()
	}

	fmt.Println("  Open in browser:", url)
	if noOpen {
		fmt.Println("  (--no-open: browser not launched automatically)")
	}
	fmt.Println("  Press Ctrl+C to stop")
	fmt.Println()

	return web.ServeOn(ln, r, store)
}
