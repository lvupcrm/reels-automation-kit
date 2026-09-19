"""목업 스트립 — 렌더 전에 크롭·자막 위치를 한 장으로 검수한다 (오버레이 ov/ 가 먼저 있어야 한다).
사용: python3 mock_strip.py [초 초 ...]   (기본: 구간별 대표 시각 12개)
→ mock/mock_strip.jpg — 크롭 중심이 사람을 잡았는지, 자막이 얼굴을 가리지 않는지 본다.
"""
import os
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_master import src_chain  # noqa: E402
from timeline import FPS, SRC, TOTAL_SEC, src_time  # noqa: E402

S = os.path.dirname(os.path.abspath(__file__))
os.makedirs(f"{S}/mock/base", exist_ok=True)
TS = [float(a) for a in sys.argv[1:]] or [0.9, 2.6, 4.5, 6.5, 8.4, 11.5, 15.5, 19.5, 21.2, 23.5, 27.0, 29.2]
panels = []
for t in TS:
  t = min(t, TOTAL_SEC - 0.05)
  c, st = src_time(t)
  n = round(t * FPS)
  bp = f"{S}/mock/base/{n:04d}.png"
  if c.get("freeze"):
    Image.open(c["freeze"]).convert("RGB").resize((1080, 1920)).save(bp)
  else:
    vf = ",".join(src_chain(c) + ["scale=1080:1920:flags=lanczos,eq=contrast=1.06:saturation=1.10"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{st:.3f}", "-i", SRC[c["src"]], "-frames:v", "1", "-vf", vf, bp],
                   check=True)
  im = Image.open(bp).convert("RGBA")
  ov = f"{S}/ov/{n:04d}.png"
  if os.path.exists(ov):
    im.alpha_composite(Image.open(ov))
  panels.append(im.convert("RGB").resize((405, 720), Image.LANCZOS))
out = Image.new("RGB", (405 * len(panels) + 6 * (len(panels) - 1), 720), (30, 30, 30))
for i, p in enumerate(panels):
  out.paste(p, (i * 411, 0))
out.save(f"{S}/mock/mock_strip.jpg", quality=90)
print("mock →", f"{S}/mock/mock_strip.jpg", TS)
