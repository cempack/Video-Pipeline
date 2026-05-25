package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newInitCmd() *cobra.Command {
	var topic, vertical string
	var duration int
	cmd := &cobra.Command{
		Use:   "init <project-id>",
		Short: "Create a new video project",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := []string{
				"init_project", args[0],
				"--topic", topic,
				"--vertical", vertical,
				"--duration", fmt.Sprintf("%d", duration),
			}
			a = append(a, r.ProjectsFlag()...)
			return runEngine(r, a...)
		},
	}
	cmd.Flags().StringVarP(&topic, "topic", "t", "", "Video topic (required)")
	cmd.Flags().StringVarP(&vertical, "vertical", "v", "technology", "technology|politics|economics|philosophy")
	cmd.Flags().IntVarP(&duration, "duration", "d", 45, "Target duration seconds")
	_ = cmd.MarkFlagRequired("topic")
	return cmd
}

func newStatusCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "status <project-id>",
		Short: "Show pipeline progress",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := append([]string{"status", args[0]}, r.ProjectsFlag()...)
			return runEngine(r, a...)
		},
	}
}

func newApproveCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "approve <stage> <project-id>",
		Short: "Approve a gated stage (e.g. script)",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := append([]string{"approve", args[0], args[1]}, r.ProjectsFlag()...)
			return runEngine(r, a...)
		},
	}
}

func newSelectImageCmd() *cobra.Command {
	var variant string
	cmd := &cobra.Command{
		Use:   "pick <project-id> <scene-id>",
		Short: "Select best image variant for a scene",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := append([]string{"select_image", args[0], args[1], variant}, r.ProjectsFlag()...)
			return runEngine(r, a...)
		},
	}
	cmd.Flags().StringVarP(&variant, "variant", "v", "v01", "Variant id e.g. v02")
	return cmd
}

func newCandidatesCmd() *cobra.Command {
	return &cobra.Command{
		Use:     "candidates <project-id>",
		Aliases: []string{"variants"},
		Short:   "List image variants per scene",
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := append([]string{"candidates", args[0]}, r.ProjectsFlag()...)
			return runEngine(r, a...)
		},
	}
}

func newLibraryCmd() *cobra.Command {
	var desc, style string
	var tags []string
	cmd := &cobra.Command{
		Use:   "library add <image-path>",
		Short: "Register image in reuse library",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			r, err := newRunner()
			if err != nil {
				return err
			}
			a := []string{"library_add", args[0], "--desc", desc}
			if style != "" {
				a = append(a, "--style", style)
			}
			for _, t := range tags {
				a = append(a, "--tag", t)
			}
			return runEngine(r, a...)
		},
	}
	cmd.Flags().StringVarP(&desc, "desc", "d", "", "Description (required)")
	cmd.Flags().StringVar(&style, "style", "", "Visual style tag")
	cmd.Flags().StringSliceVar(&tags, "tag", nil, "Tags")
	_ = cmd.MarkFlagRequired("desc")
	return cmd
}

func newDoctorCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "doctor",
		Short: "Check Python, FFmpeg, and API config",
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := loadStore()
			if err != nil {
				return err
			}
			fmt.Println("Video Factory doctor")
			if store.GeminiAPIKey != "" {
				fmt.Println("  ✓ Gemini API key configured")
			} else {
				fmt.Println("  ✗ Gemini API key missing — run: video-factory config wizard")
			}
			if store.ElevenLabsAPIKey != "" {
				fmt.Println("  ✓ ElevenLabs API key configured")
			} else {
				fmt.Println("  ○ ElevenLabs optional (needed for narration)")
			}
			r, err := newRunner()
			if err != nil {
				fmt.Println("  ✗", err)
				return err
			}
			if err := r.CheckPython(); err != nil {
				fmt.Println("  ✗", err)
				return err
			}
			fmt.Println("  ✓ Python engine OK")
			fmt.Println("  root:", r.Root)
			return nil
		},
	}
}
