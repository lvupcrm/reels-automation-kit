"""프리즈 오프너 풀스택 — 오버레이 층 (mg_overlay 가 헬퍼 정의 뒤에 import 한다). timeline.FREEZE 가 None 이면 아무것도 안 그린다.

재사용 시 바꾸는 곳: 아래 BRAND/TITLE/DESC(문구) · TSIZE/CX/CY(패널 크기·위치 — 누끼 알파로 글자 가림률을 격자 탐색해 정한다)
· LAG(베이스 드리프트 실측값 — 오버레이 없이 렌더해 정지 구간 시작 프레임을 재고 FREEZE.f0 와의 차이를 넣는다).

원본 기법(Threads 'Freeze frame' 모션그래픽 튜토리얼)의 얼린 화면 순서를 그대로 따른다:
  망점 → 집중선 → 종이결 → 색 패널+흰 점선 → CC Jaws 리빌 → 타이포 → 잘라낸 피사체 → 마름모 비네트
배경 뭉갬은 컷 입력(opener_bg.png)에 있고, 나머지 전부를 여기서 프레임마다 그린다.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

from mg_overlay import (F_BODY, F_TITLE, H, RED, W, WHITE, clamp, ease_in_cubic, ease_out_back,
                        ease_out_cubic, fit_font, font, paste, shadow, text_img)
from timeline import FREEZE, FREEZE_PNG, FREEZE_SUB

BRAND, TITLE, DESC = "BRAND NAME", "주말 아침 러닝", "남들 아직 잘 때 시작하는 아침"
TSIZE = 104
CX, CY = 600, 1400        # 패널 중심 — 누끼 알파로 글자 가림률을 크기×위치 격자 탐색해 최소점을 고른다 (preset-motivation.md)
ANGLE = 7                 # PIL 반시계 = 원본의 −7°
LAG = -1                  # 렌더 실측 보정: 앞선 컷 fps 재샘플로 베이스가 1프레임 당겨진다 (검증작: 정지 구간 f55~f96). 새 소스면 다시 잰다
FZ0 = (FREEZE["f0"] + LAG) if FREEZE else 0
FZ1 = (FZ0 + FREEZE["n"]) if FREEZE else 0
PANEL_IN, PANEL_WIPE = 3, 8   # CC Jaws 리빌: 정지 +3f 부터 8f 동안
SEED = 20260912

# ── 텍스트·테두리 ─────────────────────────────────────────────────────
def track(txt, fnt, fill, sp):
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  ws = [d.textlength(ch, font=fnt) for ch in txt]
  asc, dsc = fnt.getmetrics()
  im = Image.new("RGBA", (int(sum(ws) + sp * max(0, len(txt) - 1)) + 4, asc + dsc + 4), (0, 0, 0, 0))
  dd = ImageDraw.Draw(im)
  x = 2.0
  for ch, w in zip(txt, ws):
    dd.text((x, 2), ch, font=fnt, fill=fill)
    x += w + sp
  return im

def dash_rect(d, box, dash=22, gap=14, width=4, fill=WHITE):
  x0, y0, x1, y1 = box
  for ax, ay, bx, by in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    t = 0.0
    while t < L:
      e = min(t + dash, L)
      d.line([ax + ux * t, ay + uy * t, ax + ux * e, ay + uy * e], fill=fill, width=width)
      t += dash + gap

# ── 피사체 묶음: 본체·스티커 외곽·그림자·에코, 초점점 ──────────────────
_S = {}
def subj():
  if _S:
    return _S
  im = Image.open(FREEZE_SUB).convert("RGBA")
  a = np.asarray(im.split()[3], np.float32) / 255
  ys, xs = np.nonzero(a > 0.08)
  if len(xs) < 2000:   # 사람이 안 잡힌 프레임 — 누끼 층 없이 망점·집중선·패널만 (freeze_seg 가 이미 경고했다)
    _S.update(focus=(W / 2, H * 0.45), center=None)
    return _S
  M = 48
  x0, x1 = max(0, xs.min() - M), min(W, xs.max() + M)
  y0, y1 = max(0, ys.min() - M), min(H, ys.max() + M)
  sub = im.crop((x0, y0, x1, y1))
  ab = a[y0:y1, x0:x1]
  fy, fx = ndi.center_of_mass(ab)
  _S["focus"] = (x0 + fx, y0 + fy)
  _S["center"] = ((x0 + x1) / 2, (y0 + y1) / 2)
  sil = Image.fromarray((ab * 255).astype(np.uint8))
  # 스티커 외곽선 — 알파를 7px 팽창시킨 흰 실루엣
  dil = ndi.binary_dilation(ab > 0.5, iterations=7)
  outline = Image.new("RGBA", sub.size, (255, 255, 255, 0))
  outline.putalpha(Image.fromarray((dil * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)))
  sh = Image.new("RGBA", sub.size, (0, 0, 0, 0))
  sh.putalpha(sil.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.55)))
  echo_r = Image.new("RGBA", sub.size, (*RED[:3], 0))
  echo_r.putalpha(sil.point(lambda v: int(v * 0.55)))
  echo_w = Image.new("RGBA", sub.size, (255, 255, 255, 0))
  echo_w.putalpha(sil.point(lambda v: int(v * 0.30)))
  _S.update(sub=sub, outline=outline, shadow=sh, echo_r=echo_r, echo_w=echo_w)
  return _S

# ── ① 망점: 뭉갠 배경 밝기로 점 크기 변조 (어두울수록 큰 점) ────────────
_half = None
def halftone(P=16):
  global _half
  if _half is None:
    lum = np.asarray(Image.open(FREEZE_PNG).convert("L"), np.float32) / 255
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = (0, 0, 0, int(255 * 0.30))
    for j, y in enumerate(range(0, H + P, P)):
      off = P // 2 if j % 2 else 0
      for x in range(-off, W + P, P):
        l = lum[min(max(y, 0), H - 1), min(max(x, 0), W - 1)]
        r = 1.0 + 5.2 * (1 - l) ** 1.3
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    _half = im
  return _half

# ── ② 집중선: 초점점(피사체 무게중심)에서 방사, 마름모 반전 마스크로 중심은 비움 ──
_lines = None
def speed_lines():
  global _lines
  if _lines is None:
    fx, fy = subj()["focus"]
    rng = np.random.default_rng(SEED)
    L = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(L)
    R = math.hypot(W, H)
    for _ in range(140):
      th = rng.uniform(0, 2 * math.pi)
      r0 = rng.uniform(300, 520)
      w = int(rng.choice([2, 2, 3, 3, 4, 5, 7]))
      d.line([fx + r0 * math.cos(th), fy + r0 * math.sin(th), fx + R * math.cos(th), fy + R * math.sin(th)],
             fill=255, width=w)
    yy, xx = np.mgrid[0:H, 0:W]
    dd = np.abs(xx - fx) / (W * 0.55) + np.abs(yy - fy) / (H * 0.55)
    m = np.clip((dd - 0.45) / 0.55, 0, 1) ** 0.9
    a = (np.asarray(L, np.float32) / 255 * m * 255).astype(np.uint8)
    im = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    im.putalpha(Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8)))
    _lines = im
  return _lines

# ── ③ 종이결: 미세 노이즈 + 성긴 얼룩 두 옥타브 ──────────────────────────
_paper = None
def paper():
  global _paper
  if _paper is None:
    rng = np.random.default_rng(SEED + 1)
    fine = rng.normal(0, 1, (H, W)).astype(np.float32)
    coarse = ndi.gaussian_filter(rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32), 2)
    coarse = np.asarray(Image.fromarray(coarse).resize((W, H), Image.BILINEAR), np.float32)
    n = fine * 0.6 + coarse * 1.6
    n = (n - n.min()) / (n.max() - n.min())
    g = Image.fromarray((n * 255).astype(np.uint8))
    _paper = Image.merge("RGBA", [g, g, g, Image.new("L", (W, H), int(255 * 0.11))])
  return _paper

# ── ④ 패널(회전 전) + 글자별 좌표 ─────────────────────────────────────
_P = {}
def panel():
  if _P:
    return _P
  f_brand = font(F_BODY, 40)
  f_title, _ = fit_font(TITLE, F_TITLE, TSIZE, maxw=780)
  f_desc = font(F_BODY, 44)
  brand = track(BRAND, f_brand, WHITE, 7)
  title = text_img(TITLE, f_title, WHITE)
  desc = text_img(DESC, f_desc, (255, 255, 255, 235))
  gaps, padl, padr, padt, padb = [20, 26], 100, 36, 44, 50   # 비대칭 여백 — 앞 인물이 겹치는 쪽을 넓혀 글자 대신 색 면만 가리게
  cw = max(brand.width, title.width, desc.width)
  pw = cw + padl + padr
  ph = padt + brand.height + title.height + desc.height + sum(gaps) + padb
  base = Image.new("RGBA", (pw, ph), RED)
  dash_rect(ImageDraw.Draw(base), (18, 18, pw - 18, ph - 18))
  ccx = padl + cw / 2                                       # 글자 블록 중심 x
  y = padt
  base.alpha_composite(brand, (int(ccx - brand.width / 2), y))
  y += brand.height + gaps[0]
  ty = y
  y += title.height + gaps[1]
  base.alpha_composite(desc, (int(ccx - desc.width / 2), y))
  # 타이틀은 base 에 굽지 않고 글자별로 스태거 — 전체 문자열 원점 기준으로 각 글자의 중심을 계산
  d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
  b = d.textbbox((0, 0), TITLE, font=f_title)
  pad = 2
  ox, oy = int(ccx - title.width / 2) + pad - b[0], ty + pad - b[1]
  glyphs = []
  for i, ch in enumerate(TITLE):
    if ch == " ":
      continue
    adv = d.textlength(TITLE[:i], font=f_title)
    gb = d.textbbox((0, 0), ch, font=f_title)
    glyphs.append((text_img(ch, f_title, WHITE), ox + adv + (gb[0] + gb[2]) / 2, oy + (gb[1] + gb[3]) / 2))
  _P.update(base=base, pw=pw, ph=ph, glyphs=glyphs)
  return _P

def title_layer(lt):
  P = panel()
  im = Image.new("RGBA", (P["pw"], P["ph"]), (0, 0, 0, 0))
  for i, (g, gx, gy) in enumerate(P["glyphs"]):
    t = clamp((lt - PANEL_IN - 3 - i * 1.1) / 6)
    if t <= 0:
      continue
    paste(im, g, gx, gy, scale=1.9 - 0.9 * ease_out_back(t), alpha=clamp(t * 2.5))
  return im

def jaws(pw, ph, prog, J=26, period=34.0):
  """CC Jaws 근사 — 톱니 경계가 패널 긴 축을 따라 쓸고 지나가며 드러낸다 (회전 전 패널 공간)."""
  y = np.arange(ph)
  zig = (np.abs(((y / period) % 2) - 1) * 2 - 1) * J
  edge = prog * (pw + 2 * J) - J + zig
  return Image.fromarray(((np.arange(pw)[None, :] < edge[:, None]) * 255).astype(np.uint8))

# ── ⑥ 마름모 비네트 ─────────────────────────────────────────────────
_vig = None
def vignette():
  global _vig
  if _vig is None:
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.abs(xx - W / 2) / (W / 2) * 0.62 + np.abs(yy - H / 2) / (H / 2) * 0.38
    a = (255 * 0.42 * np.clip((d - 0.42) / 0.58, 0, 1) ** 1.4).astype(np.uint8)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.putalpha(Image.fromarray(a).filter(ImageFilter.GaussianBlur(6)))
    _vig = im
  return _vig

# ── 프레임 합성 ──────────────────────────────────────────────────────
def draw_freeze(cv, n):
  if not FREEZE or not (FZ0 <= n < FZ1):
    return
  lt, out, hold = n - FZ0, FZ1 - n, FREEZE["n"] - 1
  fx, fy = subj()["focus"]
  cv.alpha_composite(halftone())                                                     # ① 망점
  lines = speed_lines().rotate(-lt * 0.5, resample=Image.BILINEAR, center=(fx, fy))  # ② 집중선 — 느리게 돌며 미세 깜빡
  paste(cv, lines, W // 2, H // 2, alpha=0.50 * (0.82 + 0.18 * abs(math.sin(lt * 1.7))) * clamp(lt / 2))
  cv.alpha_composite(paper())                                                        # ③ 종이결
  P = panel()                                                                        # ④ 패널: CC Jaws 리빌 + 글자 스태거
  prog = clamp((lt - PANEL_IN) / PANEL_WIPE)
  if prog > 0:
    comp = P["base"].copy()
    comp.alpha_composite(title_layer(lt))
    if prog < 1:
      comp.putalpha(Image.fromarray(np.minimum(np.asarray(comp.split()[3]), np.asarray(jaws(P["pw"], P["ph"], prog)))))
    comp = comp.rotate(ANGLE, resample=Image.BICUBIC, expand=True)
    pa = 1.0 if out > 5 else ease_in_cubic(out / 5)
    paste(cv, shadow(comp, alpha=0.55, blur=22, dy=14), CX, CY, scale=1.0 + 0.03 * (1 - prog), alpha=pa)
  S = subj()                                                                         # ⑤ 피사체: 에코 → 그림자 → 스티커 외곽 → 본체
  if S["center"] is None:
    cv.alpha_composite(vignette())
    return
  bx, by = S["center"]
  sa = clamp(lt / 1.5)
  punch = 1.0 + 0.05 * (1 - ease_out_cubic(clamp(lt / 7))) + 0.015 * (lt / hold)   # 정지 순간 펀치 + 배경(1.03)보다 얕은 푸시
  e = 10 + 36 * (1 - ease_out_cubic(clamp(lt / 9)))                                # 에코가 뒤(오른쪽)에서 본체로 수렴
  paste(cv, S["echo_w"], bx + 2 * e, by + e * 0.15, scale=punch, alpha=sa)
  paste(cv, S["echo_r"], bx + e, by + e * 0.08, scale=punch, alpha=sa)
  paste(cv, S["shadow"], bx, by + 16, scale=punch, alpha=sa)
  paste(cv, S["outline"], bx, by, scale=punch, alpha=sa)
  paste(cv, S["sub"], bx, by, scale=punch, alpha=sa)
  cv.alpha_composite(vignette())                                                     # ⑥ 마름모 비네트
