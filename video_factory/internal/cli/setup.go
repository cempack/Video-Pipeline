package cli

import (
	"fmt"

	"github.com/cempack/video-pipeline/video_factory/internal/bootstrap"
	"github.com/spf13/cobra"
)

func newSetupCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "setup",
		Short: "Install Python engine and dependencies (macOS, Windows, Linux)",
		Long: `Downloads or uses system Python 3.11+, creates a managed virtualenv,
and pip-installs the embedded pipeline. Run automatically on first use; use this to retry.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			env, err := bootstrap.Ensure(func(msg string) { fmt.Println(msg) })
			if err != nil {
				return err
			}
			fmt.Println("✓ Engine:", env.Root)
			fmt.Println("✓ Python:", env.PythonBin)
			fmt.Println("✓ Projects:", env.ProjectsDir)
			if err := bootstrap.CheckFFmpeg(); err != nil {
				fmt.Println("!", err.Error())
			} else {
				fmt.Println("✓ FFmpeg found")
			}
			return nil
		},
	}
}
