"""화면 전용 설명편 도구 — 얼굴 없이 화면 카드만으로 가는 릴스 (references/preset-screen-only.md).

  python screen_cards.py capture <URL> page.png [--viewport 640x940]
      웹페이지를 2배 해상도로 캡처한다(Playwright). 뷰포트를 카드 비율에 맞춰 '작게' 잡아야 글자가 폰에서 읽힌다.
      실제 창을 찍으면 글씨가 너무 작다 — 이 방식이 릴스엔 오히려 낫다.
  python screen_cards.py browser page.png <표시할 URL> card.png [--insecure]
      캡처 위에 신호등·주소창·자물쇠를 그린 브라우저 카드(980x1010). 주소는 실제 URL 그대로 — 증거성이 유지된다.
  python screen_cards.py terminal lines.txt card.png [--title terminal]
      실제 명령 출력을 읽히는 크기(42px/행간 62)로 렌더한 터미널 카드. lines.txt 한 줄 = "텍스트|색",
      색: cmd(흰·굵게) ok(초록) dim(회색) acc(민트). 텍스트 안 **강조**는 민트+밑줄.
  python screen_cards.py render timing.json out.mp4 [--audio narration.wav] [--ass subs.ass]
      [--bg bg.png | --color 0E1116] [--title title.png]
      PNG를 프레임 단위로 직접 합성해 ffmpeg에 흘려보낸다 — 컷별 중간 인코딩도, filter_complex 셸 함정도 없다.
      timing.json = {"total": 초, "cuts": [{"start":0, "end":3.1, "card":"card1.png", "overlay":"선택.png"}, ...]}
      카드는 0.26초에 걸쳐 26px 아래에서 떠오른다. bg가 프레임보다 크면 전체 길이 동안 천천히 팬한다.

⚠️ 내 실제 프로젝트·계정 화면을 찍지 않는다 — 키·고객 정보가 프레임에 들어간다. 더미 데이터로 만든 데모 앱/계정을 찍는다.
좌표 정본은 layout.py (카드 x50 y360 980x1010 · 라벨 y228/306 · 자막 중심 y1450).
"""
import json
import os
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import CARD_H, CARD_W, CARD_X, CARD_Y, H, W  # noqa: E402
from reel_assets import font_path  # noqa: E402

BAR_H = 68
MINT = (0, 229, 200, 255)
COLORS = {"cmd": (236, 239, 244, 255), "ok": (120, 200, 110, 255), "dim": (140, 148, 160, 255), "acc": MINT}
MONO = font_path("nanumgothiccoding")      # 한글·영문 고정폭을 한 폰트로
LABEL = font_path("pretendard")
FALLBACK = font_path("gothica1")          # ✓✔ 같은 기호 — 고정폭 폰트에 없는 글자만 이걸로 그린다


def _cmap(path, _c={}):
  if path not in _c:
    from fontTools.ttLib import TTFont
    _c[path] = TTFont(path, lazy=True).getBestCmap()
  return _c[path]


def draw_run(d, x, y, s, f, fb, fill):
  """글자마다 고정폭 폰트에 있으면 그대로, 없으면 대체 폰트로 — 두부(□) 방지."""
  cm = _cmap(MONO)
  for ch in s:
    use = f if ord(ch) in cm or ch.isspace() else fb
    d.text((x, y), ch, font=use, fill=fill)
    x += use.getlength(ch)
  return x


def rounded(bg):
  img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
  ImageDraw.Draw(img).rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=22, fill=bg)
  return img


def lights(d, y):
  for i, c in enumerate([(255, 95, 87), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([26 + i * 30, y - 8, 26 + i * 30 + 16, y + 8], fill=c)


def browser(page_png, url, out, secure=True):
  img = rounded((233, 236, 240, 255))
  d = ImageDraw.Draw(img)
  lights(d, BAR_H // 2)
  x0, x1 = 132, CARD_W - 40
  d.rounded_rectangle([x0, 13, x1, BAR_H - 13], radius=20, fill=(255, 255, 255, 255))
  if secure:
    lx, ly = x0 + 24, BAR_H // 2
    d.rounded_rectangle([lx, ly - 3, lx + 13, ly + 8], radius=2, fill=(60, 130, 70))
    d.arc([lx + 2, ly - 12, lx + 11, ly + 1], 180, 360, fill=(60, 130, 70), width=3)
  else:
    d.ellipse([x0 + 22, BAR_H // 2 - 8, x0 + 38, BAR_H // 2 + 8], outline=(130, 136, 145), width=2)
  f = ImageFont.truetype(MONO, 30)
  while f.getlength(url) > x1 - x0 - 70 and f.size > 18:
    f = ImageFont.truetype(MONO, f.size - 1)
  d.text((x0 + 54, BAR_H // 2), url, font=f, fill=(48, 54, 62), anchor="lm")
  page = Image.open(page_png).convert("RGBA")
  ph = CARD_H - BAR_H
  page = page.resize((CARD_W, round(page.height * CARD_W / page.width)), Image.LANCZOS).crop((0, 0, CARD_W, ph))
  img.paste(page, (0, BAR_H))
  mask = Image.new("L", (CARD_W, CARD_H), 0)
  ImageDraw.Draw(mask).rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=22, fill=255)
  img.putalpha(mask)
  img.save(out)
  print(f"→ {out}")


def terminal(lines_txt, out, title="terminal", size=42, lead=62):
  img = rounded((11, 14, 19, 255))
  d = ImageDraw.Draw(img)
  top = 68
  d.rounded_rectangle([0, 0, CARD_W - 1, top + 22], radius=22, fill=(23, 27, 34, 255))
  d.rectangle([0, top - 10, CARD_W - 1, top + 22], fill=(23, 27, 34, 255))
  lights(d, top // 2)
  ft = ImageFont.truetype(LABEL, 26)
  d.text((CARD_W / 2, top // 2), title, font=ft, fill=(140, 148, 160), anchor="mm")
  rows = [r.rsplit("|", 1) if "|" in r else (r, "cmd") for r in open(lines_txt, encoding="utf-8").read().splitlines()]
  f = ImageFont.truetype(MONO, size)
  longest = max((f.getlength(t.replace("**", "")) for t, _ in rows), default=0)
  if longest > CARD_W - 88:     # 46px면 URL 한 줄이 카드 폭을 넘어 잘렸다 — 넘치면 줄인다
    f = ImageFont.truetype(MONO, int(size * (CARD_W - 88) / longest))
  fb = ImageFont.truetype(FALLBACK, f.size)
  y = top + max(46, (CARD_H - top - len(rows) * lead) // 2)
  for text, col in rows:
    x, on = 44, False
    for part in re.split(r"(\*\*)", text):
      if part == "**":
        on = not on; continue
      if not part:
        continue
      c = MINT if on else COLORS.get(col.strip(), COLORS["cmd"])
      x1 = draw_run(d, x, y, part, f, fb, c)
      if on:
        d.line([x, y + f.size * 1.18, x1, y + f.size * 1.18], fill=c, width=3)
      x = x1
    y += lead
  img.save(out)
  print(f"→ {out}")


def capture(url, out, viewport="640x940"):
  npx = shutil.which("npx")
  if not npx:
    sys.exit("npx(Node.js)가 없습니다 — 페이지를 직접 캡처해 PNG로 주거나 Node.js를 설치하세요.")
  w, h = viewport.split("x")
  subprocess.run([npx, "-y", "playwright", "screenshot", "--device=Desktop Chrome HiDPI",
                  f"--viewport-size={w},{h}", url, out], check=True)
  print(f"→ {out} (2배 해상도)")


def render(timing_json, out, audio=None, ass=None, bg=None, color="0E1116", title=None, fps=30):
  t = json.load(open(timing_json, encoding="utf-8"))
  total, cuts = float(t["total"]), t["cuts"]
  if bg:
    bg_full = Image.open(bg).convert("RGB")
    if bg_full.width < W or bg_full.height < H:
      bg_full = bg_full.resize((max(W, bg_full.width), max(H, bg_full.height)), Image.LANCZOS)
  else:
    bg_full = Image.new("RGB", (W, H), tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)))
  pan_x, pan_y = bg_full.width - W, bg_full.height - H
  cache = {}

  def img(p):
    if p not in cache:
      cache[p] = Image.open(p).convert("RGBA")
    return cache[p]

  def faded(im, a):
    if a >= 0.999:
      return im
    o = im.copy(); o.putalpha(o.getchannel("A").point(lambda v: int(v * a))); return o

  title_im = img(title) if title else None

  def frame(i):
    tt = i / fps
    p = tt / total
    fr = bg_full.crop((int(pan_x * p), int(pan_y * p), int(pan_x * p) + W, int(pan_y * p) + H)).convert("RGBA")
    cut = next((c for c in cuts if c["start"] <= tt < c["end"]), cuts[-1])
    lt = tt - cut["start"]
    if cut.get("card"):
      card = img(cut["card"])
      e = 1 - (1 - min(1.0, lt / 0.26)) ** 3
      x = cut.get("x", CARD_X if card.width == CARD_W else (W - card.width) // 2)
      fr.alpha_composite(faded(card, e), (x, cut.get("y", CARD_Y) + int(26 * (1 - e))))
    if cut.get("overlay"):
      b = 1 - (1 - max(0.0, min(1.0, (lt - 0.14) / 0.24))) ** 3
      fr.alpha_composite(faded(img(cut["overlay"]), b), (0, int(18 * (1 - b))))
    if title_im is not None and tt < 1.82:
      a = 1.0 if tt < 1.42 else max(0.0, 1 - (tt - 1.42) / 0.40)
      fr.alpha_composite(faded(title_im, a), (0, 0))
    return fr.convert("RGB")

  cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
  if audio:
    cmd += ["-i", audio]
  vf = f"ass={ass}:fontsdir=_fonts" if ass else "null"
  cmd += ["-vf", vf, "-map", "0:v"] + (["-map", "1:a", "-c:a", "aac", "-b:a", "192k"] if audio else [])
  cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
          "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-t", f"{total:.3f}", out]
  proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
  n = int(total * fps)
  for i in range(n):
    proc.stdin.write(frame(i).tobytes())
  proc.stdin.close()
  assert proc.wait() == 0, "렌더 실패"
  print(f"→ {out} ({total:.2f}s, {n}프레임)")


def opt(a, name, default=None):
  return a[a.index(name) + 1] if name in a else default


if __name__ == "__main__":
  a = sys.argv[1:]
  if not a:
    sys.exit(__doc__)
  if a[0] == "capture":
    capture(a[1], a[2], opt(a, "--viewport", "640x940"))
  elif a[0] == "browser":
    browser(a[1], a[2], a[3], secure="--insecure" not in a)
  elif a[0] == "terminal":
    terminal(a[1], a[2], title=opt(a, "--title", "terminal"))
  elif a[0] == "render":
    render(a[1], a[2], audio=opt(a, "--audio"), ass=opt(a, "--ass"), bg=opt(a, "--bg"),
           color=opt(a, "--color", "0E1116"), title=opt(a, "--title"))
  else:
    sys.exit(__doc__)
