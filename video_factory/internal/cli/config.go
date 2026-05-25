package cli

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"syscall"

	"github.com/cempack/video-pipeline/video_factory/internal/config"
	"github.com/cempack/video-pipeline/video_factory/internal/python"
	"github.com/spf13/cobra"
	"golang.org/x/term"
)

func newConfigCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "config",
		Short: "Manage API keys and settings",
	}
	cmd.AddCommand(newConfigSetCmd())
	cmd.AddCommand(newConfigGetCmd())
	cmd.AddCommand(newConfigPathCmd())
	cmd.AddCommand(newConfigWizardCmd())
	cmd.AddCommand(newConfigSetSecretCmd())
	return cmd
}

func newConfigSetCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "set <key> <value>",
		Short: "Set a configuration value",
		Long: `Keys: gemini-api-key, elevenlabs-api-key, elevenlabs-voice-id,
gemini-model, gemini-image-model, ffmpeg, ffprobe, image-backend, projects-dir, python, root`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := config.Load()
			if err != nil {
				return err
			}
			key, val := strings.ToLower(args[0]), args[1]
			switch key {
			case "gemini-api-key", "gemini":
				store.GeminiAPIKey = val
			case "elevenlabs-api-key", "elevenlabs":
				store.ElevenLabsAPIKey = val
			case "elevenlabs-voice-id", "voice-id":
				store.ElevenLabsVoiceID = val
			case "gemini-model":
				store.GeminiModel = val
			case "gemini-image-model":
				store.GeminiImageModel = val
			case "ffmpeg":
				store.FFmpegBin = val
			case "ffprobe":
				store.FFprobeBin = val
			case "image-backend":
				store.ImageBackend = val
			case "projects-dir", "projects":
				store.ProjectsDir = val
			case "python":
				store.PythonBin = val
			case "root", "video-factory-root":
				store.VideoFactoryRoot = val
			default:
				return fmt.Errorf("unknown key %q", key)
			}
			if err := config.Save(store); err != nil {
				return err
			}
			root := store.VideoFactoryRoot
			if root == "" {
				r, _ := python.NewRunner(store)
				if r != nil {
					root = r.Root
				}
			}
			if root != "" {
				_ = store.WriteDotEnv(root)
			}
			fmt.Printf("✓ Set %s\n", key)
			return nil
		},
	}
	return cmd
}

func newConfigGetCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "get [key]",
		Short: "Show configuration (secrets masked)",
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := config.Load()
			if err != nil {
				return err
			}
			if len(args) == 1 {
				switch strings.ToLower(args[0]) {
				case "gemini-api-key", "gemini":
					fmt.Println(config.MaskSecret(store.GeminiAPIKey))
				case "elevenlabs-api-key":
					fmt.Println(config.MaskSecret(store.ElevenLabsAPIKey))
				default:
					return fmt.Errorf("unknown key")
				}
				return nil
			}
			path, _ := config.ConfigPath()
			fmt.Println("Config:", path)
			fmt.Println("  gemini-api-key:     ", config.MaskSecret(store.GeminiAPIKey))
			fmt.Println("  elevenlabs-api-key: ", config.MaskSecret(store.ElevenLabsAPIKey))
			fmt.Println("  elevenlabs-voice-id:", orEmpty(store.ElevenLabsVoiceID))
			fmt.Println("  gemini-model:       ", store.GeminiModel)
			fmt.Println("  gemini-image-model: ", store.GeminiImageModel)
			fmt.Println("  image-backend:      ", store.ImageBackend)
			fmt.Println("  projects-dir:       ", store.ProjectsDir)
			fmt.Println("  python:             ", store.PythonBin)
			fmt.Println("  root:               ", orEmpty(store.VideoFactoryRoot))
			return nil
		},
	}
	return cmd
}

func newConfigPathCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "path",
		Short: "Print config file path",
		RunE: func(cmd *cobra.Command, args []string) error {
			p, err := config.ConfigPath()
			if err != nil {
				return err
			}
			fmt.Println(p)
			return nil
		},
	}
}

func newConfigWizardCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "wizard",
		Short: "Interactive setup for Gemini and ElevenLabs",
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := config.Load()
			if err != nil {
				return err
			}
			fmt.Println("Video Factory — setup wizard")
			fmt.Println("Get a Gemini key: https://aistudio.google.com/apikey")
			fmt.Print("Gemini API key (Enter to skip): ")
			if key := readLine(); key != "" {
				store.GeminiAPIKey = key
			}
			fmt.Print("Gemini model [gemini-2.0-flash]: ")
			if m := readLine(); m != "" {
				store.GeminiModel = m
			}
			fmt.Print("Gemini image model [gemini-2.0-flash-exp-image-generation]: ")
			if m := readLine(); m != "" {
				store.GeminiImageModel = m
			}
			fmt.Println("\nElevenLabs: https://elevenlabs.io")
			fmt.Print("ElevenLabs API key (Enter to skip): ")
			if key := readLine(); key != "" {
				store.ElevenLabsAPIKey = key
			}
			fmt.Print("ElevenLabs voice ID (Enter to skip): ")
			if v := readLine(); v != "" {
				store.ElevenLabsVoiceID = v
			}
			if err := config.Save(store); err != nil {
				return err
			}
			r, err := python.NewRunner(store)
			if err == nil {
				_ = store.WriteDotEnv(r.Root)
				fmt.Println("\n✓ Saved. .env updated at", r.Root)
			} else {
				fmt.Println("\n✓ Saved to", mustConfigPath())
			}
			return nil
		},
	}
}

func newConfigSetSecretCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "set-secret <key>",
		Short: "Set a secret without echoing (gemini-api-key, elevenlabs-api-key)",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			store, err := config.Load()
			if err != nil {
				return err
			}
			fmt.Printf("%s: ", args[0])
			b, err := term.ReadPassword(int(syscall.Stdin))
			fmt.Println()
			if err != nil {
				return err
			}
			val := string(b)
			switch strings.ToLower(args[0]) {
			case "gemini-api-key":
				store.GeminiAPIKey = val
			case "elevenlabs-api-key":
				store.ElevenLabsAPIKey = val
			default:
				return fmt.Errorf("use gemini-api-key or elevenlabs-api-key")
			}
			if err := config.Save(store); err != nil {
				return err
			}
			r, _ := python.NewRunner(store)
			if r != nil {
				_ = store.WriteDotEnv(r.Root)
			}
			fmt.Println("✓ Secret saved")
			return nil
		},
	}
}

func readLine() string {
	sc := bufio.NewScanner(os.Stdin)
	if sc.Scan() {
		return strings.TrimSpace(sc.Text())
	}
	return ""
}

func orEmpty(s string) string {
	if s == "" {
		return "(default)"
	}
	return s
}

func mustConfigPath() string {
	p, _ := config.ConfigPath()
	return p
}
