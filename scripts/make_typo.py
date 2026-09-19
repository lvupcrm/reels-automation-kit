"""릴스 타이포 렌더 — 레퍼런스 픽셀 대조로 검증된 최종 스타일 (2026-08-19 v3.8).
폰트: assets/fonts에서 자동 선택 — 기본은 가석원체(Gasoek One). 잘난체를 직접 받아 넣으면 최우선.
스펙(레퍼런스 픽셀 재추출값): 수식 = 빨강 필 #FC0000 + 흰 글자 / 메인 = 박스 없음, 흰 글자 + 근검정 외곽선
#140D08 4px(얇게) + 강한 드롭섀도 / 강조 오버레이 = 노랑 #FCED00 + 검정 외곽선 (보조 = 흰 + 검정 외곽선)
최종 mp4에서 노랑을 재면 #FFDE00쯤으로 읽힌다 — yuv420p 크로마 서브샘플링 탓이지 설정 오류가 아니다.

사용:
  python make_typo.py title "수식 문구" "메인 타이틀" title.png    # 1080x480(2줄이면 더 길다), overlay=0:227
      메인이 한 줄에 안 들어가면(대략 4어절 이상) 자동으로 2줄로 나눈다 — 줄이기만 하면 양끝이 잘린다.
      직접 나누려면 메인 문구에 \n 을 넣는다.
  python make_typo.py overlay "보조 문구" "강조 문구" ov.png       # 1080x1920 투명, overlay=0:0
"""
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 잘난체가 없으면 OS 기본 한글 폰트로 폴백한다 — 폰트 없이도 릴스를 뽑을 수 있게.
# (경로, 컬렉션 index, 단어간격 배율) — 잘난체는 공백 글리프가 없어 배율 1.0, 일반 폰트는 좁힌다.
_FALLBACKS = [
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6, "Apple SD Gothic Neo Bold"),   # macOS
    (r"C:\Windows\Fonts\malgunbd.ttf", 0, "맑은 고딕 Bold"),                          # Windows
    (r"C:\Windows\Fonts\malgun.ttf", 0, "맑은 고딕"),                                 # Windows(볼드 없을 때)
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 0, "Noto Sans CJK Bold"),  # Linux
]
_SKILL = Path(__file__).resolve().parent.parent          # …/reel

def _from_assets():
    """assets/fonts를 하위 폴더까지 뒤져 폰트를 찾는다 (카테고리 폴더 구조 지원).
    기본은 가석원체(gasoekone). 잘난체를 직접 받아 넣었다면 그것을 최우선. REEL_FONT=이름일부 로 교체 가능."""
    d = _SKILL / "assets" / "fonts"
    if not d.is_dir():
        return None
    cands = sorted(f for f in d.rglob("*")
                   if f.suffix.lower() in (".otf", ".ttf", ".ttc")
                   and "licenses" not in f.parts)
    if not cands:
        return None
    want = os.environ.get("REEL_FONT", "").strip()
    if want:
        for f in cands:
            if want.lower() in f.name.lower():
                return f
    for key in ("jalnan", "gasoekone"):   # 직접 넣은 잘난체 > 동봉 가석원체
        for f in cands:
            if key in f.name.lower():
                return f
    return cands[0]

_asset_font = _from_assets()
if _asset_font:
    # 단어를 따로 그려 붙이므로 간격은 배율로 준다 — 잘난체는 검증된 넓은 간격(1.0), 일반 폰트는 좁힌다
    FONT, FONT_INDEX, GAP_RATIO = str(_asset_font), 0, (1.0 if "jalnan" in _asset_font.name.lower() else 0.5)
    print(f"[알림] assets/fonts의 {_asset_font.name}로 렌더합니다.", file=sys.stderr)
else:
    for _path, _idx, _label in _FALLBACKS:
        if Path(_path).exists():
            FONT, FONT_INDEX, GAP_RATIO = _path, _idx, 0.45
            print(f"[알림] assets/fonts가 비어 있어 {_label}로 렌더합니다.", file=sys.stderr)
            break
    else:
        raise SystemExit("한글 폰트를 찾을 수 없습니다 — assets/fonts를 확인하세요.")

def load_font(size):
    return ImageFont.truetype(FONT, size, index=FONT_INDEX)

WHITE = (255, 255, 255, 255); RED = (252, 0, 0, 255); OUTLINE = (20, 13, 8, 255)
YELLOW = (252, 237, 0, 255); BLACK = (0, 0, 0, 255)

def spaced_size(d, words, font, gap, stroke=0):
    tw = h = 0
    for w in words:
        b = d.textbbox((0, 0), w, font=font, stroke_width=stroke)
        tw += b[2]-b[0]; h = max(h, b[3]-b[1])
    return tw + gap*(len(words)-1), h

def draw_spaced(d, x, y, words, font, gap, fill, stroke=0, stroke_fill=None):
    for w in words:
        b = d.textbbox((0, 0), w, font=font, stroke_width=stroke)
        d.text((x - b[0], y - b[1]), w, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += (b[2]-b[0]) + gap

def with_shadow(cv, alpha=0.5, blur=7, dx=4, dy=9):
    a = cv.split()[3].point(lambda v: int(v*alpha))
    sh = Image.new("RGBA", cv.size, (0, 0, 0, 0)); sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", cv.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (dx, dy)); out.alpha_composite(cv)
    return out

def _fit(d, lines, start, floor, stroke):
    """모든 줄이 폭 985 안에 들어가는 가장 큰 크기."""
    size = start
    while True:
        f = load_font(size); gap = int(size*0.22*GAP_RATIO)
        dims = [spaced_size(d, ln, f, gap, stroke) for ln in lines]
        if max(w for w, _ in dims) <= 985 or size <= floor:
            return f, gap, dims
        size -= 4


def _split2(words):
    """글자수가 가장 고르게 갈리는 어절 경계에서 두 줄로."""
    best = min(range(1, len(words)), key=lambda k: abs(len("".join(words[:k])) - len("".join(words[k:]))))
    return [words[:best], words[best:]]


def title(eyebrow_txt, main_txt, out):
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    STROKE = 4
    if "\\n" in main_txt or "\n" in main_txt:
        lines = [ln.split() for ln in main_txt.replace("\\n", "\n").split("\n") if ln.strip()]
    else:
        lines = [main_txt.split()]
    f_main, gap, dims = _fit(probe, lines, 170, 120 if len(lines) == 1 and len(lines[0]) > 1 else 90, STROKE)
    if len(lines) == 1 and dims[0][0] > 985 and len(lines[0]) > 1:
        lines = _split2(lines[0])
        f_main, gap, dims = _fit(probe, lines, 150, 80, STROKE)
    eb_words = eyebrow_txt.split(); f_eb = load_font(55); egap = max(int(17*GAP_RATIO), 14)
    ew, eh = spaced_size(probe, eb_words, f_eb, egap)
    ebw, ebh = int(ew)+76, eh+42
    ebx, eby = (1080-ebw)//2, 30
    lead = int(max(h for _, h in dims) * 1.22)
    height = max(480, eby + ebh + 26 + lead * len(lines) + 40)
    cv = Image.new("RGBA", (1080, height), (0, 0, 0, 0)); d = ImageDraw.Draw(cv)
    d.rounded_rectangle([ebx, eby, ebx+ebw, eby+ebh], radius=int(ebh/2)-6, fill=RED)
    draw_spaced(d, ebx+38, eby+21, eb_words, f_eb, egap, WHITE)
    y = eby + ebh + 26
    for ln, (mw, _) in zip(lines, dims):
        draw_spaced(d, (1080-int(mw))//2, y, ln, f_main, gap, WHITE, STROKE, OUTLINE)
        y += lead
    with_shadow(cv, alpha=0.78, blur=10, dx=5, dy=12).save(out)
    if len(lines) > 1:
        print(f"[알림] 메인 타이틀을 {len(lines)}줄로 나눴습니다: " + " / ".join(" ".join(ln) for ln in lines), file=sys.stderr)

def overlay(sub_txt, key_txt, out):
    cv = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); d = ImageDraw.Draw(cv)
    for txt, fsize, fill, sw, y in ((sub_txt, 52, WHITE, 6, 660), (key_txt, 118, YELLOW, 11, 760)):
        ws = txt.split(); f = load_font(fsize); g = int(fsize*0.26*GAP_RATIO)
        w, _ = spaced_size(d, ws, f, g, sw)
        draw_spaced(d, (1080-int(w))//2, y, ws, f, g, fill, sw, BLACK)
    with_shadow(cv, alpha=0.4, blur=5, dx=3, dy=6).save(out)

mode = sys.argv[1]
(title if mode == "title" else overlay)(sys.argv[2], sys.argv[3], sys.argv[4])
print(sys.argv[4])
