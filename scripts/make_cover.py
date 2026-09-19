"""릴스 커버 생성 — 영상 프레임 + 타이틀 → 1080x1920 커버 PNG (+ 그리드 1:1 미리보기).

스타일 6종 (89편 첫 프레임 전수 분류 기준):
  badge : 상단 배지(수식어) + 대형 타이틀 — 임팩트 타이포 릴스의 기본형
  bar   : 하단 단색 띠 위에 타이틀 — 기사·예측형 커버
  box   : 중앙 반투명 박스 — 사례·후기형 커버
  big   : 풀블리드 대형 타이포 — 한 단어로 때리는 커버
  duo   : 투톤 스택 키워드 — *별표* 단어만 포인트색. **가장 흔한 문법(약 1/4)**
  elegant : 세리프 감성 — 외곽선·그림자 없이 조용하게. 뷰티·카페·공간 계열

사용:
  python make_cover.py badge frame.jpg cover.png --title "이 릴스, AI가 만들었습니다" --eyebrow "릴스 자동화"
  python make_cover.py bar   frame.jpg cover.png --title "2026 마케팅 예측" --color 2E6BFF
  python make_cover.py box   frame.jpg cover.png --title "45분 만에 한 달치 콘텐츠" --sub "실제 과정 공개"
  python make_cover.py big   frame.jpg cover.png --title "자동화"

옵션: --color HEX(포인트색, 기본 EE1E1E) · --font 이름일부(동봉 폰트 교체) · --no-grid(1:1 미리보기 생략)
그리드 세이프존: 인스타 그리드에선 중앙 1:1만 보인다 — 텍스트는 y 480~1440 안에만 배치된다.
"""
import argparse
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
SAFE_TOP, SAFE_BOT = 480, 1440          # 그리드 1:1 크롭 세이프존
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)

_SKILL = Path(__file__).resolve().parent.parent


def find_font(want=""):
    d = _SKILL / "assets" / "fonts"
    cands = []
    if d.is_dir():
        cands = sorted(f for f in d.rglob("*")
                       if f.suffix.lower() in (".otf", ".ttf", ".ttc") and "licenses" not in f.parts)
    want = (want or os.environ.get("REEL_FONT", "")).strip().lower()
    if want:
        for f in cands:
            if want in f.name.lower():
                return str(f), 0
    for key in ("jalnan", "gasoekone"):   # 직접 넣은 잘난체 > 동봉 가석원체
        for f in cands:
            if key in f.name.lower():
                return str(f), 0
    if cands:
        return str(cands[0]), 0
    for path, idx in [("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6),
                      (r"C:\Windows\Fonts\malgunbd.ttf", 0)]:
        if Path(path).exists():
            return path, idx
    raise SystemExit("한글 폰트를 찾을 수 없습니다 — assets/fonts를 확인하세요.")


FONT_PATH, FONT_IDX = None, 0


def font(size):
    return ImageFont.truetype(FONT_PATH, size, index=FONT_IDX)


def _measure(draw, text, size, stroke):
    b = draw.textbbox((0, 0), text, font=font(size), stroke_width=stroke)
    return b[2] - b[0]


def _balance(draw, words, n, size, max_w, stroke):
    """어절을 n줄에 나누는 모든 분할 중 — 전부 폭 안에 들고, 줄 폭이 고르며,
    마지막 줄이 고아(한 단어만 덜렁)가 되지 않는 분할을 고른다."""
    from itertools import combinations
    best, best_score = None, None
    for cuts in combinations(range(1, len(words)), n - 1):
        idx = [0, *cuts, len(words)]
        lines = [" ".join(words[idx[i]:idx[i + 1]]) for i in range(n)]
        ws = [_measure(draw, ln, size, stroke) for ln in lines]
        if max(ws) > max_w:
            continue
        score = max(ws) - min(ws)                     # 들쭉날쭉할수록 벌점
        if n > 1 and min(ws) < max(ws) * 0.45:        # 어느 줄이든 고아(짧은 외톨이) 벌점
            score += max_w
        if best_score is None or score < best_score:
            best, best_score = lines, score
    return best


def wrap(draw, text, size, max_w, stroke=0):
    """명시적 줄바꿈(\\n)은 그대로 존중. 자동 줄바꿈은 **균형 분배** —
    최소 줄 수를 찾은 뒤 그 줄 수 안에서 가장 고른 분할을 고른다 (고아 단어 방지)."""
    lines = []
    for raw in text.split("\\n"):
        words = raw.split()
        if not words:
            continue
        if _measure(draw, raw, size, stroke) <= max_w:
            lines.append(raw)
            continue
        for n in range(2, len(words) + 1):
            got = _balance(draw, words, n, size, max_w, stroke)
            if got:
                lines.extend(got)
                break
        else:
            lines.append(raw)                          # 한 어절이 폭 초과 — fit()이 크기를 줄인다
    return lines


def fit(draw, text, start, max_w, max_h, stroke=0, min_size=54):
    """글자 크기를 훑으며 (줄 수, 크기) 후보를 모은 뒤 —
    최대 크기의 62% 안에서 **줄 수가 가장 적은** 조합을 고른다.
    커버는 줄 수가 적을수록 읽힌다: 큰 글자 5줄보다 조금 작은 글자 2줄이 낫다."""
    accepted = []
    size = start
    while size >= min_size:
        lines = wrap(draw, text, size, max_w, stroke)
        lh = int(size * 1.18)
        if all(_measure(draw, ln, size, stroke) <= max_w for ln in lines) and lh * len(lines) <= max_h:
            accepted.append((len(lines), size, lines, lh))
        size -= 6
    if not accepted:
        lines = wrap(draw, text, min_size, max_w, stroke)
        return lines, min_size, int(min_size * 1.18)
    s_max = max(a[1] for a in accepted)
    pool = [a for a in accepted if a[1] >= s_max * 0.62]
    n_min = min(a[0] for a in pool)
    best = max((a for a in pool if a[0] == n_min), key=lambda a: a[1])
    return best[2], best[1], best[3]


def draw_lines(draw, lines, size, lh, y, fill, stroke=0, stroke_fill=None, cx=W // 2):
    for i, ln in enumerate(lines):
        b = draw.textbbox((0, 0), ln, font=font(size), stroke_width=stroke)
        draw.text((cx - (b[2] - b[0]) // 2 - b[0], y + i * lh - b[1]), ln, font=font(size),
                  fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def load_frame(path):
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H)).convert("RGBA")


def style_badge(base, d, a):
    """상단 빨강 배지 + 대형 타이틀 (세이프존 상단)."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    y = SAFE_TOP + 40
    if a.eyebrow:
        eb_size = 58
        b = od.textbbox((0, 0), a.eyebrow, font=font(eb_size))
        bw, bh = b[2] - b[0] + 84, b[3] - b[1] + 46
        ex = (W - bw) // 2
        od.rounded_rectangle([ex, y, ex + bw, y + bh], radius=bh // 2 - 4, fill=a.rgba)
        od.text((ex + 42 - b[0], y + 23 - b[1]), a.eyebrow, font=font(eb_size), fill=WHITE)
        y += bh + 34
    lines, size, lh = fit(od, a.title, 150, 980, SAFE_BOT - y, stroke=13)
    draw_lines(od, lines, size, lh, y, WHITE, stroke=13, stroke_fill=BLACK)
    base.alpha_composite(shadowed(ov))
    return base


def style_bar(base, d, a):
    """하단 단색 띠 — 세이프존 하단에 걸치게."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    lines, size, lh = fit(od, a.title, 120, 940, 420)
    pad_v = 56
    bar_h = lh * len(lines) + pad_v * 2
    top = SAFE_BOT - bar_h + 60
    od.rectangle([0, top, W, top + bar_h], fill=a.rgba)
    draw_lines(od, lines, size, lh, top + pad_v, WHITE)
    if a.sub:
        s2 = 46
        b = od.textbbox((0, 0), a.sub, font=font(s2))
        od.text(((W - b[2] + b[0]) // 2 - b[0], top - 66 - b[1]), a.sub, font=font(s2),
                fill=WHITE, stroke_width=6, stroke_fill=BLACK)
    base.alpha_composite(ov)
    return base


def style_box(base, d, a):
    """중앙 반투명 박스 + 타이틀(+서브)."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    lines, size, lh = fit(od, a.title, 110, 820, 520)
    sub_h = 96 if a.sub else 0
    bw = max(od.textbbox((0, 0), ln, font=font(size))[2] for ln in lines) + 120
    bw = min(max(bw, 560), 980)
    bh = lh * len(lines) + 96 + sub_h
    bx, by = (W - bw) // 2, (SAFE_TOP + SAFE_BOT - bh) // 2
    od.rounded_rectangle([bx, by, bx + bw, by + bh], radius=28, fill=(12, 14, 18, 208))
    od.rounded_rectangle([bx, by, bx + bw, by + bh], radius=28, outline=a.rgba, width=6)
    draw_lines(od, lines, size, lh, by + 48, WHITE)
    if a.sub:
        s2 = 44
        b = od.textbbox((0, 0), a.sub, font=font(s2))
        od.text(((W - b[2] + b[0]) // 2 - b[0], by + 48 + lh * len(lines) + 26 - b[1]),
                a.sub, font=font(s2), fill=a.rgba)
    base.alpha_composite(shadowed(ov, alpha=0.35))
    return base


def style_big(base, d, a):
    """풀블리드 대형 타이포 — 배경을 어둡게 누르고 글자로 때린다."""
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 96))
    base.alpha_composite(dark)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    lines, size, lh = fit(od, a.title, 300, 1000, SAFE_BOT - SAFE_TOP, stroke=16, min_size=90)
    y = (SAFE_TOP + SAFE_BOT - lh * len(lines)) // 2
    draw_lines(od, lines, size, lh, y, a.rgba, stroke=16, stroke_fill=BLACK)
    base.alpha_composite(shadowed(ov))
    return base


def shadowed(layer, alpha=0.5, blur=9, dx=4, dy=9):
    a = layer.split()[3].point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0)); sh.putalpha(a)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)), (dx, dy))
    out.alpha_composite(layer)
    return out


def style_duo(base, d, a):
    """투톤 스택 키워드 — 88편 첫 프레임에서 가장 흔한 커버 문법 (약 1/4).
    *별표*로 감싼 단어는 포인트색, 나머지는 흰색. 줄은 \\n으로 직접 나누는 걸 권장."""
    base.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 80)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)

    def parse(line):
        return [(w.replace("*", ""), a.rgba if "*" in w else WHITE) for w in line.split()]

    def drawn_w(parts, size):
        """실제로 그려질 폭 — 단어 폭 합 + 단어 간격. 측정과 그리기를 같은 식으로."""
        gap = int(size * 0.22)
        return sum(_measure(od, t, size, 14) for t, _ in parts) + gap * (len(parts) - 1), gap

    clean = a.title.replace("*", "")
    if "\\n" in a.title:
        lines_raw = a.title.split("\\n")
    else:
        _, size0, _ = fit(od, clean, 190, 1000, SAFE_BOT - SAFE_TOP, stroke=14, min_size=80)
        lines_raw = wrap(od, clean, size0, 1000, 14)

    parsed = [parse(ln) for ln in lines_raw if ln.strip()]
    size = 190
    while size > 80:
        lh = int(size * 1.18)
        if all(drawn_w(pt, size)[0] <= 1000 for pt in parsed) and lh * len(parsed) <= SAFE_BOT - SAFE_TOP:
            break
        size -= 6
    lh = int(size * 1.18)

    y = (SAFE_TOP + SAFE_BOT - lh * len(parsed)) // 2
    for i, parts in enumerate(parsed):
        total, gap = drawn_w(parts, size)
        x = (W - total) // 2
        for t, col in parts:
            b = od.textbbox((0, 0), t, font=font(size), stroke_width=14)
            od.text((x - b[0], y + i * lh - b[1]), t, font=font(size),
                    fill=col, stroke_width=14, stroke_fill=BLACK)
            x += (b[2] - b[0]) + gap
    base.alpha_composite(shadowed(ov))
    return base


def style_elegant(base, d, a):
    """세리프 감성형 — 외곽선·그림자 없이 조용하게. 뷰티·카페·공간·감성 계열의 기본 커버.
    (89편 중 약 8%에서 반복 관찰 — 얇은 세리프, 넉넉한 여백, 소문자 느낌의 절제)"""
    global FONT_PATH, FONT_IDX
    if not a.font:                                   # 지정이 없으면 명조 계열로 강제
        FONT_PATH, FONT_IDX = find_font("gowunbatang")
    base.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 110)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)

    lines, size, lh = fit(od, a.title, 104, 860, 460, min_size=58)
    block_h = lh * len(lines)
    eb_h = 110 if a.eyebrow else 0
    y = (SAFE_TOP + SAFE_BOT - block_h - eb_h) // 2

    if a.eyebrow:
        # ⚠️ thin space(U+2009)는 한글 폰트에 글리프가 없어 두부(□)가 된다 — 일반 공백으로 자간을 벌린다
        spaced = " ".join(a.eyebrow.replace(" ", ""))
        b = od.textbbox((0, 0), spaced, font=font(40))
        od.text(((W - b[2] + b[0]) // 2 - b[0], y - b[1]), spaced, font=font(40), fill=(255, 255, 255, 235))
        ry = y + (b[3] - b[1]) + 28                  # 가는 구분선
        od.rectangle([W // 2 - 60, ry, W // 2 + 60, ry + 2], fill=(255, 255, 255, 190))
        y += eb_h

    draw_lines(od, lines, size, lh, y, (255, 255, 255, 250))
    sh = ov.filter(ImageFilter.GaussianBlur(5))      # 스트로크 대신 아주 옅은 소프트 섀도
    sh.putalpha(sh.split()[3].point(lambda v: int(v * 0.22)))
    base.alpha_composite(sh, (0, 3))
    base.alpha_composite(ov)
    return base


STYLES = {"badge": style_badge, "bar": style_bar, "box": style_box,
          "big": style_big, "duo": style_duo, "elegant": style_elegant}


def main():
    global FONT_PATH, FONT_IDX
    ap = argparse.ArgumentParser()
    ap.add_argument("style", choices=list(STYLES))
    ap.add_argument("frame"); ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--eyebrow", default="")
    ap.add_argument("--sub", default="")
    ap.add_argument("--color", default="EE1E1E")
    ap.add_argument("--font", default="")
    ap.add_argument("--no-grid", action="store_true")
    a = ap.parse_args()

    c = a.color.lstrip("#")
    a.rgba = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    FONT_PATH, FONT_IDX = find_font(a.font)
    print(f"[커버] {a.style} · 폰트 {Path(FONT_PATH).name}", file=sys.stderr)

    base = load_frame(a.frame)
    out = STYLES[a.style](base, None, a).convert("RGB")
    out.save(a.out, quality=95)
    if not a.no_grid:
        g = out.crop((0, (H - W) // 2, W, (H - W) // 2 + W))
        gp = str(Path(a.out).with_suffix("")) + "_grid.jpg"
        g.save(gp, quality=90)
        print(gp)
    print(a.out)


if __name__ == "__main__":
    main()
