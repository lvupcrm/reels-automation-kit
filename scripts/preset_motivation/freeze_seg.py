"""프리즈 오프너 — 인물 누끼 분리 (u2net human seg, 정지 프레임 1장만 추론).

원본 기법의 얼린 화면은 [뭉갠 배경] 위에 [잘라낸 피사체]를 다시 얹어 입체감을 만든다.
배경을 블러하는 이유가 누끼를 띄우기 위해서이므로, 누끼가 있을 때만 배경을 뭉갠다.

산출: freeze/opener_bg.png   — 뭉갠 배경 (ffmpeg 컷 입력)
      freeze/opener_sub.png  — 누끼 피사체 RGBA (오버레이에서 패널 위에 얹음)
사용: python3 freeze_seg.py
"""
import os
import sys

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageEnhance, ImageFilter
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import FREEZE, FREEZE_PNG, FREEZE_STILL, FREEZE_SUB  # noqa: E402

MODEL = os.path.expanduser("~/.u2net/u2net_human_seg.onnx")   # U-2-Net 사람 분할(Apache-2.0) — onnxruntime 으로 직접 돌린다
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"
MODEL_MD5 = "c09ddc2e0104f800e3e1bb4652583d1f"   # 176MB, 첫 실행 때 한 번만 받는다
SRC, BG_OUT, SUB_OUT = FREEZE_STILL, FREEZE_PNG, FREEZE_SUB

BG_TINT = (28, 34, 48)   # 차가운 남색 — 빨강 패널과 살구빛 피부를 동시에 띄운다
BG_BLUR = 22
BG_ZOOM = 1.04           # 배경을 살짝만 밀어 인물과 분리 — 크게 밀면 블러 잔상이 인물에서 어긋난다

def _ensure_model():
  if os.path.exists(MODEL) and os.path.getsize(MODEL) > 100_000_000:
    return
  import hashlib
  import urllib.request
  os.makedirs(os.path.dirname(MODEL), exist_ok=True)
  print("누끼 모델(176MB)을 처음 한 번 내려받습니다…", flush=True)
  tmp = MODEL + ".part"
  urllib.request.urlretrieve(MODEL_URL, tmp)
  h = hashlib.md5()
  with open(tmp, "rb") as fh:
    for b in iter(lambda: fh.read(1 << 20), b""):
      h.update(b)
  if h.hexdigest() != MODEL_MD5:
    os.remove(tmp)
    sys.exit("누끼 모델 다운로드가 손상됐습니다 — 다시 실행하세요")
  os.replace(tmp, MODEL)


def _sess():
  _ensure_model()
  s = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
  return s, s.get_inputs()[0].name, s.get_outputs()[0].name

def _raw(sess, iname, oname, im):
  x = np.asarray(im.convert("RGB").resize((320, 320), Image.LANCZOS), np.float32)
  x = x / max(x.max(), 1e-6)
  x = (x - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
  d = sess.run([oname], {iname: x.transpose(2, 0, 1)[None]})[0][0, 0]
  return (d - d.min()) / max(d.max() - d.min(), 1e-6)

def mask(im, overlap=0.35):
  """전체뷰 1회 + 세로 정사각 타일 추론을 합친다. 전체뷰는 원경 인물을, 타일은 가까운 인물의 윤곽을 살린다."""
  sess, iname, oname = _sess()
  W, H = im.size
  full = np.asarray(Image.fromarray((_raw(sess, iname, oname, im) * 255).astype(np.uint8))
                    .resize((W, H), Image.LANCZOS), np.float32) / 255
  step = int(W * (1 - overlap))
  ys = list(range(0, max(1, H - W + 1), step))
  if ys[-1] != H - W:
    ys.append(H - W)
  acc = np.zeros((H, W), np.float32)
  wgt = np.zeros((H, W), np.float32)
  r = np.minimum(np.arange(W), np.arange(W)[::-1]).astype(np.float32)
  ramp = (r / r.max() * 0.9 + 0.1)[:, None]
  for y in ys:
    m = _raw(sess, iname, oname, im.crop((0, y, W, y + W)))
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((W, W), Image.LANCZOS), np.float32) / 255
    acc[y:y + W] += m * ramp
    wgt[y:y + W] += ramp
  return np.maximum(acc / np.maximum(wgt, 1e-6), full * 0.9)

def drop_blurred_blobs(im, m, min_px=4000, min_focus=5.0, rel=0.6):
  """초점이 안 맞는 덩어리(카메라 앞을 스쳐간 흐린 전경)를 통째로 제거한다.
  픽셀 단위로 자르면 검은 옷처럼 평탄한 면에 구멍이 나므로 연결 성분 단위로 판정한다.
  기준은 '가장 선명한 덩어리의 rel배'와 min_focus 중 낮은 쪽 — 절대값만 쓰면 부드러운 소스(업스케일·1080p)에서
  주인공까지 통째로 지워진다."""
  g = im.convert("L")
  a = np.asarray(g, np.float32)
  hi = np.abs(a - np.asarray(g.filter(ImageFilter.GaussianBlur(3)), np.float32))
  focus = np.asarray(Image.fromarray(hi.astype(np.uint8)).filter(ImageFilter.GaussianBlur(45)), np.float32)
  er = ndi.binary_erosion(m > 0.45, np.ones((9, 9)))
  lab, n = ndi.label(er)
  if n == 0:
    return m
  idx = range(1, n + 1)
  sizes = ndi.sum(np.ones_like(lab), lab, idx)
  mf = ndi.mean(focus, lab, idx)
  big = [mf[i] for i in range(n) if sizes[i] > min_px]
  thr = min(min_focus, rel * max(big)) if big else min_focus
  keep = np.zeros(n + 1, bool)
  for i in range(n):
    keep[i + 1] = sizes[i] > min_px and mf[i] >= thr
  sel = ndi.binary_dilation(keep[lab], np.ones((13, 13)))
  return m * sel

def drop_corner_fragments(m, zone=(0.28, 0.75), erode=15, inside=0.80):
  """카메라 앞을 스쳐간 전경이 들어온 구석(왼쪽 아래)에 고립된 작은 조각을 뗀다.
  강하게 침식해 본체와 떼어낸 뒤, 픽셀의 80% 이상이 구석 안에 있는 성분만 제거 — 본체·다리는 구석 밖이라 안전."""
  H, W = m.shape
  ys, xs = np.mgrid[0:H, 0:W]
  corner = (xs < W * zone[0]) & (ys > H * zone[1])
  lab, n = ndi.label(ndi.binary_erosion(m > 0.45, np.ones((erode, erode))))
  if n == 0:
    return m
  idx = range(1, n + 1)
  sizes = ndi.sum(np.ones_like(lab), lab, idx)
  incorner = ndi.sum(corner, lab, idx)
  drop = np.zeros(n + 1, bool)
  for i in range(n):
    drop[i + 1] = sizes[i] > 0 and incorner[i] / sizes[i] >= inside
  if not drop.any():
    return m
  return m * ~ndi.binary_dilation(drop[lab], np.ones((erode + 6, erode + 6)))

def build():
  if not FREEZE:
    sys.exit("timeline.FREEZE 가 비어 있다 — 프리즈 오프너를 쓰려면 먼저 채운다")
  im = Image.open(SRC).convert("RGB")
  W, H = im.size
  a = drop_corner_fragments(drop_blurred_blobs(im, mask(im)))
  am = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
  am = am.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2.5))

  bg = ImageEnhance.Color(im).enhance(0.30)
  bg = Image.blend(bg, Image.new("RGB", (W, H), BG_TINT), 0.28)
  bg = ImageEnhance.Brightness(bg).enhance(0.93).filter(ImageFilter.GaussianBlur(BG_BLUR))
  zw, zh = int(W * BG_ZOOM), int(H * BG_ZOOM)
  bg = bg.resize((zw, zh), Image.LANCZOS).crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
  bg.save(BG_OUT)

  sub = im.filter(ImageFilter.UnsharpMask(radius=3, percent=85, threshold=3))
  sub = ImageEnhance.Contrast(sub).enhance(1.10).convert("RGBA")
  sub.putalpha(am)
  sub.save(SUB_OUT)
  # 눈 검수용: 왼쪽 원본 · 오른쪽 초록 바탕 위 누끼 — 손에 든 물건·바닥까지 딸려오면 다른 프레임을 고른다
  pv = Image.new("RGB", (W // 2, H // 4), (0, 150, 0))
  pv.paste(im.resize((W // 4, H // 4)), (0, 0))
  small = sub.resize((W // 4, H // 4))
  pv.paste(small, (W // 4, 0), small)
  pv.save(os.path.join(os.path.dirname(SUB_OUT), "mask_preview.jpg"), quality=85)
  cov = (np.asarray(am, float) / 255 > 0.5).mean() * 100
  print(f"배경 → {BG_OUT}\n누끼 → {SUB_OUT}  (커버리지 {cov:.1f}%)")
  if cov < 3:
    print("⚠️ 정지 프레임에서 사람이 거의 안 잡혔다 — 누끼 층 없이 진행된다. 인물이 크게 나온 컷으로\n"
          "   timeline.FREEZE['src_cut'] 을 바꾸고(직전 컷도 같이) freeze_card.py 부터 다시 돌린다.")
  elif cov > 55:
    print("⚠️ 화면 대부분이 누끼로 잡혔다 — 바닥·소품이 딸려왔을 수 있다. freeze/mask_preview.jpg 를 눈으로 보고,\n"
          "   지저분하면 전신이 보이는 와이드 컷으로 src_cut 을 바꾼다(가까운 클로즈업일수록 소품까지 사람으로 잡힌다).")

if __name__ == "__main__":
  build()
