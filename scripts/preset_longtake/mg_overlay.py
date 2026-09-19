"""롱테이크 브이로그 오버레이 — 관찰 자막 스타일 (1080x1920 RGBA PNG 시퀀스, 30fps).
레퍼런스 실측(좋아요 3만+ 육아 롱테이크): 타이틀 약 115px + 부제 46px(0~2.6초), 본문 자막 54px 흰색+검은 외곽선,
인물을 피해 배경 쪽에 배치, 어둠 띠 없음(외곽선만으로 가독성 확보).
새 릴스에서 바꾸는 곳: TITLE · CAPS (자막은 반말 관찰 일기체 — preset-longtake.md)
사용: python3 mg_overlay.py [out_dir]   (기본 ./ov) — 겹침·폭 검사를 먼저 돌리고 렌더한다
"""
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
from timeline import FPS, TOTAL_FRAMES  # noqa: E402

W, H = 1080, 1920
F_TITLE = font_path("jalnan", "gasoekone")   # 직접 넣은 잘난체 > 가석원체
F_BODY = font_path("pretendard")             # Pretendard Black
WHITE = (255, 255, 255, 255); BLK = (17, 17, 17, 255)
MAXW = 960

TITLE = dict(f0=0, f1=78, main="강아지 일상", sub="- 목욕 대작전 -", y=430)

# (시작f, 끝f, 문구, 크기, 중심y) — y는 인물·주인공을 피해 배경 쪽 (주인공이 하단이면 430, 화면을 채우면 470)
# 문구는 그 구간에 실제로 벌어지는 동작과 맞아야 한다 — qa_strip.py 1초 시트로 대조한다.
CAPS = [
  (90, 186, "목욕하자니까 일단 숨음", 54, 430),
  (196, 236, "찾았다ㅋ", 54, 430),
  (255, 362, "물 보자마자 얼음", 54, 430),
  (376, 470, "잠깐은 얌전했음", 54, 430),
  (495, 648, "샴푸 들자마자 탈출 시도", 54, 430),
  (676, 828, "또 잡힘ㅋㅋ", 54, 430),
  (856, 916, "이번엔 진짜 끝난 줄 알았는데", 54, 430),
  (928, 998, "털면서 온 집안 투어", 54, 430),
  (1014, 1094, "수건 들고 쫓아갔지만", 54, 470),
  (1105, 1156, "결국 소파 점령ㅠ", 58, 470),
  (1162, 1262, "본인이 제일 억울한 표정", 54, 470),
  (1278, 1360, "씻은 건 난데 왜 네가 지쳐", 54, 470),
  (1382, 1437, "결국 간식으로 화해ㅋ", 54, 470),
]

_fc = {}
def font(path, size):
  k = (path, size)
  if k not in _fc:
    _fc[k] = ImageFont.truetype(path, size)
  return _fc[k]

def clamp(x, a=0.0, b=1.0):
  return max(a, min(b, x))

def ease_out_cubic(t):
  t = clamp(t); return 1 - (1 - t) ** 3

def text_img(txt, fnt, fill=WHITE, stroke=5, sfill=BLK):
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  b = d.textbbox((0, 0), txt, font=fnt, stroke_width=stroke)
  pad = stroke + 2
  im = Image.new("RGBA", (b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad), (0, 0, 0, 0))
  ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), txt, font=fnt, fill=fill,
                          stroke_width=stroke, stroke_fill=sfill)
  return im

def fit_font(txt, path, size, maxw=MAXW, minsize=40):
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  while size > minsize:
    f = font(path, size)
    if d.textlength(txt, font=f) <= maxw:
      break
    size -= 2
  return font(path, size)

def shadow(im, alpha=0.45, blur=8, dx=0, dy=5):
  M = blur * 2 + max(abs(dx), abs(dy))
  out = Image.new("RGBA", (im.width + 2 * M, im.height + 2 * M), (0, 0, 0, 0))
  sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
  sh.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
  sh = sh.filter(ImageFilter.GaussianBlur(blur))
  out.alpha_composite(sh, (M + dx, M + dy)); out.alpha_composite(im, (M, M))
  return out

def paste(cv, im, x, y, scale=1.0, alpha=1.0):
  if alpha <= 0.002 or scale <= 0.01:
    return
  if abs(scale - 1) > 1e-3:
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
  if alpha < 0.998:
    im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
  w, h = im.size
  px, py = round(x - w / 2), round(y - h / 2)
  sx0, sy0 = max(0, -px), max(0, -py)
  sx1, sy1 = min(w, cv.width - px), min(h, cv.height - py)
  if sx1 <= sx0 or sy1 <= sy0:
    return
  if (sx0, sy0, sx1, sy1) != (0, 0, w, h):
    im = im.crop((sx0, sy0, sx1, sy1))
  cv.alpha_composite(im, (max(0, px), max(0, py)))

def draw_title(cv, n):
  f0, f1 = TITLE["f0"], TITLE["f1"]
  if not (f0 <= n < f1): return
  lt = n - f0
  al = ease_out_cubic(lt / 8) if lt < 8 else (1.0 if f1 - n > 8 else (f1 - n) / 8)
  sc = 1.06 - 0.06 * ease_out_cubic(lt / 10)
  main = shadow(text_img(TITLE["main"], fit_font(TITLE["main"], F_TITLE, 116), stroke=7))
  paste(cv, main, W / 2, TITLE["y"], scale=sc, alpha=al)
  if lt > 5:
    a2 = ease_out_cubic((lt - 5) / 8) * al
    sub = shadow(text_img(TITLE["sub"], font(F_TITLE, 46), stroke=4))
    paste(cv, sub, W / 2, TITLE["y"] + 108, alpha=a2)

def draw_cap(cv, n, f0, f1, txt, size, cy):
  if not (f0 <= n < f1): return
  lt = n - f0; rem = f1 - n
  al = ease_out_cubic(lt / 4) if lt < 4 else (1.0 if rem > 4 else rem / 4)
  im = shadow(text_img(txt, fit_font(txt, F_BODY, size), stroke=5))
  paste(cv, im, W / 2, cy, alpha=al)

OUT_DIR = None
def render_frame(n):
  cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
  draw_title(cv, n)
  for f0, f1, txt, size, cy in CAPS:
    draw_cap(cv, n, f0, f1, txt, size, cy)
  cv.save(f"{OUT_DIR}/{n:04d}.png", compress_level=1)
  return n

def _init(d):
  global OUT_DIR
  OUT_DIR = d

def lint():
  """자막 2개가 같은 시각에 겹치면 못 읽는다 — 렌더 전에 코드로 막는다. 폭도 함께 본다."""
  bad = []
  for (a0, a1, t0, *_), (b0, b1, t1, *_) in zip(CAPS, CAPS[1:]):
    if a1 > b0:
      bad.append(f"겹침: '{t0}'(~f{a1}) ↔ '{t1}'(f{b0}~)")
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  for _, _, t, size, _ in CAPS:
    if d.textlength(t, font=font(F_BODY, size)) > MAXW:
      bad.append(f"폭 초과(자동 축소됨): '{t}'")
  for b in bad:
    print("⚠️ " + b)
  return not any(b.startswith("겹침") for b in bad)


if __name__ == "__main__":
  if not lint():
    sys.exit("자막 겹침을 먼저 고친다")
  args = sys.argv[1:]
  out = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ov")
  os.makedirs(out, exist_ok=True)
  with Pool(8, initializer=_init, initargs=(out,)) as pool:
    done = 0
    for _ in pool.imap_unordered(render_frame, range(TOTAL_FRAMES), chunksize=4):
      done += 1
      if done % 400 == 0: print(f"{done}/{TOTAL_FRAMES}", flush=True)
  print(f"완료 {TOTAL_FRAMES}f → {out}")
