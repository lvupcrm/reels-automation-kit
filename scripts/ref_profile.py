"""레퍼런스 릴스 자동 계측 — 따라 만들 영상의 편집 규격을 숫자로 뽑는다.

사용:
    python ref_profile.py <레퍼런스.mp4> [--out ref_profile.json]

뽑는 것 (전부 실측 — 눈대중 금지):
  · 장면 전환 시점과 컷 길이 분포
  · 자막 밴드 위치(화면 대비 %)·글자 높이·글자색/외곽선색
  · 타이틀(상단 고정 텍스트) 위치·크기
  · 텍스트 등장 형태(즉시 / 페이드 / 팝)
  · 풀스크린 카드 구간(단색 배경) 시점
  · 나레이션 유무·발화 비율, 효과음으로 보이는 트랜지언트 시각

출력 JSON을 그대로 컷시트·자막 스펙에 옮기면 레퍼와 같은 규격이 된다.
"""
import json
import subprocess
import sys
from collections import Counter

import numpy as np
from PIL import Image

FPS_SAMPLE = 6          # 분석용 샘플링 (초당 프레임)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(src):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v",
             "-show_entries", "stream=width,height", "-show_entries", "format=duration",
             "-of", "json", src])
    d = json.loads(r.stdout)
    st = d["streams"][0]
    return int(st["width"]), int(st["height"]), float(d["format"]["duration"])


def scene_cuts(src):
    """장면 전환 시각(초) — 컷 리듬의 근거."""
    r = run(["ffmpeg", "-v", "error", "-i", src,
             "-vf", "scdet=threshold=12,metadata=mode=print:file=-", "-an", "-f", "null", "-"])
    cuts = []
    for ln in (r.stdout + r.stderr).splitlines():
        if "lavfi.scd.time" in ln:
            try:
                cuts.append(round(float(ln.split("=")[-1]), 2))
            except ValueError:
                pass
    return sorted(set(cuts))


def sample_frames(src, dur, tmp="_rp"):
    """분석용 프레임을 일정 간격으로 뽑는다."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                    "-vf", f"fps={FPS_SAMPLE},scale=540:-2", f"{tmp}_%05d.png"], check=True)
    import glob
    return sorted(glob.glob(f"{tmp}_*.png"))


def text_mask(a):
    """외곽선 있는 텍스트를 잡는다 — 아주 밝은 픽셀 옆에 확연히 어두운 픽셀이 붙어 있는 곳.
    ⚠️ dark 임계를 너무 낮게(<42) 잡으면 '흰 외곽선 + 진한 컬러 글자'(예: 남색 #0E1C54,
       밝기 42)를 통째로 놓친다 — 2026-08 실측. 90이면 검정·남색·진회색 글자를 모두 잡는다."""
    g = a.mean(axis=2)
    bright = g > 232
    dark = g < 90
    nb = np.zeros_like(dark)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
        nb |= np.roll(np.roll(dark, dy, 0), dx, 1)
    return bright & nb


def bands(mask, H, min_rows=6, merge_gap=8):
    """텍스트가 모인 세로 구간(밴드). 간격이 좁은 조각은 한 줄로 병합한다."""
    rows = mask.sum(axis=1)
    thr = max(6, rows.max() * 0.18) if rows.max() else 999
    on = rows > thr
    raw, start = [], None
    for y, v in enumerate(on):
        if v and start is None:
            start = y
        elif not v and start is not None:
            raw.append((start, y - 1)); start = None
    if start is not None:
        raw.append((start, len(on) - 1))
    merged = []
    for b in raw:
        if merged and b[0] - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(list(b) if False else (b[0], b[1]))
            merged[-1] = (b[0], b[1])
    merged = [list(m) for m in merged]
    out = []
    for a, b in merged:
        if b - a + 1 >= min_rows:
            out.append((a, b))
    return out


def text_colors(a, mask):
    """글자 안쪽 색과 외곽선 색 추정 — 밴드 안의 색 분포에서 분리한다."""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return [], []
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    reg = a[y0:y1 + 1, x0:x1 + 1].reshape(-1, 3).astype(int)
    g = reg.mean(axis=1)
    sat = reg.max(axis=1) - reg.min(axis=1)
    fmt = lambda c: "#%02X%02X%02X" % tuple(int(v) for v in c)
    # 외곽선: 아주 밝고 무채색
    out_px = reg[(g > 225) & (sat < 26)]
    # 글자: 어둡거나(검정 계열) 채도가 뚜렷한 색
    ink_px = reg[((g < 150) & (sat < 40)) | (sat >= 45)]
    def top(px, k=3):
        if len(px) == 0:
            return []
        q = (px // 14 * 14)
        cnt = Counter(map(tuple, q))
        return [fmt(c) for c, _ in cnt.most_common(k)]
    return top(ink_px), top(out_px, 2)


def flat_frames(frames):
    """풀스크린 카드(단색 배경) 구간 — 색 분산이 낮은 프레임."""
    out = []
    for i, p in enumerate(frames):
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
        if a.reshape(-1, 3).std(axis=0).mean() < 26:
            out.append(round(i / FPS_SAMPLE, 2))
    return out


def audio_profile(src):
    """발화 비율과 효과음으로 보이는 짧은 트랜지언트."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1",
                    "-ar", "16000", "_rp.wav"], check=True)
    r = run(["ffmpeg", "-v", "info", "-i", "_rp.wav",
             "-af", "silencedetect=noise=-32dB:d=0.20", "-f", "null", "-"])
    sil = []
    for ln in r.stderr.splitlines():
        if "silence_start" in ln:
            sil.append(["s", float(ln.split("silence_start:")[-1])])
        elif "silence_end" in ln:
            sil.append(["e", float(ln.split("silence_end:")[-1].split("|")[0])])
    return sil


def main():
    src = sys.argv[1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "ref_profile.json"
    W, H, dur = probe(src)
    print(f"▶ {src}  {W}x{H}  {dur:.1f}초")

    cuts = scene_cuts(src)
    seg = [round(b - a, 2) for a, b in zip([0] + cuts, cuts + [dur])]
    print(f"▶ 장면 전환 {len(cuts)}회 · 컷 {len(seg)}개 · 중앙값 {np.median(seg):.1f}초")

    frames = sample_frames(src, dur)
    print(f"▶ 분석 프레임 {len(frames)}장")

    band_hits, sizes, inner_c, outer_c = Counter(), [], Counter(), Counter()
    for p in frames:
        a = np.asarray(Image.open(p).convert("RGB"))
        h = a.shape[0]
        m = text_mask(a)
        if m.sum() < 40:
            continue
        for (y0, y1) in bands(m, h):
            band_hits[(round(y0 / h, 2), round(y1 / h, 2))] += 1
            sizes.append((y1 - y0 + 1) / h)
        ic, oc = text_colors(a, m)
        for c in ic:
            inner_c[c] += 1
        for c in oc:
            outer_c[c] += 1

    common = band_hits.most_common(4)
    cards = flat_frames(frames)
    sil = audio_profile(src)
    speech = 1.0 - sum(b - a for (_, a), (_, b) in zip(sil[::2], sil[1::2]) if b > a) / dur \
        if len(sil) >= 2 else None

    prof = {
        "source": src,
        "resolution": [W, H],
        "duration": round(dur, 2),
        "cuts": {"times": cuts, "count": len(seg),
                 "median_len": round(float(np.median(seg)), 2),
                 "min_len": round(float(min(seg)), 2), "max_len": round(float(max(seg)), 2)},
        "text_bands": [{"top_pct": b[0], "bottom_pct": b[1], "frames": n} for b, n in common],
        "glyph_height_pct": round(float(np.median(sizes)) * 100, 1) if sizes else None,
        "glyph_height_max_pct": round(float(np.max(sizes)) * 100, 1) if sizes else None,
        "text_inner_colors": [c for c, _ in inner_c.most_common(3)],
        "text_outline_colors": [c for c, _ in outer_c.most_common(2)],
        "fullscreen_card_times": cards,
        "speech_ratio": round(speech, 2) if speech else None,
    }
    json.dump(prof, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n── 계측 결과 (이 값을 그대로 컷시트·자막 스펙에 옮긴다)")
    print(f"  컷 길이       중앙값 {prof['cuts']['median_len']}초 (최단 {prof['cuts']['min_len']} / 최장 {prof['cuts']['max_len']})")
    for b in prof["text_bands"]:
        print(f"  텍스트 밴드   화면 {b['top_pct']*100:.0f}~{b['bottom_pct']*100:.0f}% ({b['frames']}프레임)")
    print(f"  글자 높이     보통 {prof['glyph_height_pct']}% · 최대 {prof['glyph_height_max_pct']}% (화면 높이 대비)")
    print(f"  글자색        {prof['text_inner_colors']}")
    print(f"  외곽선색      {prof['text_outline_colors']}")
    print(f"  풀스크린 카드 {len(cards)}구간")
    print(f"  발화 비율     {prof['speech_ratio']}")
    print(f"\n→ {out}")
    import glob as _g
    import os as _os
    for _f in _g.glob("_rp_*.png") + ["_rp.wav"]:
        try:
            _os.remove(_f)
        except OSError:
            pass


if __name__ == "__main__":
    main()
