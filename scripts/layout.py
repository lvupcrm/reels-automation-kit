"""릴스 레이아웃 그리드 — 1080x1920 기준. 오버레이 좌표는 이 상수만 참조한다.

요소마다 좌표를 따로 쓰면 정렬이 어긋나고 "CTA만 그림자가 빠지는" 식의 누락이 생긴다.

인스타 릴스 UI가 가리는 영역
  하단 y>1580 : 캡션·계정명·음원 표시
  우측 x>900  : 좋아요·댓글·공유 버튼 (하단 절반)
  상단 y<170  : 상태바·탭

검수 (눈대중 금지 — 축소 이미지에 가이드를 얹으면 착시로 오판한다):
  python layout.py check overlay.png [...]     # 투명 PNG의 글자 픽셀이 UI 가림 영역에 들어갔는지 알파로 잰다
                                               (알파 128 이상만 센다 — 반투명 어둠 띠·그림자는 가려져도 괜찮다)
"""
import sys

W, H = 1080, 1920
SAFE_L, SAFE_R = 72, 1008          # 좌우 여백
SAFE_T, SAFE_B = 190, 1560         # 상하 안전선
UI_BOTTOM, UI_RIGHT_X, UI_TOP = 1580, 900, 170
CENTER = W // 2

# 인물 편 (배경이 인물·실사)
SUB_Y = 1120                       # 자막 중심 — 화면 중앙보다 조금 아래(≈58%)
CTA_Y = 1448                       # 하단 CTA 중심 — 1500 위를 지킨다(1690에 뒀다가 캡션에 가릴 뻔했다)

# 화면 전용 편 (배경을 화면 카드가 대신함) — 인물 편 좌표를 그대로 쓰면 하단 절반이 빈다
CARD_X, CARD_Y, CARD_W, CARD_H = 50, 360, 980, 1010
LABEL_Y, LABEL_EN_Y = 228, 306     # 카드 위 라벨(번호+한글) · 영문 병기
SUB_Y_SCREEN = 1450                # 카드가 커져 자막을 카드 아래로 — 하단 1494로 UI선 안쪽


def margin_v(center_y, glyph_h=64):
  """ASS MarginV(Alignment 2) = 1920 - (자막 중심 y + 글자높이/2). 84px 폰트면 glyph_h≈60."""
  return int(H - (center_y + glyph_h / 2))


def check(paths, thr=128):
  from PIL import Image
  bad = 0
  for p in paths:
    a = Image.open(p).convert("RGBA").split()[3]
    if a.size != (W, H):
      print(f"  ? {p}: {a.size} — 1080x1920 오버레이만 검사한다"); continue
    px = a.load()
    cover = sum(1 for y in range(0, H, 16) for x in range(0, W, 16) if px[x, y] > thr) / ((H // 16) * (W // 16))
    if cover > 0.9:
      print(f"  · {p}: 화면 전체를 덮는 레이어(디밍·플래시) — 검사 생략"); continue
    zones = {"하단 캡션(y>1580)": (0, UI_BOTTOM, W, H), "우측 버튼(x>900, y>960)": (UI_RIGHT_X, 960, W, UI_BOTTOM),
             "상단 상태바(y<170)": (0, 0, W, UI_TOP)}
    hits = []
    for name, (x0, y0, x1, y1) in zones.items():
      n = sum(1 for y in range(y0, y1, 2) for x in range(x0, x1, 2) if px[x, y] > thr)
      if n:
        hits.append(f"{name} {n * 4}px")
    print(("  ✘ " if hits else "  ✔ ") + p + ("  → " + " · ".join(hits) if hits else ""))
    bad += bool(hits)
  return bad


if __name__ == "__main__":
  if len(sys.argv) > 2 and sys.argv[1] == "check":
    sys.exit(1 if check(sys.argv[2:]) else 0)
  print(__doc__)
