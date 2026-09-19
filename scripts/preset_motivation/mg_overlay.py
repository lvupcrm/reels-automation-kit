"""모티베이션 몽타주 오버레이 — 전 구간 자막 블록 + 프리즈 오프너(freeze_fx) (1080x1920 RGBA PNG 시퀀스, 30fps).
서브(작게)+키(크게) 블록, 비트에 맞춘 팝/플리커/플래시, 드롭 슬램, 로고 범퍼.
새 릴스에서 바꾸는 곳: TS(오프닝 타임스탬프) · BLOCKS(카피) · SLAM(드롭 한 줄) · TAGLINE · logo.png(선택)
대형 워드마크·빨간 밑줄은 넣지 않는다(검증 때 빼달라는 피드백 — 카피가 묻힌다).
사용: python3 mg_overlay.py [out_dir]   (기본 ./ov)
"""
import math
import os
import sys
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (os.path.dirname(HERE), os.path.expanduser("~/.claude/skills/reel/scripts")):
  if os.path.exists(os.path.join(_p, "reel_assets.py")):
    sys.path.insert(1, _p); break
from reel_assets import font_path  # noqa: E402
sys.modules.setdefault("mg_overlay", sys.modules[__name__])   # 스크립트(__main__/__mp_main__)로 돌아도 freeze_fx 가 이 모듈을 찾게
from timeline import BAR, BEAT, FPS, FREEZE, TOTAL_FRAMES  # noqa: E402

W, H = 1080, 1920
F_HEAD = font_path("gasoekone")          # 타임스탬프만
F_BODY = font_path("pretendard")         # Pretendard Black — 자막 블록
F_TITLE = font_path("jalnan", "dohyeon")  # 프리즈 타이틀 — 가석원체는 초성 ㄹ이 ㅌ처럼 읽혀 쓰지 않는다. 새 폰트는 자모 스윕으로 확인
LOGO = os.path.join(HERE, "logo.png")     # 선택 — 없으면 BRAND 글자 워드마크로 대신한다
RED = (252, 0, 0, 255); WHITE = (255, 255, 255, 255); BLK = (0, 0, 0, 255); OUT = (20, 13, 8, 255)
MAXW = 940  # 텍스트 최대 폭(양옆 70px 안전)

def fr(k_bar, beat=0, f=0):
  return k_bar * BAR + beat * BEAT + f

# ── 자막 블록: (시작f, 끝f, 서브, 키, 키크기) — 키는 "\n"으로 2줄 가능 ─────────
TS = dict(f0=3, f1=(FREEZE["f0"] - 2) if FREEZE else fr(1, 2), text="AM 07:00")   # 프리즈를 쓰면 진입 전에 끝낸다
# 카피 6~9줄: 취지(왜 하는지) + 감정(힘든 순간) + 관계(같이 하는 사람)를 섞는다. 이모지는 폰트에 없다 → "!"로.
BLOCKS = ([] if FREEZE else [   # 프리즈 오프너 카드(freeze_fx.py 의 BRAND/TITLE/DESC)가 훅 블록을 대체한다
  (fr(1) + 6, fr(2) - 2, "남들 아직 잘 때,", "우리의 주말은\n이렇게 시작합니다", 84),
]) + [
  (fr(2), fr(3), "", "숨이 차는 순간", 96),
  (fr(3), fr(4) - 2, "", "멈추고 싶은 순간", 96),
  (fr(6), fr(8) - 2, "선선한 날씨에 야외 운동,", "이것까지 함께합니다!", 84),
  (fr(8), fr(10) - 4, "기록이 아니라", "오늘의 한 바퀴", 116),
  (fr(10), fr(11), "혼자 하기 싫고", "의욕이 없는 날에도", 96),
  (fr(11), fr(12) - 2, "", "움직일 수밖에\n없게 만들어 드립니다!", 84),
  (fr(12) + 4, fr(13, 2), "", "옆에 같이 뛰는 사람", 96),
  (fr(14), fr(15) - 2, "더 활기찬 주말을 위해", "주말 아침, 누구보다\n빠르게 움직여요", 84),
]
SLAM = dict(f0=fr(4, 1), f1=fr(6) - 2, text="그래도 앞으로", size=150)  # 드롭 슬램 (글자별 스태거)
FLICKER = {
  **{f: "white" for f in (fr(4, 0, 2), fr(4, 0, 3), fr(4, 0, 6), fr(4, 0, 7), fr(4, 0, 10), fr(4, 0, 11))},
  **{f: "white" for f in (fr(11, 3, 2), fr(11, 3, 3), fr(11, 3, 10), fr(11, 3, 11))},
  **{f: "black" for f in (fr(11, 3, 6), fr(11, 3, 13))},
}
FLASHES = [(fr(8), 0.7), (fr(12), 0.9), (fr(4, 1), 1.0)]
if FREEZE:   # 프리즈 진입·해제 섬광 — 2f 폭으로 ±1 드리프트를 흡수, 2f 째는 낮춰 얼린 화면을 드러낸다
  FLASHES += [(FREEZE["f0"] - 2, 0.85), (FREEZE["f0"] - 1, 0.42),
              (FREEZE["f0"] + FREEZE["n"] - 2, 0.55), (FREEZE["f0"] + FREEZE["n"] - 1, 0.30)]
LOGO_F0, LOGO_F1 = fr(15), TOTAL_FRAMES
TAGLINE = "태그라인 한 줄"
BRAND = "BRAND"   # logo.png 가 없을 때 범퍼에 쓰는 글자 워드마크

# ── 유틸 ─────────────────────────────────────────────────────────────
_fc = {}
def font(path, size):
  k = (path, size)
  if k not in _fc:
    _fc[k] = ImageFont.truetype(path, size)
  return _fc[k]

def clamp(x, a=0.0, b=1.0):
  return max(a, min(b, x))

def ease_out_back(t, s=1.70158):
  t = clamp(t); return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2

def ease_out_cubic(t):
  t = clamp(t); return 1 - (1 - t) ** 3

def ease_in_cubic(t):
  t = clamp(t); return t ** 3

def text_img(txt, fnt, fill, stroke=0, sfill=OUT):
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  b = d.textbbox((0, 0), txt, font=fnt, stroke_width=stroke)
  pad = stroke + 2
  im = Image.new("RGBA", (b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad), (0, 0, 0, 0))
  ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), txt, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=sfill)
  return im

def fit_font(txt, path, size, maxw=MAXW, minsize=60):
  """폭이 maxw를 넘으면 크기를 줄인다 (줄별 최대 폭 기준)."""
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  while size > minsize:
    f = font(path, size)
    if max(d.textlength(line, font=f) for line in txt.split("\n")) <= maxw:
      break
    size -= 2
  return font(path, size), size

def shadow(im, alpha=0.6, blur=10, dx=0, dy=8):
  M = blur * 2 + max(abs(dx), abs(dy))
  out = Image.new("RGBA", (im.width + 2 * M, im.height + 2 * M), (0, 0, 0, 0))
  sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
  sh = sh.filter(ImageFilter.GaussianBlur(blur))
  out.alpha_composite(sh, (M + dx, M + dy)); out.alpha_composite(im, (M, M))
  return out

def paste(cv, im, x, y, scale=1.0, alpha=1.0, anchor="mm"):
  if alpha <= 0.002 or scale <= 0.01:
    return
  if abs(scale - 1) > 1e-3:
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
  if alpha < 0.998:
    im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
  w, h = im.size
  if anchor == "mm": px, py = round(x - w / 2), round(y - h / 2)
  elif anchor == "lm": px, py = round(x), round(y - h / 2)
  else: px, py = round(x), round(y)
  sx0, sy0 = max(0, -px), max(0, -py)
  sx1, sy1 = min(w, cv.width - px), min(h, cv.height - py)
  if sx1 <= sx0 or sy1 <= sy0:
    return
  if (sx0, sy0, sx1, sy1) != (0, 0, w, h):
    im = im.crop((sx0, sy0, sx1, sy1))
  cv.alpha_composite(im, (max(0, px), max(0, py)))

def solid(alpha, color=(0, 0, 0)):
  return Image.new("RGBA", (W, H), (*color, int(255 * clamp(alpha))))

_band = None
def band():
  global _band
  if _band is None:
    h = 760; im = Image.new("RGBA", (W, h), (0, 0, 0, 0)); px = im.load()
    for y in range(h):
      a = int(255 * 0.32 * max(0.0, math.sin(math.pi * y / (h - 1))) ** 1.3)
      for x in range(W):
        px[x, y] = (0, 0, 0, a)
    _band = im
  return _band

_logo = None
def logo():
  """로고 PNG를 흰 실루엣으로 — 폭 480. 배경이 불투명한 로고(밝은 배경+어두운 선)도 명도 마스크로 뜬다
  (알파를 그대로 쓰면 흰 사각형이 된다). logo.png 가 없으면 BRAND 글자로 대신한다."""
  global _logo
  if _logo is None and not os.path.exists(LOGO):
    _logo = text_img(BRAND, font(F_TITLE, 120), WHITE)
  if _logo is None:
    import numpy as np
    g = np.asarray(Image.open(LOGO).convert("L")).astype(float)
    bg, fg = np.percentile(g, 95), np.percentile(g, 2)
    m = np.clip((bg - g) / max(bg - fg, 1.0), 0, 1)
    mask = Image.fromarray((m * 255).astype("uint8"))
    im = Image.new("RGBA", mask.size, (255, 255, 255, 255)); im.putalpha(mask)
    im = im.crop(mask.point(lambda v: 255 if v > 40 else 0).getbbox())
    s = 480 / im.width
    _logo = im.resize((480, max(1, round(im.height * s))), Image.LANCZOS)
  return _logo

# ── 요소 ─────────────────────────────────────────────────────────────
def draw_ts(cv, n):
  f0, f1 = TS["f0"], TS["f1"]
  if not (f0 <= n < f1): return
  lt = (n - f0) / FPS
  k = int(round(ease_out_cubic(lt / 0.5) * len(TS["text"])))
  txt = TS["text"][:k] + ("_" if (lt * 2.5) % 1 < 0.5 else " ")
  im = text_img(txt, font(F_HEAD, 46), WHITE, 3, BLK)
  al = 1.0 if f1 - n > 5 else (f1 - n) / 5
  paste(cv, im, 118, 214, alpha=al, anchor="lm")
  if (lt * 2) % 1 < 0.6:
    dot = Image.new("RGBA", (22, 22), (0, 0, 0, 0)); ImageDraw.Draw(dot).ellipse([0, 0, 21, 21], fill=RED)
    paste(cv, dot, 86, 214, alpha=al)

def pop(n, f0, frames=6):
  p = ease_out_cubic((n - f0) / frames)
  return p, 1.12 - 0.12 * p

def draw_block(cv, n, f0, f1, sub, key, ksize):
  """서브(위, 작게) + 키(아래, 크게·2줄 가능). 서브 먼저, 키는 4f 뒤 팝."""
  if not (f0 <= n < f1): return
  rem = f1 - n
  fade = 1.0 if rem > 3 else rem / 3
  kf, ks = fit_font(key, F_BODY, ksize)
  klines = key.split("\n")
  line_h = int(ks * 1.18)
  block_h = line_h * len(klines)
  cy = 880
  al, sc = pop(n, f0)
  paste(cv, band(), W / 2, cy, alpha=al * fade)
  if sub:
    im = shadow(text_img(sub, font(F_BODY, 60), WHITE))
    paste(cv, im, W / 2, cy - block_h / 2 - 66, scale=sc, alpha=al * fade)
  al2, sc2 = pop(n, f0 + (4 if sub else 0))
  y0 = cy - block_h / 2 + line_h / 2
  for i, line in enumerate(klines):
    im = shadow(text_img(line, kf, WHITE))
    paste(cv, im, W / 2, y0 + i * line_h, scale=sc2, alpha=al2 * fade)

def draw_slam(cv, n):
  f0, f1 = SLAM["f0"], SLAM["f1"]
  if not (f0 <= n < f1): return
  lt = n - f0; rem = f1 - n
  layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
  fm, _ = fit_font(SLAM["text"], F_BODY, SLAM["size"], maxw=980)
  d = ImageDraw.Draw(layer)
  chars = SLAM["text"]
  adv = [d.textlength(ch, font=fm) for ch in chars]
  total = sum(adv); x = (W - total) / 2
  paste(layer, band(), W / 2, 880, alpha=ease_out_cubic(lt / 4))
  for i, (ch, a) in enumerate(zip(chars, adv)):
    if ch == " ":
      x += a; continue
    p = (lt - i * 1.0) / 7.0
    if p > 0:
      im = shadow(text_img(ch, fm, WHITE), alpha=0.7, blur=12, dy=10)
      paste(layer, im, x + a / 2, 880, scale=2.0 - 1.0 * ease_out_back(p), alpha=ease_out_cubic(p * 2.5))
    x += a
  if rem < 4:
    q = ease_in_cubic(1 - rem / 4)
    paste(cv, layer, W / 2, H / 2, scale=1 + 0.12 * q, alpha=1 - q)
  else:
    cv.alpha_composite(layer)

def draw_logo(cv, n):
  if not (LOGO_F0 <= n < LOGO_F1): return
  lt = n - LOGO_F0
  cv.alpha_composite(solid(0.55 * ease_out_cubic(lt / 10)))
  p = (lt - 4) / 9
  if p > 0:
    paste(cv, shadow(logo(), alpha=0.5, blur=14, dy=6), W / 2, 880, scale=max(0.05, 0.7 + 0.3 * ease_out_back(p)), alpha=ease_out_cubic(p * 2))
  q = ease_out_cubic((lt - 14) / 8)
  if q > 0:
    im = text_img(TAGLINE, font(F_BODY, 40), (255, 255, 255, 235))
    paste(cv, im, W / 2, 1050 + 16 * (1 - q), alpha=q)

def draw_fx(cv, n):
  col = FLICKER.get(n)
  if col:
    cv.alpha_composite(solid(0.95, (255, 255, 255) if col == "white" else (0, 0, 0)))
  for f0, amax in FLASHES:
    lt = n - f0
    if 0 <= lt < 4:
      cv.alpha_composite(solid(amax * (1 - ease_out_cubic(lt / 4)), (255, 255, 255)))

from freeze_fx import draw_freeze  # noqa: E402  — 헬퍼 정의 뒤에 import (순환 import 회피). FREEZE 가 None 이면 no-op

# ── 프레임 ───────────────────────────────────────────────────────────
OUT_DIR = None
def render_frame(n):
  cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
  draw_ts(cv, n)
  for f0, f1, sub, key, ks in BLOCKS:
    draw_block(cv, n, f0, f1, sub, key, ks)
  draw_slam(cv, n); draw_freeze(cv, n); draw_logo(cv, n); draw_fx(cv, n)
  cv.save(f"{OUT_DIR}/{n:04d}.png", compress_level=1)
  return n

def _init(d):
  global OUT_DIR
  OUT_DIR = d

if __name__ == "__main__":
  args = sys.argv[1:]
  out = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ov")
  os.makedirs(out, exist_ok=True)
  with Pool(8, initializer=_init, initargs=(out,)) as pool:
    done = 0
    for _ in pool.imap_unordered(render_frame, range(TOTAL_FRAMES), chunksize=4):
      done += 1
      if done % 200 == 0: print(f"{done}/{TOTAL_FRAMES}", flush=True)
  print(f"완료 {TOTAL_FRAMES}f → {out}")
