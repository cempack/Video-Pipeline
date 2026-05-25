package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/cempack/video-pipeline/video_factory/internal/config"
	"github.com/cempack/video-pipeline/video_factory/internal/python"
	"github.com/spf13/cobra"
)

var (
	projectsDirFlag string
	forceFlag       bool
	resumeFlag      bool = true
	appPort         int  = 3847
	appNoOpen       bool
)

func Execute() error {
	root := &cobra.Command{
		Use:   "video-factory",
		Short: "Short-video pipeline — double-click or run to open the web app",
		Long:  "Run with no arguments to open the browser and configure everything in the UI.",
		RunE: func(cmd *cobra.Command, args []string) error {
			return RunApp(appPort, appNoOpen)
		},
	}
	root.Flags().IntVarP(&appPort, "port", "p", 3847, "Web UI port")
	root.Flags().BoolVar(&appNoOpen, "no-open", false, "Do not open a browser automatically")
	root.PersistentFlags().StringVar(&projectsDirFlag, "projects", "", "Projects directory (default: ./projects or config)")

	root.AddCommand(newInitCmd())
	root.AddCommand(newRunCmd())
	root.AddCommand(newStatusCmd())
	root.AddCommand(newConfigCmd())
	root.AddCommand(newServeCmd())
	root.AddCommand(newApproveCmd())
	root.AddCommand(newSelectImageCmd())
	root.AddCommand(newCandidatesCmd())
	root.AddCommand(newLibraryCmd())
	root.AddCommand(newDoctorCmd())
	root.AddCommand(newSetupCmd())

	return root.Execute()
}

func loadStore() (config.Store, error) {
	return config.Load()
}

func newRunner() (*python.Runner, error) {
	store, err := loadStore()
	if err != nil {
		return nil, err
	}
	if projectsDirFlag != "" {
		store.ProjectsDir = projectsDirFlag
	}
	return python.NewRunner(store)
}

func printErr(err error) {
	fmt.Fprintf(os.Stderr, "✗ %v\n", err)
}

func runEngine(r *python.Runner, args ...string) error {
	out, stderr, err := r.Run(args...)
	if out != "" {
		fmt.Print(strings.TrimSpace(out))
		if !strings.HasSuffix(strings.TrimSpace(out), "\n") {
			fmt.Println()
		}
	}
	if err != nil {
		if stderr != "" {
			printErr(fmt.Errorf("%s\n%s", err, stderr))
		} else {
			printErr(err)
		}
	}
	return err
}
