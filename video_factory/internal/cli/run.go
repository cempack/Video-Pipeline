package cli

import (
	"fmt"

	"github.com/cempack/video-pipeline/video_factory/internal/python"
	"github.com/cempack/video-pipeline/video_factory/internal/web"
	"github.com/spf13/cobra"
)

var stages = []string{
	"research", "script", "scenes", "prompts", "character",
	"images", "narration", "subtitles", "timeline", "render", "qa",
}

func newRunCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "run",
		Short: "Run pipeline stages",
	}
	cmd.AddCommand(newRunAllCmd())
	for _, s := range stages {
		stage := s
		cmd.AddCommand(&cobra.Command{
			Use:   stage,
			Short: fmt.Sprintf("Run %s stage", stage),
			Args:  cobra.ExactArgs(1),
			RunE: func(cmd *cobra.Command, args []string) error {
				return runStage(stage, args[0])
			},
		})
	}
	return cmd
}

func newRunAllCmd() *cobra.Command {
	var skipResearch, noResume bool
	cmd := &cobra.Command{
		Use:   "all <project-id>",
		Short: "Run full pipeline",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := []string{"run_stage", "all", args[0]}
			a = append(a, r.ProjectsFlag()...)
			if forceFlag {
				a = append(a, "--force")
			}
			if skipResearch {
				a = append(a, "--skip-research")
			}
			if noResume || !resumeFlag {
				a = append(a, "--no-resume")
			}
			fmt.Printf("▶ Running pipeline for %s\n", args[0])
			return runEngine(r, a...)
		},
	}
	cmd.Flags().BoolVar(&forceFlag, "force", false, "Re-run completed stages")
	cmd.Flags().BoolVar(&resumeFlag, "resume", true, "Skip completed stages")
	cmd.Flags().BoolVar(&skipResearch, "skip-research", false, "Skip research stage")
	cmd.Flags().BoolVar(&noResume, "no-resume", false, "Run every stage")
	return cmd
}

func runStage(stage, projectID string) error {
	r, err := newRunner()
	if err != nil {
		return err
	}
	a := []string{"run_stage", stage, projectID}
	a = append(a, r.ProjectsFlag()...)
	if forceFlag {
		a = append(a, "--force")
	}
	fmt.Printf("▶ %s\n", stage)
	return runEngine(r, a...)
}

func newServeCmd() *cobra.Command {
	var port int
	var noOpen bool
	cmd := &cobra.Command{
		Use:     "serve",
		Aliases: []string{"web", "ui"},
		Short:   "Start web interface",
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := loadStore()
			if err != nil {
				return err
			}
			if projectsDirFlag != "" {
				store.ProjectsDir = projectsDirFlag
			}
			r, err := python.NewRunner(store)
			if err != nil {
				return err
			}
			addr := fmt.Sprintf("127.0.0.1:%d", port)
			fmt.Println()
			fmt.Println("  Video Factory")
			fmt.Println("  ─────────────────────────────")
			fmt.Printf("  Web UI   http://%s\n", addr)
			fmt.Println("  Press Ctrl+C to stop")
			fmt.Println()
			return web.Serve(addr, r, store)
		},
	}
	cmd.Flags().IntVarP(&port, "port", "p", 3847, "HTTP port")
	cmd.Flags().BoolVar(&noOpen, "no-open", false, "Do not print browser hint")
	return cmd
}

