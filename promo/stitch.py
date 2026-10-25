# -*- coding: utf-8 -*-
"""宣传片拼接：8 段统一 1280x720@30fps h264 + aac 44.1k，输出 promo/final。

用法: python stitch.py [输出文件名]
缺省输入按 01..08 顺序；字卡(08)无音轨自动补静音。
"""
import json
import subprocess
import sys
from pathlib import Path

FF = None
def ffmpeg():
    global FF
    if FF is None:
        import imageio_ffmpeg
        FF = imageio_ffmpeg.get_ffmpeg_exe()
    return FF

ROOT = Path(__file__).parent
VIDEO = ROOT / "video"
OUT = ROOT / "final"
OUT.mkdir(exist_ok=True)

CLIPS = [
    "成片01·血月之城.mp4",
    "fenjing02_00001_.mp4",
    "fenjing03_00001_.mp4",
    "fenjing04_00001_.mp4",
    "fenjing05_00001_.mp4",
    "fenjing06_00001_.mp4",
    "fenjing07_00001_.mp4",
    "成片08·片尾字卡.mp4",
]

VF = ("scale=1280:720:force_original_aspect_ratio=increase,"
      "crop=1280:720,fps=30,setsar=1,format=yuv420p")


def normalize(src: Path, dst: Path):
    """单段标准化：720p30 + 44.1k aac 立体声（无音轨则补静音）。"""
    probe = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(src)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    has_audio = "Audio:" in probe.stderr
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    if has_audio:
        cmd += ["-map", "0:v:0", "-map", "0:a:0",
                "-af", "aresample=44100", "-ac", "2"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += ["-vf", VF, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-video_track_timescale", "15360", str(dst)]
    subprocess.run(cmd, check=True)
    print(f"  ok: {dst.name}")


def main():
    out_name = sys.argv[1] if len(sys.argv) > 1 else " ApocalypseZombies_宣传片_1080p.mp4"
    final = OUT / out_name
    parts = []
    tmp = OUT / "_parts"
    tmp.mkdir(exist_ok=True)
    for i, name in enumerate(CLIPS, 1):
        src = VIDEO / name
        if not src.exists():
            print(f"[缺] {name} —— 跳过前先补齐该镜", file=sys.stderr)
            sys.exit(1)
        dst = tmp / f"part{i}.mp4"
        normalize(src, dst)
        parts.append(dst)

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(final)], check=True)
    print(f"[done] {final}")
    # 时长核对
    probe = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(final)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    for ln in probe.stderr.splitlines():
        if "Duration" in ln:
            print(ln.strip())


if __name__ == "__main__":
    main()
