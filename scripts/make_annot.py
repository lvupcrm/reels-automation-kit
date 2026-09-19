"""주석 그래픽 → 1080x1920 투명 PNG (overlay=0:0 용).

자료 화면에서 "어디를 보라"고 짚어주는 장치. 설명형·사례형 릴스에서 기사·앱 화면 위에 얹는다.
좌표는 1080x1920 캔버스 기준이며, 원점은 왼쪽 위다.

사용:
  python make_annot.py arrow  out.png --from 300,500 --to 620,760
  python make_annot.py circle out.png --at 540,900 --size 420,240
  python make_annot.py box    out.png --at 540,700 --size 700,180
  python make_annot.py line   out.png --at 540,1100 --size 560,0      # 밑줄

여러 개 얹기 — 같은 파일에 --add 로 덧그린다:
  python make_annot.py circle out.png --at 540,700 --size 400,220
  python make_annot.py arrow  out.png --from 200,1150 --to 470,850 --add

옵션:
  --color   HEX (기본 EE1E1E 빨강). 브랜드 색을 쓰려면 여기에 지정
  --width   선 두께 px (기본 화면 비례 12)
  --bow     화살표 휘는 정도 -1.0~1.0 (기본 0.28, 0이면 직선)
  --add     기존 파일 위에 덧그리기
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

CANVAS = (1080, 1920)


def hex2rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def pair(s):
    x, y = s.split(",")
    return int(x), int(y)


def bezier(p0, p1, p2, steps=64):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def base(out, add):
    if add and Path(out).exists():
        im = Image.open(out).convert("RGBA")
        if im.size != CANVAS:
            im = im.resize(CANVAS, Image.LANCZOS)
        return im
    return Image.new("RGBA", CANVAS, (0, 0, 0, 0))


def with_shadow(layer, alpha=0.38, blur=7, dx=3, dy=5):
    """자료 화면 위에 얹어도 묻히지 않게 옅은 그림자를 깐다."""
    a = layer.split()[3].point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (dx, dy))
    out.alpha_composite(layer)
    return out


def draw_arrow(dr, p_from, p_to, color, w, bow):
    # 시작→끝의 수직 방향으로 제어점을 밀어 곡선을 만든다
    mx, my = (p_from[0] + p_to[0]) / 2, (p_from[1] + p_to[1]) / 2
    dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
    ctrl = (mx - dy * bow, my + dx * bow)
    pts = bezier(p_from, ctrl, p_to)

    # 촉이 앉을 자리를 비워두고 몸통을 그린다
    head = max(w * 3.2, 32)
    body = pts[:-4] if len(pts) > 8 else pts
    dr.line(body, fill=color, width=w, joint="curve")

    # 화살촉 — 끝 직전 방향을 따라 삼각형
    ax, ay = pts[-1]
    bx, by = pts[-7] if len(pts) > 8 else pts[0]
    vx, vy = ax - bx, ay - by
    n = (vx * vx + vy * vy) ** 0.5 or 1
    vx, vy = vx / n, vy / n
    px, py = -vy, vx
    dr.polygon([(ax, ay),
                (ax - vx * head + px * head * 0.52, ay - vy * head + py * head * 0.52),
                (ax - vx * head - px * head * 0.52, ay - vy * head - py * head * 0.52)],
               fill=color)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shape", choices=["arrow", "circle", "box", "line"])
    ap.add_argument("out")
    ap.add_argument("--from", dest="p_from", type=pair)
    ap.add_argument("--to", dest="p_to", type=pair)
    ap.add_argument("--at", type=pair)
    ap.add_argument("--size", type=pair)
    ap.add_argument("--color", default="EE1E1E")
    ap.add_argument("--width", type=int, default=12)
    ap.add_argument("--bow", type=float, default=0.28)
    ap.add_argument("--add", action="store_true")
    a = ap.parse_args()

    color = hex2rgba(a.color)
    w = max(3, a.width)
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)

    if a.shape == "arrow":
        if not (a.p_from and a.p_to):
            raise SystemExit("arrow 는 --from 과 --to 가 필요합니다")
        draw_arrow(dr, a.p_from, a.p_to, color, w, a.bow)

    elif a.shape in ("circle", "box"):
        if not (a.at and a.size):
            raise SystemExit(f"{a.shape} 는 --at 과 --size 가 필요합니다")
        cx, cy = a.at; bw, bh = a.size
        box = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
        if a.shape == "circle":
            dr.ellipse(box, outline=color, width=w)
        else:
            dr.rounded_rectangle(box, radius=max(8, w * 2), outline=color, width=w)

    else:  # line — 밑줄
        if not (a.at and a.size):
            raise SystemExit("line 은 --at 과 --size 가 필요합니다")
        cx, cy = a.at; lw, _ = a.size
        dr.line([(cx - lw // 2, cy), (cx + lw // 2, cy)], fill=color, width=w)

    canvas = base(a.out, a.add)
    canvas.alpha_composite(with_shadow(layer))
    canvas.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
