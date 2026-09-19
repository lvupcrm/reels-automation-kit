"""카라오케 자막 — 말하는 단어를 따라 색이 차오르는 ASS (\\k 태그) + 강조어 시각 추출.

사용: python karaoke_subs.py <audio.wav> <phrases.txt> [--accent FCED00] [--out reel_subs_k.ass]
  - phrases.txt: 구 단위 문구(줄당 ≤16자). *별표* 강조어의 발화 시각을 accents.json으로 내보낸다
    → fx.punch(times)에 넣으면 "강조어 자동 펀치인"과 동기화된다.
  - 스타일: Pretendard 84 · 검정 박스(BorderStyle 4) · 흰 글자가 강조색으로 차오름.
  합성: ass=reel_subs_k.ass:fontsdir=_fonts   (Pretendard를 작업 폴더 _fonts/ 에 모아둔다 — assets/fonts 를 직접 주면
        libass가 하위 폴더를 안 뒤져 시스템 고딕으로 바뀐다)
"""
import json
import os
import re
import sys

_pos = [a for a in sys.argv[1:] if not a.startswith("--")]
AUDIO = _pos[0] if _pos else "reel_narration.wav"
PHRASES = _pos[1] if len(_pos) > 1 else sys.exit("phrases.txt가 필요합니다")
ACCENT = "FCED00"
OUT = "reel_subs_k.ass"
for _i, _a in enumerate(sys.argv):
    if _a == "--accent" and _i + 1 < len(sys.argv): ACCENT = sys.argv[_i + 1].lstrip("#")
    if _a == "--out" and _i + 1 < len(sys.argv): OUT = sys.argv[_i + 1]
ACC_ASS = ACCENT[4:6] + ACCENT[2:4] + ACCENT[0:2]


def transcribe_words(audio):
    """맥은 mlx_whisper, 그 외는 faster_whisper (make_subs와 동일 폴백)."""
    try:
        import mlx_whisper
        r = mlx_whisper.transcribe(audio, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                   language="ko", word_timestamps=True)
        return [{"t": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
                for seg in r["segments"] for w in seg.get("words", []) if w["word"].strip()]
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("자막 엔진이 없습니다 — mlx-whisper(맥) 또는 faster-whisper(윈도우)를 설치하세요.")
    model = WhisperModel("turbo", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, language="ko", word_timestamps=True)
    return [{"t": w.word.strip(), "s": w.start, "e": w.end}
            for seg in segments for w in (seg.words or []) if w.word.strip()]


def norm_len(text):
    return len(re.sub(r"[\s.,!?~…·'\"()\[\]{}<>%*-]", "", text))


words = transcribe_words(AUDIO)
raw = [ln for ln in open(PHRASES, encoding="utf-8").read().splitlines() if ln.strip()]
lines, wi = [], 0
for row in raw:
    text = row.split("|", 1)[0].strip()
    need, got, ws = norm_len(text), 0, []
    while wi < len(words) and got < need:
        ws.append(words[wi]); got += norm_len(words[wi]["t"]); wi += 1
    if not ws:
        continue
    accents = []
    for m in re.finditer(r"\*(.+?)\*", text):
        core = re.sub(r"[\s.,!?~…·'\"()\[\]{}<>%*-]", "", m.group(1))
        for w in ws:
            if core and core[0] in w["t"]:
                accents.append(round(w["s"], 2)); break
    lines.append({"text": re.sub(r"\*", "", text), "ws": ws,
                  "s": ws[0]["s"], "e": ws[-1]["e"] + 0.15, "accents": accents})
for i, ln in enumerate(lines):
    if i + 1 < len(lines):
        ln["e"] = lines[i + 1]["s"]


def ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Pretendard,84,&H00{ACC_ASS},&H00FFFFFF,&H50000000,&H70000000,-1,0,0,0,100,100,0,0,4,16,0,2,60,60,568,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

events = []
for ln in lines:
    toks = ln["text"].split()
    total = ln["ws"][-1]["e"] - ln["ws"][0]["s"]
    if len(toks) == len(ln["ws"]):
        durs = [max(w["e"] - w["s"], 0.08) for w in ln["ws"]]
    else:
        durs = [total / max(len(toks), 1)] * len(toks)
    body = "".join("{\\k" + str(max(int(round(d * 100)), 8)) + "}" + t + " " for t, d in zip(toks, durs))
    events.append(f"Dialogue: 0,{ts(ln['s'])},{ts(ln['e'])},Sub,,0,0,0,,{body.rstrip()}")

open(OUT, "w", encoding="utf-8").write(HEAD + "\n".join(events) + "\n")
acc = sorted({a for ln in lines for a in ln["accents"]})
json.dump({"accents": acc, "end": lines[-1]["e"]}, open("accents.json", "w"))
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reel_assets import font_path, fontsdir
    fontsdir(font_path("pretendard"))
except SystemExit:
    pass
print(f"✔ {OUT} ({len(lines)}줄) · 강조어 시각 → accents.json {acc} · 합성: ass={OUT}:fontsdir=_fonts")
