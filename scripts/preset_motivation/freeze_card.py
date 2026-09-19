"""프리즈 오프너 — 얼린 스틸 추출 (1080x1920 PNG).
직전 컷과 이음매가 보이지 않도록 그 컷과 '같은 필터 체인'을 돌려 마지막 프레임을 꺼낸다.
산출한 스틸은 freeze_seg.py 가 [뭉갠 배경]과 [누끼 피사체]로 분리한다.
사용: python3 freeze_card.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import FPS, FREEZE, FREEZE_STILL, SRC  # noqa: E402
from build_master import src_chain  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "freeze", "_seq")

def extract():
  if not FREEZE:
    sys.exit("timeline.FREEZE 가 비어 있다 — 프리즈 오프너를 쓰려면 먼저 채운다")
  c = FREEZE["src_cut"]
  os.makedirs(os.path.dirname(FREEZE_STILL), exist_ok=True)
  os.makedirs(TMP, exist_ok=True)
  for f in os.listdir(TMP):
    os.remove(os.path.join(TMP, f))
  vf = ",".join(src_chain(c) + [f"scale=1080:1920:flags=lanczos,fps={FPS}"])
  subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{c['start']:.3f}",
                  "-t", f"{(c['n'] + 2) / FPS:.3f}", "-i", SRC[c["src"]],
                  "-vf", vf, "-frames:v", str(c["n"]), os.path.join(TMP, "%03d.png")], check=True)
  seq = sorted(os.listdir(TMP))
  assert len(seq) == c["n"], f"프레임 {len(seq)}장 != {c['n']}장"
  os.replace(os.path.join(TMP, seq[-1]), FREEZE_STILL)
  for f in os.listdir(TMP):
    os.remove(os.path.join(TMP, f))
  os.rmdir(TMP)
  print(f"프리즈 스틸 ← {c['src']} @{c['start']:.3f}s +{c['n']}f 의 마지막 프레임 → {FREEZE_STILL}")

if __name__ == "__main__":
  extract()
