"""렌더 QA 시트 — 컷 중간 프레임 시트 + 1초 간격 시트 (라벨: 컷번호/시각).
사용: python3 qa_strip.py preview_540.mp4 [태그]  → <태그>_mid.jpg · <태그>_1s.jpg
1초 시트로 "자막 문구 ↔ 그 순간 실제 동작"을 대조한다 (문구는 맞는데 동작이 한 박자 늦은 어긋남이 잦다).
"""
import glob, math, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
for _p in (os.path.dirname(S), os.path.expanduser("~/.claude/skills/reel/scripts")):
  if os.path.exists(os.path.join(_p, "reel_assets.py")):
    sys.path.insert(1, _p); break
from reel_assets import font_path
from timeline import CUTS, CT, FPS, TOTAL_SEC
F = ImageFont.truetype(font_path("pretendard"), 20)
vid = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "qa"
PW = 162  # 패널 폭 (9:16 → 162x288)

def grab(t, path):
  subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{t:.3f}","-i",vid,"-frames:v","1","-vf",f"scale={PW}:-2",path],check=True)

def sheet(items, cols, out):  # items = [(label, t)]
  with tempfile.TemporaryDirectory() as td:
    ims = []
    for i, (lab, t) in enumerate(items):
      p = f"{td}/{i:03d}.png"; grab(t, p)
      im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
      d.rectangle([0,0,PW,24],fill=(0,0,0)); d.text((3,2),lab,font=F,fill=(255,230,0)); ims.append(im)
    w, h = ims[0].size; rows = math.ceil(len(ims)/cols)
    o = Image.new("RGB",(cols*(w+3),rows*(h+3)),(20,20,20))
    for i, im in enumerate(ims): o.paste(im,((i%cols)*(w+3),(i//cols)*(h+3)))
    o.save(out, quality=88); print(out)

mid = [(f"c{i+1} {(s+e)/2:.1f}s", (s+e)/2) for i,(s,e) in enumerate(CT)]
sheet(mid, 14, f"{S}/{tag}_mid.jpg")
sec = [(f"{t}s", t+0.5) for t in range(int(TOTAL_SEC))]
sheet(sec, 15, f"{S}/{tag}_1s.jpg")
