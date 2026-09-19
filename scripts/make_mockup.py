"""스크린샷 → 아이폰 목업 → 1080x1920 투명 PNG (overlay=0:0 용).

앱 화면을 그냥 얹으면 "스크린샷을 붙였구나"로 보이지만,
목업 프레임 안에 넣으면 "실제로 쓰는 화면"으로 읽힌다. 설명형·사례형 릴스의 기본 연출.

사용:
  python make_mockup.py shot.png out.png                    # 기본: 화면 폭 640, 세로 중앙
  python make_mockup.py shot.png out.png --w 720 --y 420    # 크기·위치 지정
  python make_mockup.py shot.png out.png --tilt -6          # 살짝 기울이기
  python make_mockup.py shot.png out.png --no-shadow

옵션:
  --w      목업 화면 폭 px (기본 640)
  --x/--y  캔버스 안 목업 중심 좌표 (기본 540 / 960)
  --tilt   기울기 각도 (기본 0)
  --crop   top|center|bottom — 스크린샷이 목업보다 길 때 어디를 남길지 (기본 top)
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

CANVAS = (1080, 1920)
ASPECT = 19.5 / 9          # 아이폰 화면 비율
BODY = (42, 44, 48, 255)   # 프레임 본체
EDGE = (96, 100, 108, 255) # 테두리 하이라이트
ISLAND = (12, 12, 14, 255) # 다이나믹 아일랜드


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def fit_screenshot(img, size, crop="top"):
    """스크린샷을 목업 화면 비율에 맞춰 채운다(비율 유지, 넘치는 쪽을 자름)."""
    tw, th = size
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    new = img.resize((max(1, round(sw * scale)), max(1, round(sh * scale))), Image.LANCZOS)
    nw, nh = new.size
    left = (nw - tw) // 2
    if crop == "top":
        top = 0
    elif crop == "bottom":
        top = nh - th
    else:
        top = (nh - th) // 2
    return new.crop((left, top, left + tw, top + th))


def build(shot_path, out_path, w=640, cx=540, cy=960, tilt=0.0, crop="top", shadow=True):
    sw = int(w)
    sh = int(round(sw * ASPECT))
    bezel = max(8, round(sw * 0.023))          # 베젤 두께
    r_screen = round(sw * 0.115)               # 화면 코너
    r_body = r_screen + bezel

    body_size = (sw + bezel * 2, sh + bezel * 2)
    device = Image.new("RGBA", body_size, (0, 0, 0, 0))
    d = ImageDraw.Draw(device)

    # 본체 + 테두리 하이라이트(금속 느낌)
    d.rounded_rectangle([0, 0, body_size[0] - 1, body_size[1] - 1], radius=r_body, fill=BODY)
    d.rounded_rectangle([0, 0, body_size[0] - 1, body_size[1] - 1], radius=r_body,
                        outline=EDGE, width=max(2, bezel // 4))

    # 화면
    shot = Image.open(shot_path).convert("RGB")
    screen = fit_screenshot(shot, (sw, sh), crop).convert("RGBA")
    screen.putalpha(rounded_mask((sw, sh), r_screen))
    device.paste(screen, (bezel, bezel), screen)

    # 다이나믹 아일랜드 — 화면 위 알약
    iw, ih = round(sw * 0.30), round(sh * 0.022)
    ix = bezel + (sw - iw) // 2
    iy = bezel + round(sh * 0.014)
    d.rounded_rectangle([ix, iy, ix + iw, iy + ih], radius=ih // 2, fill=ISLAND)

    if tilt:
        device = device.rotate(tilt, resample=Image.BICUBIC, expand=True)

    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    px = int(cx) - device.size[0] // 2
    py = int(cy) - device.size[1] // 2

    if shadow:
        sh_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        alpha = device.split()[3].point(lambda v: int(v * 0.45))
        blob = Image.new("RGBA", device.size, (0, 0, 0, 0))
        blob.putalpha(alpha)
        sh_layer.paste(blob, (px + round(sw * 0.02), py + round(sw * 0.05)), blob)
        canvas.alpha_composite(sh_layer.filter(ImageFilter.GaussianBlur(round(sw * 0.045))))

    canvas.alpha_composite(device, (px, py))
    canvas.save(out_path)
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("shot"); ap.add_argument("out")
    ap.add_argument("--w", type=int, default=640)
    ap.add_argument("--x", type=int, default=540)
    ap.add_argument("--y", type=int, default=960)
    ap.add_argument("--tilt", type=float, default=0.0)
    ap.add_argument("--crop", choices=["top", "center", "bottom"], default="top")
    ap.add_argument("--no-shadow", action="store_true")
    a = ap.parse_args()
    if not Path(a.shot).exists():
        raise SystemExit(f"스크린샷을 찾을 수 없습니다: {a.shot}")
    print(build(a.shot, a.out, a.w, a.x, a.y, a.tilt, a.crop, not a.no_shadow))
