"""Rich-powered CLI presentation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from video_factory import __version__
from video_factory.models.schemas import ApprovalStatus, StageName

THEME = Theme(
    {
        "info": "cyan",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "accent": "bold magenta",
        "dim": "dim white",
        "stage": "bold blue",
    }
)

_console: VFConsole | None = None


class VFConsole:
    def __init__(self) -> None:
        self.console = Console(theme=THEME, highlight=False)

    def banner(self) -> None:
        title = Text("Video Factory", style="accent")
        subtitle = Text(f"v{__version__}  ·  short-form pipeline", style="dim")
        self.console.print(
            Panel(
                Text.assemble(title, "\n", subtitle),
                border_style="accent",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    def rule(self, label: str) -> None:
        self.console.print(Rule(label, style="dim"))

    def success(self, msg: str) -> None:
        self.console.print(f"[ok]✓[/ok] {msg}")

    def warn(self, msg: str) -> None:
        self.console.print(f"[warn]![/warn] {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[err]✗[/err] {msg}")

    def info(self, msg: str) -> None:
        self.console.print(f"[info]→[/info] {msg}")

    def project_header(self, project_id: str, topic: str, vertical: str) -> None:
        self.console.print(
            Panel(
                f"[bold]{project_id}[/bold]\n"
                f"[dim]Topic:[/dim] {topic}\n"
                f"[dim]Vertical:[/dim] {vertical}",
                title="Project",
                border_style="info",
                box=box.ROUNDED,
            )
        )

    def stage_start(self, stage: StageName) -> None:
        self.console.print(f"\n[stage]▶ {stage.value}[/stage]")

    def stage_done(self, stage: StageName, detail: str = "") -> None:
        suffix = f"  [dim]{detail}[/dim]" if detail else ""
        self.success(f"{stage.value}{suffix}")

    @contextmanager
    def progress_task(self, description: str, total: int) -> Iterator[Progress]:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        with progress:
            task = progress.add_task(description, total=total)
            progress._vf_task_id = task  # type: ignore[attr-defined]
            yield progress

    def status_table(
        self,
        project_id: str,
        rows: list[tuple[str, str, str]],
        *,
        refs_ok: bool = False,
    ) -> None:
        table = Table(
            title=f"Pipeline · {project_id}",
            box=box.SIMPLE_HEAVY,
            header_style="bold",
            show_lines=False,
            pad_edge=False,
        )
        table.add_column("Stage", style="stage", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Detail", overflow="fold")

        status_style = {
            "complete": "ok",
            "failed": "err",
            "pending": "dim",
            "awaiting": "warn",
        }
        for stage, status, detail in rows:
            style = status_style.get(status, "dim")
            label = status
            if status == "complete":
                label = "✓ complete"
            elif status == "failed":
                label = "✗ failed"
            elif status == "awaiting":
                label = "⏳ awaiting approval"
            table.add_row(stage, f"[{style}]{label}[/]", detail or "—")

        self.console.print(table)
        if refs_ok:
            self.success("Style + character references detected (Whisk coherence enabled)")
        else:
            self.warn("Add inputs/style_reference.png and inputs/character_reference.png for best coherence")

    def candidates_table(self, scenes: list[dict]) -> None:
        table = Table(title="Image variants", box=box.ROUNDED, header_style="bold magenta")
        table.add_column("Scene", style="cyan", no_wrap=True)
        table.add_column("Variants")
        table.add_column("Selected", style="ok")
        for scene in scenes:
            variants = ", ".join(v["variant_id"] for v in scene.get("variants", []))
            sel = scene.get("selected_variant_id") or "—"
            table.add_row(scene["scene_id"], variants, sel)
        self.console.print(table)

    def qa_summary(self, passed: bool, checks: list, warnings: list) -> None:
        color = "ok" if passed else "err"
        icon = "✓" if passed else "✗"
        self.console.print(
            Panel(
                f"[{color}]{icon} {'PASSED' if passed else 'FAILED'}[/{color}]\n"
                + (f"[warn]{len(warnings)} warning(s)[/warn]" if warnings else "[dim]No warnings[/dim]"),
                title="QA Report",
                border_style=color,
            )
        )


def get_console() -> VFConsole:
    global _console
    if _console is None:
        _console = VFConsole()
    return _console
