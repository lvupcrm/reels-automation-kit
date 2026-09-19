"""롱테이크·일상 브이로그 타임라인 — 템플릿.
새 릴스를 만들 때 SRC·HDR·CUTS·TARGET_FRAMES만 바꾼다. 아래 값은 예시 구성(48초, 컷 6개)이다.

컷 = C(src, start, n[프레임], speed, crop=(cx,cy,zoom), fit=(cx,cy,zoom,aspect)|None, audio, shake, label)
- 롱테이크는 crop·speed를 건드리지 않는다(기본값 유지). 앵글을 그대로 두는 것이 이 포맷의 핵심이다.
  세로 9:16 소스는 crop 기본값(0.5,0.5,1.0)이 원본 전체 프레임이 된다.
- fit : 가로·4:5 소스를 블러 배경 위에 aspect 비율 프레임으로 얹는다 (브이로그 몽타주 변형에서 쓴다)
- audio : 현장음 볼륨 배수 (슬로모 컷은 기본 0)
- HDR : 아이폰 HLG(arib-std-b67) 소스 키. `ffprobe -show_entries stream=color_transfer`로 소스마다 확인한다.
"""
import os

FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {"A": "../input/clip_a.mov", "B": "../input/clip_b.mov"}
SRC = {k: (v if os.path.isabs(v) else os.path.normpath(os.path.join(HERE, v))) for k, v in SRC.items()}
SRC_LRF = dict(SRC)      # 프리뷰용 프록시(DJI .LRF 등)가 있으면 여기에. 아이폰은 원본으로도 충분히 빠르다
HDR = set()              # 예: {"A", "B"}


def C(src, start, n, speed=1.0, crop=None, fit=None, audio=None, shake=0, label=""):
  if audio is None:
    audio = 0.0 if speed < 1 else 1.0
  return dict(src=src, start=start, n=n, speed=speed, crop=crop or (0.5, 0.5, 1.0), fit=fit,
              audio=audio, shake=shake, label=label)


def section(name, cuts, expect):
  got = sum(c["n"] for c in cuts)
  assert got == expect, f"{name}: {got}f != {expect}f"
  for c in cuts:
    c["section"] = name
  return cuts


TARGET_FRAMES = 1440   # 48초. 레퍼런스 길이에 맞춰 조정 (45~50초가 기본)

# 점프컷은 늘어지는 구간만 덜어낸다 — 4~6회. 컷마다 그 구간에서 벌어지는 일을 label에 적어둔다(자막 근거).
CUTS = []
CUTS += section("OPEN", [C("A", 0.0, 240, label="상황 도입")], 240)
CUTS += section("BUILD", [C("A", 12.0, 240, label="전개")], 240)
CUTS += section("TURN", [C("A", 22.0, 180, label="갈등·변화 시작")], 180)
CUTS += section("RETRY", [C("A", 30.0, 180, label="한 번 더")], 180)
CUTS += section("PEAK", [C("A", 38.0, 162, label="전환점")], 162)
CUTS += section("END", [C("B", 0.0, 438, label="클라이맥스 → 마무리")], 438)


def cut_times():
  out, n = [], 0
  for c in CUTS:
    out.append((n / FPS, (n + c["n"]) / FPS)); n += c["n"]
  return out


def cut_frame_ranges():
  out, n = [], 0
  for c in CUTS:
    out.append((n, n + c["n"])); n += c["n"]
  return out


TOTAL_FRAMES = sum(c["n"] for c in CUTS)
TOTAL_SEC = TOTAL_FRAMES / FPS
CT = cut_times()
assert TOTAL_FRAMES == TARGET_FRAMES, TOTAL_FRAMES

if __name__ == "__main__":
  for i, (c, (f0, f1), (s, e)) in enumerate(zip(CUTS, cut_frame_ranges(), CT)):
    print(f"컷{i+1} f{f0:4d}~{f1:4d} {s:5.2f}~{e:5.2f}s ({c['n']:3d}f) {c['section']:6s} {c['src']} {c['start']:.1f} {c['label']}")
  print(f"총 {TOTAL_FRAMES}f = {TOTAL_SEC:.2f}s, 컷 {len(CUTS)}개")
  miss = [k for k, p in SRC.items() if not os.path.exists(p)]
  if miss:
    print(f"⚠️ 없는 소스: {', '.join(miss)} — SRC 경로를 채운다")
