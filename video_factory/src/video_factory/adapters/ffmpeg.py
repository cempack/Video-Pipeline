"""FFmpeg/ffprobe command builder and runner."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from video_factory.config import AppSettings
from video_factory.models.schemas import RenderTimeline, TimelineScene

logger = logging.getLogger("video_factory")


class FFmpegAdapter:
    def __init__(self, settings: AppSettings) -> None:
        self.ffmpeg = settings.ffmpeg_bin
        self.ffprobe = settings.ffprobe_bin

    def run(self, args: list[str], *, cwd: Path | None = None) -> None:
        cmd = [self.ffmpeg, *args]
        logger.debug("ffmpeg %s", " ".join(args))
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed ({proc.returncode}): {proc.stderr[-2000:] if proc.stderr else proc.stdout}"
            )

    def probe_duration(self, path: Path) -> float:
        cmd = [
            self.ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        return float(data["format"]["duration"])

    def probe_video_info(self, path: Path) -> dict:
        cmd = [
            self.ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)

    def normalize_image(self, src: Path, dst: Path, width: int, height: int) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        self.run(["-y", "-loop", "1", "-i", str(src), "-vf", vf, "-frames:v", "1", str(dst)])

    def render_scene_clip(
        self,
        image: Path,
        audio: Path | None,
        duration: float,
        output: Path,
        width: int,
        height: int,
        motion: TimelineScene,
        fps: int = 30,
    ) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        frames = max(int(duration * fps), 1)
        zoom = motion.motion.zoom if motion.motion.type == "ken_burns" else 1.0
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(zoom+0.001,{zoom})':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},"
            f"fps={fps},format=yuv420p"
        )
        args = ["-y", "-loop", "1", "-i", str(image), "-vf", vf, "-t", str(duration)]
        if audio and audio.is_file():
            args.extend(["-i", str(audio), "-c:a", "aac", "-shortest"])
        else:
            args.extend(["-f", "lavfi", "-i", "anullsrc", "-t", str(duration), "-shortest"])
        args.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)])
        self.run(args)

    def concat_clips(self, clip_paths: list[Path], output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        list_file = output.parent / "concat_list.txt"
        lines = [f"file '{p.resolve()}'" for p in clip_paths]
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.run(
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
        )

    def mux_audio(self, video: Path, audio: Path, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.run(
            [
                "-y",
                "-i",
                str(video),
                "-i",
                str(audio),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                str(output),
            ]
        )

    def burn_subtitles(self, video: Path, srt: Path, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        srt_esc = str(srt.resolve()).replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{srt_esc}'"
        self.run(
            [
                "-y",
                "-i",
                str(video),
                "-vf",
                vf,
                "-c:a",
                "copy",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )

    def loudness_normalize(self, audio: Path, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.run(
            [
                "-y",
                "-i",
                str(audio),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                str(output),
            ]
        )

    def render_from_timeline(
        self,
        timeline: RenderTimeline,
        project_dir: Path,
        *,
        srt_path: Path | None = None,
        clean_output: Path,
        subtitled_output: Path | None = None,
    ) -> Path:
        work = project_dir / "work" / "clips"
        work.mkdir(parents=True, exist_ok=True)
        clips: list[Path] = []
        for scene in timeline.scenes:
            clip_out = work / f"{scene.scene_id}.mp4"
            img = project_dir / scene.image_path
            audio = project_dir / scene.audio_path if scene.audio_path else None
            self.render_scene_clip(
                img,
                audio,
                scene.duration_sec,
                clip_out,
                timeline.width,
                timeline.height,
                scene,
                timeline.fps,
            )
            clips.append(clip_out)

        concat_out = work / "concat.mp4"
        self.concat_clips(clips, concat_out)

        voiceover = project_dir / "work/audio/voiceover.mp3"
        if voiceover.is_file():
            muxed = work / "muxed.mp4"
            self.mux_audio(concat_out, voiceover, muxed)
            final_video = muxed
        else:
            final_video = concat_out

        clean_output.parent.mkdir(parents=True, exist_ok=True)
        self.run(["-y", "-i", str(final_video), "-c", "copy", str(clean_output)])

        if srt_path and srt_path.is_file() and subtitled_output:
            self.burn_subtitles(clean_output, srt_path, subtitled_output)
            return subtitled_output
        return clean_output
