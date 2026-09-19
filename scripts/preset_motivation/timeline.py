"""모티베이션 몽타주 타임라인 — 템플릿 (비트 그리드 14f = 128.6 BPM, 16마디 = 896f = 29.87초).

실제 센터 현장 촬영본(그룹 운동 클립 11개)으로 검증된 구조다. 새 릴스를 만들 때는
**SRC·HDR·CUTS만 바꾼다** — 마디 구조(section 합계)는 assert가 지키므로 건드리지 않는다.

컷 = C(src, start, n[프레임], speed, crop=(cx, cy, zoom)|None, bump, shake, whip_in, whip_out, label)
- crop : 소스에서 (cx,cy) 중심(0~1 비율)으로 9:16 창의 1/zoom 영역을 잘라 1080x1920으로 — 펀치인 클로즈업.
         해상도와 무관하다(4K든 1080p든 같은 값). zoom ≤1.6이면 4K 세로 소스는 업스케일 없이 선명하다.
         ⚠️ (cx,cy)는 썸네일 눈대중으로 잡으면 절반쯤 빗나간다 — 그리드 프레임으로 실측한다(preset-motivation.md).
- bump : 비트마다 줌 펀치 / shake: 흔들림 진폭(px) / whip_*: 컷 경계 휩 블러 프레임 수
- freeze: 스틸 PNG — 주면 영상 대신 그 한 장을 n프레임 홀드 (프리즈 오프너, 아래 FREEZE)
"""
import os

FPS = 30
BEAT = 14           # 프레임/비트 (128.57 BPM)
BAR = BEAT * 4      # 56f = 1.867s
HERE = os.path.dirname(os.path.abspath(__file__))

# 소스 — 키는 짧게, 경로는 이 폴더 기준 상대경로 또는 절대경로
SRC = {
  "A": "../input/clip_a.mp4",
  "B": "../input/clip_b.mp4",
  "C": "../input/clip_c.mp4",
  "D": "../input/clip_d.mp4",
  "E": "../input/clip_e.mp4",
  "F": "../input/clip_f.mp4",
}
SRC = {k: (v if os.path.isabs(v) else os.path.normpath(os.path.join(HERE, v))) for k, v in SRC.items()}
# 아이폰 HLG(arib-std-b67) 소스 키 — ffprobe -show_entries stream=color_transfer 로 소스마다 확인한다.
# 같은 날 찍은 파일도 섞여 있다(3개 중 2개만 HLG였던 적이 있다). 넣으면 렌더 시 bt709로 톤매핑한다.
HDR = set()


def C(src, start, n, speed=1.0, crop=None, bump=True, shake=0, whip_in=0, whip_out=0, label="", freeze=None):
  return dict(src=src, start=start, n=n, speed=speed, crop=crop, bump=bump, shake=shake,
              whip_in=whip_in, whip_out=whip_out, label=label, freeze=freeze)


def section(name, cuts, expect):
  got = sum(c["n"] for c in cuts)
  assert got == expect, f"{name}: {got}f != {expect}f"
  return cuts


# ── 프리즈 오프너 (기본 켜짐) ─────────────────────────────────────────
# 영상 재생 → 순간 정지(얼린 스틸 위에 망점·집중선·패널·타이포·누끼) → 같은 샷 이어재생.
# 순서: freeze_card.py → freeze_seg.py → mg_overlay.py → build_master.py (문구·위치는 freeze_fx.py 상단)
#   f0/n    정지 시작 프레임·길이 — 마디 머리에 맞추면 비트와 맞아떨어진다
#   src_cut 얼릴 직전 컷과 '완전히 같은' 파라미터 — freeze_card.py 가 이 컷의 마지막 프레임을 뽑아 이음매를 없앤다
# 끄려면 FREEZE = None — INTRO 가 조용한 3컷(보드 → 얼굴 슬로모 → 발)으로 바뀐다.
FREEZE = dict(f0=56, n=42, src_cut=dict(src="B", start=2.3, n=28, crop=(0.50, 0.78, 1.60)))
FREEZE_STILL = os.path.join(HERE, "freeze", "opener.png")      # 원본 정지 프레임 (freeze_card.py 산출)
FREEZE_PNG = os.path.join(HERE, "freeze", "opener_bg.png")     # 뭉갠 배경 = 컷 입력 (freeze_seg.py 산출)
FREEZE_SUB = os.path.join(HERE, "freeze", "opener_sub.png")    # 누끼 피사체 RGBA (freeze_seg.py 산출)

CUTS = []
if FREEZE:
  # 마디 1~2 INTRO 프리즈판: 분위기 컷 → 주인공 컷 → [정지 n f] → 같은 샷 이어재생 (합계 2마디)
  _fc = FREEZE["src_cut"]
  CUTS += section("INTRO", [
    C("A", 0.6, 28, 1.0, (0.50, 0.42, 1.35), bump=False, label="분위기 컷 (보드·장비·공간)"),
    C(_fc["src"], _fc["start"], _fc["n"], 1.0, _fc["crop"], bump=False, whip_out=2, label="주인공 컷 (프리즈 직전)"),
    C(_fc["src"], 0, FREEZE["n"], 1.0, None, bump=False, freeze=FREEZE_PNG, label="★ 프리즈 오프너"),
    C(_fc["src"], _fc["start"] + _fc["n"] / FPS, 2 * BAR - 28 - _fc["n"] - FREEZE["n"], 1.0, _fc["crop"],
      bump=False, label="주인공 컷 이어재생 (프리즈 해제)"),
  ], 2 * BAR)
else:
  CUTS += section("INTRO", [
    C("A", 0.6, 56, 1.0, (0.50, 0.42, 1.35), bump=False, label="분위기 컷"),
    C("A", 8.9, 28, 0.5, (0.38, 0.76, 1.30), bump=False, label="눈 마주침 슬로모"),
    C("B", 2.3, 28, 1.0, (0.50, 0.78, 1.60), bump=False, label="발·손 클로즈업"),
  ], 2 * BAR)
# 마디 3~4 BUILD — 2비트마다 컷
CUTS += section("BUILD", [
  C("C", 0.5, 28, 1.2, (0.42, 0.50, 1.30), label="동작 1"),
  C("D", 0.3, 28, 1.2, (0.30, 0.60, 1.45), label="동작 2"),
  C("E", 9.0, 28, 1.0, (0.35, 0.80, 1.50), label="정면 동작"),
  C("F", 0.8, 28, 1.2, (0.18, 0.60, 1.60), label="동작 3"),
], 2 * BAR)
# 마디 5 DROP — 1비트 플리커(2f×7) → 홀드 3비트 + 흔들림
CUTS += section("DROP", [
  C("B", 4.00, 2, 1.0, (0.30, 0.42, 1.60), bump=False, label="플리커 얼굴"),
  C("A", 0.20, 2, 1.0, (0.55, 0.40, 1.20), bump=False, label="플리커 미소"),
  C("C", 0.15, 2, 1.0, (0.50, 0.50, 1.30), bump=False, label="플리커 점프"),
  C("B", 4.10, 2, 1.0, (0.30, 0.42, 1.60), bump=False, label="플리커 얼굴"),
  C("D", 4.90, 2, 1.0, (0.45, 0.55, 1.20), bump=False, label="플리커 동작"),
  C("A", 0.30, 2, 1.0, (0.55, 0.40, 1.20), bump=False, label="플리커 미소"),
  C("E", 9.30, 2, 1.0, (0.38, 0.80, 1.50), bump=False, label="플리커 정면"),
  C("E", 9.35, 42, 1.15, (0.40, 0.80, 1.45), shake=8, whip_out=3, label="드롭 홀드 (가장 힘 있는 컷)"),
], BAR)
# 마디 6~8 MONTAGE 1 — 비트마다 컷
CUTS += section("MONTAGE1", [
  C("B", 4.6, 14, 1.3, (0.50, 0.50, 1.30), whip_in=2, label="측면"),
  C("C", 2.2, 14, 1.2, (0.40, 0.50, 1.40), label="동작"),
  C("D", 1.2, 14, 1.4, (0.45, 0.50, 1.30), label="동작"),
  C("E", 2.9, 14, 1.2, (0.50, 0.50, 1.50), label="동작"),
  C("F", 0.0, 28, 1.2, (0.50, 0.50, 1.30), whip_out=3, label="점프"),
  C("A", 1.9, 14, 1.2, (0.50, 0.62, 1.60), whip_in=2, label="동작"),
  C("C", 10.0, 14, 1.2, (0.50, 0.60, 1.40), label="와이드"),
  C("D", 1.0, 14, 1.2, (0.50, 0.50, 1.30), label="후면"),
  C("B", 6.0, 28, 1.2, (0.35, 0.45, 1.50), shake=5, whip_out=3, label="클로즈"),
  C("E", 8.3, 14, 1.0, (0.40, 0.45, 1.50), whip_in=2, label="클로즈"),
], 3 * BAR)
# 마디 9~10 HERO — 슬로모 2컷
CUTS += section("HERO", [
  C("D", 4.4, 60, 0.5, (0.45, 0.55, 1.20), bump=False, label="히어로 슬로모 1"),
  C("E", 8.6, 52, 0.5, (0.30, 0.82, 1.30), bump=False, label="히어로 슬로모 2"),
], 2 * BAR)
# 마디 11 MONTAGE 2 — 반비트 컷 + 휩
CUTS += section("MONTAGE2", [
  C("A", 1.8, 7, 1.3, (0.70, 0.55, 1.40), whip_in=1, whip_out=1, label="반비트"),
  C("B", 5.0, 7, 1.3, (0.50, 0.50, 1.30), whip_in=1, whip_out=1, label="반비트"),
  C("C", 13.6, 7, 1.2, (0.60, 0.55, 1.40), whip_in=1, whip_out=1, label="반비트"),
  C("D", 1.8, 7, 1.4, (0.45, 0.50, 1.30), whip_in=1, whip_out=1, label="반비트"),
  C("E", 3.2, 7, 1.2, (0.50, 0.50, 1.50), whip_in=1, whip_out=1, label="반비트"),
  C("F", 2.8, 7, 1.2, (0.40, 0.50, 1.40), whip_in=1, whip_out=1, label="반비트"),
  C("A", 2.3, 7, 1.2, (0.50, 0.62, 1.60), whip_in=1, whip_out=1, label="반비트"),
  C("E", 10.6, 7, 1.2, (0.45, 0.80, 1.50), whip_in=1, whip_out=1, label="반비트"),
], BAR)
# 마디 12 CLIMAX — 휩 3컷 + 플리커 1비트
CUTS += section("CLIMAX", [
  C("C", 3.0, 14, 1.2, (0.22, 0.62, 1.70), shake=8, whip_in=3, whip_out=3, label="클라이맥스 1"),
  C("B", 6.5, 14, 1.2, (0.35, 0.45, 1.50), shake=8, whip_in=3, whip_out=3, label="클라이맥스 2"),
  C("D", 2.0, 14, 1.3, (0.45, 0.50, 1.30), shake=8, whip_in=3, whip_out=3, label="클라이맥스 3"),
  C("F", 0.40, 2, 1.0, (0.50, 0.50, 1.30), bump=False, label="플리커"),
  C("E", 9.60, 2, 1.0, (0.40, 0.80, 1.50), bump=False, label="플리커"),
  C("B", 4.20, 2, 1.0, (0.30, 0.42, 1.60), bump=False, label="플리커"),
  C("A", 0.40, 2, 1.0, (0.55, 0.40, 1.20), bump=False, label="플리커"),
  C("D", 5.00, 2, 1.0, (0.45, 0.55, 1.20), bump=False, label="플리커"),
  C("C", 3.00, 2, 1.0, (0.40, 0.50, 1.40), bump=False, label="플리커"),
  C("F", 1.20, 2, 1.0, (0.18, 0.60, 1.60), bump=False, label="플리커"),
], BAR)
# 마디 13~14 RESOLVE — 웃는 얼굴 슬로모 → 걸어옴
CUTS += section("RESOLVE", [
  C("A", 0.0, 84, 0.5, (0.55, 0.42, 1.15), bump=False, label="웃는 얼굴 슬로모"),
  C("F", 10.0, 28, 0.8, (0.50, 0.55, 1.15), bump=False, label="함께 걸어옴"),
], 2 * BAR)
# 마디 15~16 OUTRO — 와이드 팬 + 로고 범퍼
CUTS += section("OUTRO", [
  C("C", 4.0, 56, 0.9, None, bump=False, label="와이드 팬"),
  C("C", 5.7, 56, 0.7, None, bump=False, label="와이드 슬로모 — 로고"),
], 2 * BAR)


def cut_times():
  out, n = [], 0
  for c in CUTS:
    out.append((n / FPS, (n + c["n"]) / FPS)); n += c["n"]
  return out


TOTAL_FRAMES = sum(c["n"] for c in CUTS)
TOTAL_SEC = TOTAL_FRAMES / FPS
CT = cut_times()
assert TOTAL_FRAMES == 16 * BAR, TOTAL_FRAMES
if FREEZE:
  _f = 0
  for _c in CUTS:
    if _c["freeze"]:
      assert _f == FREEZE["f0"], f"프리즈 컷 시작 f{_f} != FREEZE.f0 {FREEZE['f0']}"
      break
    _f += _c["n"]


def src_time(t):
  for c, (s, e) in zip(CUTS, CT):
    if s <= t < e:
      return c, c["start"] + (t - s) * c["speed"]
  c = CUTS[-1]
  return c, c["start"] + c["n"] * c["speed"] / FPS - 0.01


def bar_t(k):
  """k마디 시작 시각(초) — 오버레이 타이밍용 (0-based)."""
  return k * BAR / FPS


if __name__ == "__main__":
  miss = [k for k, p in SRC.items() if not os.path.exists(p)]
  for i, (c, (s, e)) in enumerate(zip(CUTS, CT)):
    print(f"컷{i+1:2d} {s:6.3f}~{e:6.3f}s ({c['n']:3d}f) {c['src']} {c['start']:.2f} x{c['speed']} crop={c['crop']} {c['label']}")
  print(f"총 {TOTAL_FRAMES}f = {TOTAL_SEC:.2f}s, 컷 {len(CUTS)}개")
  if miss:
    print(f"⚠️ 없는 소스: {', '.join(miss)} — SRC 경로를 채운다")
