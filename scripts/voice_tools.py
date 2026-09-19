"""음성 QA 도구 — 귀로만 판단하던 것을 숫자로 잰다 (numpy·soundfile만 쓴다).

  python voice_tools.py qa <레퍼런스.wav> <청크.wav> ...
      클론 나레이션 청크 검수. 청크마다 피크·RMS·음색 거리(멜 LTAS)를 재서 재생성 후보를 표시한다.
      - 음색 드리프트: 특정 청크만 "다른 사람 목소리"처럼 들린다. 피치(F0)로는 안 잡힌다.
        레퍼런스 실제 목소리와의 멜 LTAS 거리로 고른다 — 같은 목소리 클론 3~6(짧은 청크일수록 큼) / 다른 사람 8 이상.
        3.5 이하면 채택, 3.5~6은 귀로 확인, 6 초과는 재생성. 3초 미만 청크는 값이 부풀려진다 — 문장을 합쳐 다시 재면 떨어진다.
        ⚠️ "다른 청크들의 평균에 가까운 테이크"를 고르면 실패한다(출력 전체가 조금씩 드리프트한다).
        부분 교체 때는 레퍼런스 자리에 **그 릴스의 승인된 나레이션**을 넣어야 척도가 맞는다.
      - 먹히는 청크: "목소리가 묻힌다"의 원인은 음량(RMS)이 아니라 다이내믹이다. 피크가 다른 청크보다
        낮고 평탄한 청크(예: 0.47 vs 정상 0.52~0.66)만 골라 재생성한다.
  python voice_tools.py f0 <녹음.wav> <시작-끝> [<시작-끝> ...]
      구간별 기본주파수(F0) 중앙값 — 녹음 속 화자 구분. 전사 도구의 화자 라벨은 믿지 않는다
      (전원 한 화자로 뭉쳐 나오거나 내용으로 추론해 반대로 붙인다). 애매하면 샘플을 잘라 사람에게 들려준다.
  python voice_tools.py cut <파일.wav> <초> [--win 0.3]
      그 시각 ±win 안에서 20ms RMS가 가장 낮은 지점 — 앞 어절 잔음 없이 자르는 자리.
      whisper 단어 경계는 수십 ms씩 틀린다. 무음 딥이 안 보이면(이어 붙어 발음) 자르지 말고 재생성한다.
  python voice_tools.py pace <파일.wav> <음절수>
      발화 구간 기준 음절/초. 교체 문장의 atempo는 배속값을 복사하지 말고 원본 슬롯과 이 값이 같아지게 정한다.
"""
import sys

import numpy as np
import soundfile as sf


def load(path, t0=None, t1=None):
  x, sr = sf.read(path, dtype="float32", always_2d=True)
  x = x.mean(axis=1)
  if t0 is not None:
    x = x[int(t0 * sr):int(t1 * sr) if t1 else None]
  return x, sr


def frames(x, sr, win=0.025, hop=0.010):
  n, h = int(sr * win), int(sr * hop)
  if len(x) < n:
    x = np.pad(x, (0, n - len(x)))
  idx = np.arange(0, len(x) - n + 1, h)
  return np.stack([x[i:i + n] for i in idx]), h


def mel_fb(sr, nfft, nb=26, fmax=8000):
  hz2m = lambda f: 2595 * np.log10(1 + f / 700)
  m2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
  pts = m2hz(np.linspace(hz2m(60), hz2m(min(fmax, sr / 2)), nb + 2))
  bins = np.floor((nfft + 1) * pts / sr).astype(int)
  fb = np.zeros((nb, nfft // 2 + 1))
  for i in range(nb):
    a, b, c = bins[i], bins[i + 1], bins[i + 2]
    for k in range(a, b):
      fb[i, k] = (k - a) / max(1, b - a)
    for k in range(b, c):
      fb[i, k] = (c - k) / max(1, c - b)
  return fb


def ltas(path, t0=None, t1=None):
  """유성 프레임(에너지 상위 60%)의 평균 로그 멜 스펙트럼 − 자기 평균(CMN) → 26차 벡터(자연로그)."""
  x, sr = load(path, t0, t1)
  F, _ = frames(x, sr)
  nfft = 1 << (F.shape[1] - 1).bit_length()
  spec = np.abs(np.fft.rfft(F * np.hanning(F.shape[1]), nfft)) ** 2
  mel = np.log(spec @ mel_fb(sr, nfft).T + 1e-10)
  e = mel.mean(axis=1)
  v = mel[e >= np.percentile(e, 40)].mean(axis=0)
  return v - v.mean()


def cmd_qa(ref, chunks):
  r = ltas(ref)
  half = sf.info(ref).duration / 2
  base = float(np.linalg.norm(ltas(ref, 0, half) - ltas(ref, half, None)))
  print(f"기준선: 레퍼런스 앞·뒤 절반끼리 거리 {base:.2f} — 같은 사람 같은 녹음의 흔들림 폭")
  rows = []
  for c in chunks:
    x, _ = load(c)
    rows.append((c, float(np.abs(x).max()), float(np.sqrt((x ** 2).mean())), float(np.linalg.norm(ltas(c) - r)),
                 len(x) / sf.info(c).samplerate))
  med_peak = float(np.median([row[1] for row in rows]))
  print(f"{'청크':32s} {'피크':>6s} {'RMS':>6s} {'음색거리':>8s}  판정")
  for c, p, rms, d, dur in rows:
    flags = []
    if d > 3.5:
      flags.append("음색 드리프트 의심 → 재생성" if d > 6 else "경계 — 귀로 확인" + (" (짧은 청크라 값이 큼)" if dur < 3 else ""))
    if p < med_peak * 0.88:
      flags.append("피크 낮음(먹힘) → 재생성")
    print(f"{c[-32:]:32s} {p:6.3f} {rms:6.3f} {d:8.2f}  {' · '.join(flags) or '통과'}")


def f0_track(x, sr, fmin=70, fmax=400):
  F, _ = frames(x, sr, win=0.04, hop=0.01)
  lo, hi = int(sr / fmax), int(sr / fmin)
  out = []
  for f in F:
    f = f - f.mean()
    if np.sqrt((f ** 2).mean()) < 0.01:
      continue
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    if ac[0] <= 0:
      continue
    ac = ac / ac[0]
    seg = ac[lo:hi]
    best = int(np.argmax(seg))
    if seg[best] < 0.45:
      continue
    # 옥타브 보정: 절반 주기(두 배 주파수)에도 강한 피크가 있으면 그쪽이 실제 기본주파수다
    half = (best + lo) // 2
    if half >= lo and ac[half] > 0.85 * seg[best]:
      best = half - lo
    out.append(sr / (best + lo))
  return np.array(out)


def cmd_f0(path, spans):
  for sp in spans:
    a, b = (float(v) for v in sp.split("-"))
    x, sr = load(path, a, b)
    f = f0_track(x, sr)
    if len(f) < 5:
      print(f"  {sp:>13s}  유성 구간 부족")
      continue
    print(f"  {sp:>13s}  F0 중앙 {np.median(f):6.1f}Hz  (25~75% {np.percentile(f, 25):.0f}~{np.percentile(f, 75):.0f}, 프레임 {len(f)})")
  print("  → 구간끼리 중앙값이 30Hz 이상 벌어지면 다른 화자일 가능성이 높다. 성별이 같으면 겹칠 수 있다 — 그땐 들어서 확정.")


def rms_curve(x, sr, win=0.02):
  n = int(sr * win)
  k = len(x) // n
  return np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(axis=1)), n


def cmd_cut(path, t, win):
  x, sr = load(path)
  r, n = rms_curve(x, sr)
  i0, i1 = max(0, int((t - win) * sr / n)), min(len(r), int((t + win) * sr / n) + 1)
  i = i0 + int(np.argmin(r[i0:i1]))
  med = float(np.median(r[r > 0])) if (r > 0).any() else 1.0
  depth = float(r[i]) / med
  print(f"  자를 자리 {i * n / sr:.3f}s (RMS {r[i]:.4f}, 중앙값 대비 {depth:.2f})")
  if depth > 0.25:
    print("  ⚠️ 무음 딥이 얕다 — 앞뒤 어절이 이어 붙어 있다. 자르면 음절이 상한다 → 문장을 바꿔 재생성한다.")


def cmd_pace(path, syl):
  x, sr = load(path)
  r, n = rms_curve(x, sr)
  voiced = (r > max(0.01, 0.15 * float(np.percentile(r, 95)))).sum() * n / sr
  print(f"  발화 {voiced:.2f}s · {syl}음절 → {syl / voiced:.2f} 음절/초")


if __name__ == "__main__":
  a = sys.argv[1:]
  if not a or a[0] not in ("qa", "f0", "cut", "pace"):
    sys.exit(__doc__)
  if a[0] == "qa":
    cmd_qa(a[1], a[2:])
  elif a[0] == "f0":
    cmd_f0(a[1], a[2:])
  elif a[0] == "cut":
    cmd_cut(a[1], float(a[2]), float(a[a.index("--win") + 1]) if "--win" in a else 0.3)
  else:
    cmd_pace(a[1], int(a[2]))
