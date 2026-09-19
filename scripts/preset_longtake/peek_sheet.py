"""프레임 시트 — 클립별로 일정 간격 프레임을 뽑아 시간 라벨을 붙인 한 장 (컷 고르기·장면 전환점 찾기).

사용:
  python3 peek_sheet.py <영상>[:시작:길이:간격:열]  [...]      # 예) input/a.mov:0:20:1:10
  python3 peek_sheet.py --grid <영상> <초>                      # 크롭 실측용 960px + 10% 그리드 한 장
결과: peek/<파일명>_<시작>.jpg

⚠️ 클립 식별은 파일별 시트로만 한다 — 여러 클립을 한 이미지에 쌓아 "몇 번째 행 = 어느 클립"을 세면 잘못 센다.
⚠️ 클로즈업 크롭 (cx,cy,zoom)은 192px 썸네일로 눈대중하지 말고 --grid 프레임으로 얼굴(눈) 좌표를 잰다.
   머리 폭이 9:16 창 폭보다 크면 zoom 1.0 — 어떤 중심을 잡아도 머리 일부만 남는다.
"""
import glob
import math
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

S = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.dirname(S), os.path.expanduser("~/.claude/skills/reel/scripts")):
  if os.path.exists(os.path.join(_p, "reel_assets.py")):
    sys.path.insert(0, _p); break
from reel_assets import font_path  # noqa: E402

F = ImageFont.truetype(font_path("pretendard"), 22)
os.makedirs(f"{S}/peek", exist_ok=True)


def duration(path):
  r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                     capture_output=True, text=True)
  return float(r.stdout.strip() or 0)


def sheet(path, st=0.0, du=None, iv=1.0, cols=10):
  du = du or max(0.5, duration(path) - st)
  base = os.path.splitext(os.path.basename(path))[0]
  with tempfile.TemporaryDirectory() as td:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(st), "-t", str(du), "-i", path,
                    "-vf", f"fps=1/{iv},scale=192:-2", "-start_number", "0", f"{td}/%03d.png"], check=True)
    ims = [Image.open(p).convert("RGB") for p in sorted(glob.glob(f"{td}/*.png"))]
  w, h = ims[0].size
  rows = math.ceil(len(ims) / cols)
  out = Image.new("RGB", (cols * (w + 3), rows * (h + 3)), (0, 0, 0))
  for i, im in enumerate(ims):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 70, 26], fill=(0, 0, 0)); d.text((4, 2), f"{st + i * iv:.1f}", font=F, fill=(255, 230, 0))
    out.paste(im, ((i % cols) * (w + 3), (i // cols) * (h + 3)))
  dst = f"{S}/peek/{base}_{st:g}.jpg"
  out.save(dst, quality=88)
  print(dst, len(ims), "장")


def grid(path, t):
  base = os.path.splitext(os.path.basename(path))[0]
  dst = f"{S}/peek/{base}_grid_{t:g}.jpg"
  subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", path, "-frames:v", "1",
                  "-vf", "scale=960:-2,drawgrid=w=iw/10:h=ih/10:t=1:c=yellow@0.6", dst], check=True)
  print(dst, "— 칸 하나 = 0.1 (cx·cy를 이 눈금으로 읽는다)")


if __name__ == "__main__":
  a = sys.argv[1:]
  if not a:
    sys.exit(__doc__)
  if a[0] == "--grid":
    grid(a[1], float(a[2]))
  else:
    for spec in a:
      p, *rest = spec.split(":")
      nums = [float(x) for x in rest]
      sheet(p, *(nums[:3]), *([int(nums[3])] if len(nums) > 3 else []))
