"""토킹헤드 점프컷 플래너 — ffmpeg silencedetect로 무음 구간을 찾아 keep 세그먼트를 산출.

사용:
  python jumpcut_plan.py input.mp4 [--min-silence 0.6] [--noise -35] [--pad 0.12]
  - min-silence: 이 길이(초) 이상 무음이면 컷 후보
  - noise: 무음 판정 임계(dB) — 현장 소음 많으면 -30 정도로 완화
  - pad: keep 구간 앞뒤 여유(초) — 말 앞머리 잘림 방지

산출:
  jumpcut_segments.json  — [{"s":…,"e":…}, …] keep 구간 (수동 제외 편집 후 재사용 가능)
  stdout — 전후 길이 비교 + 오디오 프리뷰용 aselect/atrim 스니펫

이후 단계(정본 순서): keep 구간으로 오디오만 먼저 렌더 → whisper 재전사 → 자막.
영상 마스터는 단일 filter_complex에서 trim·concat 1회 인코딩 (SKILL.md 공통 규약).
"""
import argparse
import json
import re
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("input")
ap.add_argument("--min-silence", type=float, default=0.6)
ap.add_argument("--noise", type=float, default=-35)
ap.add_argument("--pad", type=float, default=0.12)
args = ap.parse_args()

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", args.input],
    capture_output=True, text=True,
)
duration = float(probe.stdout.strip())

det = subprocess.run(
    ["ffmpeg", "-hide_banner", "-i", args.input, "-vn",
     "-af", f"silencedetect=noise={args.noise}dB:d={args.min_silence}", "-f", "null", "-"],
    capture_output=True, text=True,
)
starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", det.stderr)]
ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", det.stderr)]

silences = list(zip(starts, ends))
if len(starts) > len(ends):  # 파일 끝까지 무음
    silences.append((starts[-1], duration))

segments = []
cursor = 0.0
for ss, se in silences:
    keep_end = min(ss + args.pad, duration)
    if keep_end - cursor > 0.05:
        segments.append({"s": round(cursor, 3), "e": round(keep_end, 3)})
    cursor = max(se - args.pad, cursor)
if duration - cursor > 0.05:
    segments.append({"s": round(cursor, 3), "e": round(duration, 3)})

kept = sum(s["e"] - s["s"] for s in segments)
with open("jumpcut_segments.json", "w") as f:
    json.dump(segments, f, indent=1)

print(f"원본 {duration:.1f}s → 점프컷 {kept:.1f}s ({len(segments)}개 세그먼트, 무음 {duration-kept:.1f}s 제거)")
for i, s in enumerate(segments):
    print(f"  [{i}] {s['s']:6.2f} - {s['e']:6.2f}  ({s['e']-s['s']:.2f}s)")

if not segments:
    sys.exit("세그먼트 없음 — noise 임계를 확인하세요")

# 오디오 프리뷰(자막 타임라인 기준이 될 컷 적용 오디오)
atrims = "".join(
    f"[0:a]atrim={s['s']}:{s['e']},asetpts=PTS-STARTPTS[a{i}];" for i, s in enumerate(segments)
)
concat_in = "".join(f"[a{i}]" for i in range(len(segments)))
print("\n# 컷 적용 오디오 렌더 (whisper 자막용):")
print(f'ffmpeg -y -i "{args.input}" -filter_complex "{atrims}{concat_in}concat=n={len(segments)}:v=0:a=1[out]" '
      f'-map "[out]" -ac 1 -ar 16000 talk_cut.wav')
