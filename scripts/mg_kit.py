"""모션그래픽 인서트 키트 — 인물 배경을 흐리게 누른 '인서트 창' 위에 띄우는 투명 MOV(ProRes 4444).
팔레트는 잉크 카드 + 흰 선화 + 민트 포인트(인물 인서트형 문법). 요소는 1080 폭 기준 300px 이상 — 작으면 폰에서 안 보인다.

사용:
  python mg_kit.py pile  out.mov --labels "릴스,카드뉴스,제안서,미팅 정리,일정,정산" --title "전부 손으로" [--dur 4.6]
      일감 카드가 떨어져 쌓인다 — "하나하나 손으로 하고 있었다"
  python mg_kit.py cards out.mov --labels "릴스,카드뉴스,강의 자료" --title "콘텐츠 자동화" [--dur 4.8]
      아이콘 카드 3장이 팝 → 체크가 하나씩 붙는다 — "이것들이 자동으로"
  python mg_kit.py tiles out.mov --labels "회원,매출,리포트,일정" --head "운영 대시보드" --title "..." [--dur 4.0]
      대시보드 타일이 차례로 켜진다 — "시스템으로 묶었다"
  python mg_kit.py fork  out.mov --up "쓰는 쪽" --down "안 쓰는 쪽" --title "방식이 갈라진다" [--dur 5.4]
      한 점에서 두 갈래 — 민트 실선 / 회색 점선
  python mg_kit.py demo  <폴더>        # 4종 샘플 + 확인용 PNG

합성 — 인서트 창 a~a+d초 (배경 흐림·어둡게 → 그 위에 MOV):
  [0:v]split[k][b];[b]gblur=sigma=14,drawbox=x=0:y=0:w=iw:h=ih:color=black@0.65:t=fill[dim];
  [k][dim]overlay=enable='between(t,a,a+d)'[v1];[1:v]setpts=PTS-STARTPTS+a/TB[mg];
  [v1][mg]overlay=0:0:eof_action=pass:enable='between(t,a,a+d)'[v]
  → 그 구간 자막은 아래로 내린다 (word_subs.py ass --insert a-a+d)
"""
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reel_assets import font_path  # noqa: E402

W, H, AA, FPS = 1080, 1920, 2, 30
WHITE = (255, 255, 255, 255); MINT = (0, 251, 152, 255); GRAY = (160, 168, 164, 255); INK = (12, 24, 20, 255)
FONT = font_path("pretendard")


def font(size):
  return ImageFont.truetype(FONT, size * AA)


def clamp(v):
  return max(0.0, min(1.0, v))


def ease(u):
  return 1 - (1 - u) ** 3


def pop(u):
  """0.6 → 1.08 → 1.0 오버슈트 팝."""
  if u <= 0:
    return 0.0
  if u < 0.7:
    return 0.6 + 0.48 * ease(u / 0.7)
  return 1.08 - 0.08 * ease((u - 0.7) / 0.3)


def canvas():
  return Image.new("RGBA", (W * AA, H * AA))


def line(im, pts, color, width):
  ImageDraw.Draw(im).line([(x * AA, y * AA) for x, y in pts], fill=color, width=width * AA, joint="curve")


def rrect(im, box, r, outline, width, fill=None):
  ImageDraw.Draw(im).rounded_rectangle([v * AA for v in box], radius=r * AA, outline=outline, width=width * AA, fill=fill)


def text(im, s, xy, size, color, anchor="mm"):
  ImageDraw.Draw(im).text((xy[0] * AA, xy[1] * AA), s, font=font(size), fill=color, anchor=anchor)


def fade_layer(layer, a):
  if a < 1:
    layer.putalpha(layer.getchannel("A").point(lambda v: round(v * a)))
  return layer


def title(im, s, alpha=1.0, y=600):
  """인서트 위 작은 라벨 — 인서트가 무엇인지 한 줄."""
  if s and alpha > 0:
    lay = canvas(); text(lay, s, (540, y), 40, WHITE); im.alpha_composite(fade_layer(lay, alpha))


def fade_edges(im, t, D, fin=0.12, fout=0.15):
  return fade_layer(im, min(clamp(t / fin), clamp((D - t) / fout)))


def scaled(src, s):
  if s <= 0:
    return None
  return src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.Resampling.LANCZOS)


def paste_center(im, art, cx, cy):
  im.alpha_composite(art, (round(cx * AA - art.width / 2), round(cy * AA - art.height / 2)))


# ── pile: 일감 카드가 떨어져 쌓인다 ────────────────────────────────────
def mg_pile(labels, head):
  labels = (labels * 6)[:6]
  rows = [(3, 220, 860, 1290), (2, 380, 700, 1105), (1, 540, 540, 920)]
  drops = []
  for count, left, right, y in rows:
    for col in range(count):
      i = len(drops)
      x = left + (right - left) * col / max(1, count - 1)
      drops.append(dict(start=0.35 + i * 0.42, x=x, y=y, angle=[-8, 6, -5, 7, -4, 3][i], label=labels[i]))

  def card(s):
    im = Image.new("RGBA", (320 * AA, 200 * AA)); rrect(im, (8, 8, 312, 192), 18, WHITE, 7, fill=INK)
    text(im, s, (160, 100), 44 if len(s) <= 5 else 36, WHITE); return im

  def fn(t, D):
    im = canvas()
    for d in drops:
      age = t - d["start"]
      if age < 0:
        continue
      if age < 0.5:
        u = age / 0.5; y = -150 + (d["y"] + 150) * u * u; ang = d["angle"] + 14 * math.sin(u * math.pi)
      else:
        b = age - 0.5; y = d["y"] - (8 * math.sin(math.pi * b / 0.1) if b < 0.1 else 0); ang = d["angle"]
      paste_center(im, card(d["label"]).rotate(ang, Image.Resampling.BICUBIC, expand=True), d["x"], y)
    title(im, head, clamp((t - 0.15) / 0.2))
    return fade_edges(im, t, D)
  return fn


# ── cards: 아이콘 카드 팝 + 체크 ───────────────────────────────────────
def icon_card(kind, s):
  im = Image.new("RGBA", (320 * AA, 400 * AA)); rrect(im, (6, 6, 314, 394), 24, WHITE, 7, fill=INK)
  d = ImageDraw.Draw(im)
  if kind == 0:     # 영상
    rrect(im, (90, 80, 230, 240), 16, WHITE, 6)
    d.polygon([(140 * AA, 125 * AA), (140 * AA, 195 * AA), (200 * AA, 160 * AA)], fill=WHITE)
  elif kind == 1:   # 카드 묶음
    rrect(im, (80, 90, 200, 230), 10, WHITE, 6); rrect(im, (120, 120, 240, 260), 10, WHITE, 6, fill=INK)
  else:             # 문서
    rrect(im, (95, 80, 225, 240), 10, WHITE, 6)
    for yy in (125, 160, 195):
      line(im, [(120, yy), (200 if yy < 195 else 170, yy)], WHITE, 6)
  text(im, s, (160, 320), 42 if len(s) <= 5 else 34, WHITE)
  return im


def check(size=64):
  im = Image.new("RGBA", (size * AA, size * AA))
  ImageDraw.Draw(im).ellipse([2 * AA, 2 * AA, (size - 2) * AA, (size - 2) * AA], fill=MINT)
  line(im, [(size * 0.28, size * 0.52), (size * 0.44, size * 0.68), (size * 0.74, size * 0.36)], INK, 7)
  return im


def mg_cards(labels, head):
  labels = labels[:3]

  def fn(t, D):
    im = canvas()
    xs = [540] if len(labels) == 1 else [190 + i * 700 / (len(labels) - 1) for i in range(len(labels))]
    for i, s in enumerate(labels):
      art = scaled(icon_card(i % 3, s), pop(clamp((t - (0.2 + 0.45 * i)) / 0.35)))
      if art:
        paste_center(im, art, xs[i], 1020)
      ch = scaled(check(), pop(clamp((t - (1.5 + 0.25 * i)) / 0.3)))
      if ch:
        paste_center(im, ch, xs[i] + 138, 840)
    title(im, head, clamp((t - 0.1) / 0.2))
    return fade_edges(im, t, D)
  return fn


# ── tiles: 대시보드 타일이 켜진다 ──────────────────────────────────────
def mg_tiles(labels, panel_head, head):
  labels = (labels * 4)[:4]
  boxes = [(40, 130, 420, 360), (440, 130, 820, 360), (40, 380, 420, 610), (440, 380, 820, 610)]

  def fn(t, D):
    im = canvas()
    panel = Image.new("RGBA", (860 * AA, 640 * AA)); rrect(panel, (6, 6, 854, 634), 26, WHITE, 6, fill=INK)
    line(panel, [(6, 96), (854, 96)], WHITE, 4); text(panel, panel_head, (430, 52), 38, MINT)
    for i, (name, box) in enumerate(zip(labels, boxes)):
      on = clamp((t - (0.6 + i * 0.3)) / 0.25)
      col = tuple(int(WHITE[k] * (1 - on) + MINT[k] * on) for k in range(3)) + (255,)
      rrect(panel, box, 16, col, 5)
      text(panel, name, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), 38, WHITE)
      if on >= 1 and (t - (0.6 + i * 0.3)) < 0.6:   # 켜질 때 짧은 글로우
        g = Image.new("RGBA", panel.size); rrect(g, box, 16, MINT, 10); panel.alpha_composite(fade_layer(g, 0.35))
    art = scaled(panel, pop(clamp(t / 0.35)))
    if art:
      paste_center(im, art, 540, 1010)
    title(im, head, clamp((t - 0.1) / 0.2))
    return fade_edges(im, t, D)
  return fn


# ── fork: 한 점에서 두 갈래 ────────────────────────────────────────────
def bez(p0, p1, p2, n=60):
  return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
           (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]) for u in [k / n for k in range(n + 1)]]


def mg_fork(up, down, head):
  UP = bez((440, 1000), (660, 1000), (930, 760)); DN = bez((440, 1000), (660, 1000), (930, 1240))

  def part(pts, f):
    return pts[:max(2, int(len(pts) * clamp(f)))]

  def fn(t, D):
    im = canvas()
    ImageDraw.Draw(im).ellipse([135 * AA, 985 * AA, 165 * AA, 1015 * AA], fill=WHITE)
    line(im, [(165, 1000), (165 + 275 * clamp(t / 0.45), 1000)], WHITE, 9)
    if t > 0.45:
      u = clamp((t - 0.45) / 0.8)
      line(im, part(UP, u), MINT, 8)
      pts = part(DN, u)
      for i in range(0, len(pts) - 1, 6):
        line(im, pts[i:i + 3], GRAY, 7)
      if u >= 1:
        line(im, [(898, 738), (932, 759), (900, 781)], MINT, 9)
    for s, xy, col, a in [(up, (800, 700), MINT, clamp((t - 1.35) / 0.25)), (down, (800, 1305), GRAY, clamp((t - 1.55) / 0.25))]:
      if a > 0:
        lay = canvas(); text(lay, s, xy, 46, col); im.alpha_composite(fade_layer(lay, a))
    title(im, head, clamp((t - 0.1) / 0.2))
    return fade_edges(im, t, D)
  return fn


# ── 렌더 ───────────────────────────────────────────────────────────────
def render(fn, dur, out):
  """PIL 2배 AA 프레임 → ffmpeg 파이프 → ProRes 4444 알파 MOV. 확인용 PNG 3장도 남긴다."""
  os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
  cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{W}x{H}",
         "-framerate", str(FPS), "-i", "pipe:0", "-an", "-c:v", "prores_ks", "-profile:v", "4",
         "-pix_fmt", "yuva444p10le", "-t", str(dur), out]
  p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
  n = round(dur * FPS)
  for i in range(n):
    art = fn(i / FPS, dur).resize((W, H), Image.Resampling.LANCZOS)
    if i in (int(n * 0.3), int(n * 0.6), int(n * 0.9)):
      art.save(f"{os.path.splitext(out)[0]}_{i:03d}.png")
    p.stdin.write(art.tobytes())
  p.stdin.close()
  assert p.wait() == 0, out
  print(f"→ {out} ({dur}s)")


def opt(args, name, default=None):
  return args[args.index(name) + 1] if name in args else default


if __name__ == "__main__":
  a = sys.argv[1:]
  if len(a) < 2:
    sys.exit(__doc__)
  kind, out = a[0], a[1]
  labels = [s.strip() for s in opt(a, "--labels", "").split(",") if s.strip()]
  head = opt(a, "--title", "")
  if kind == "demo":
    render(mg_pile(["릴스", "카드뉴스", "제안서", "미팅 정리", "일정", "정산"], "전부 손으로"), 4.6, f"{out}/mg_pile.mov")
    render(mg_cards(["릴스", "카드뉴스", "강의 자료"], "콘텐츠 자동화"), 4.8, f"{out}/mg_cards.mov")
    render(mg_tiles(["회원", "매출", "리포트", "일정"], "운영 대시보드", "하나로 묶인 운영"), 4.0, f"{out}/mg_tiles.mov")
    render(mg_fork("쓰는 쪽", "안 쓰는 쪽", "일하는 방식이 갈라진다"), 5.4, f"{out}/mg_fork.mov")
  elif kind == "pile":
    render(mg_pile(labels, head), float(opt(a, "--dur", 4.6)), out)
  elif kind == "cards":
    render(mg_cards(labels, head), float(opt(a, "--dur", 4.8)), out)
  elif kind == "tiles":
    render(mg_tiles(labels, opt(a, "--head", ""), head), float(opt(a, "--dur", 4.0)), out)
  elif kind == "fork":
    render(mg_fork(opt(a, "--up", ""), opt(a, "--down", ""), head), float(opt(a, "--dur", 5.4)), out)
  else:
    sys.exit(__doc__)
