"""오디오 → whisper 단어 타임스탬프 → ASS 자막(reel_subs.ass) + 줄별 타임라인(reel_lines.json).

사용:
  python make_subs.py [audio.wav] [phrases.txt] [--accent FCED00] [--pos bottom|center] [--words words.json]
  - phrases.txt에서 *별표*로 감싼 단어는 강조색으로 렌더된다 (88편 자막 문법)
  - audio 기본값: reel_narration.wav
  - phrases.txt: 구 단위 문구 리스트(한 줄 = 자막 한 줄, 각 ≤16자, 의미 단위로 미리 쪼갬).
    있으면 글자수 소진 방식으로 문구에 단어 타임스탬프를 정렬(정본 — 글자수 그룹핑 금지 피드백).
    없으면 글자수 그룹핑 폴백(전사문 초안 확인용으로만).

  - --words: 재전사 대신 이미 가진 단어 시각을 쓴다 ([{"t","s","e"}] — word_subs.py words/map 산출).
    배속 오디오는 whisper가 끝을 놓치고, 점프컷 오디오는 "18번"↔"열여덟 번" 같은 표기 차이로 어긋난다 —
    원본 단어 시각을 컷 타임라인으로 옮겨 넣는 편이 정확하다.

합성 시: ass=reel_subs.ass:fontsdir=_fonts
  ⚠️ fontsdir 에 assets/fonts 를 직접 주면 안 된다 — libass는 하위 폴더를 뒤지지 않아 오류 없이 시스템 고딕으로
     바뀐다. 이 스크립트가 쓴 폰트를 작업 폴더 _fonts/ 에 모아두므로 그 폴더를 준다.
"""
import json
import os
import platform
import re
import sys
from pathlib import Path

ACCENT = "FCED00"; POS = "bottom"; STYLE = "standard"; ANIM = "none"; WORDS = None
EMPH_SCALE = 1.0      # 강조 단어 확대 배수 — 숏폼 문법은 3~4배(레퍼 실측)
BASE_SIZE = 84        # Sub 스타일 기준 크기 (스케일 계산용)
for _i, _a in enumerate(sys.argv):
    if _a == "--accent" and _i + 1 < len(sys.argv): ACCENT = sys.argv[_i + 1].lstrip("#")
    if _a == "--pos" and _i + 1 < len(sys.argv): POS = sys.argv[_i + 1]
    if _a == "--style" and _i + 1 < len(sys.argv): STYLE = sys.argv[_i + 1]
    if _a == "--emph-scale" and _i + 1 < len(sys.argv): EMPH_SCALE = float(sys.argv[_i + 1])
    if _a == "--size" and _i + 1 < len(sys.argv): BASE_SIZE = int(sys.argv[_i + 1])
    if _a == "--anim" and _i + 1 < len(sys.argv): ANIM = sys.argv[_i + 1]   # fade = 줄마다 부드럽게 뜨고 진다
    if _a == "--words" and _i + 1 < len(sys.argv): WORDS = sys.argv[_i + 1]
_pos = [a for i, a in enumerate(sys.argv[1:], 1)
        if not a.startswith("--") and not sys.argv[i - 1].startswith("--")]
AUDIO = _pos[0] if len(_pos) > 0 else "reel_narration.wav"
PHRASES = _pos[1] if len(_pos) > 1 else None
ACCENT_ASS = ACCENT[4:6] + ACCENT[2:4] + ACCENT[0:2]   # ASS 색은 BGR 순서
MAX_CHARS = 14          # 폴백 모드: 한 자막 줄 최대 글자수
GAP_BREAK = 0.55        # 폴백 모드: 이 이상 쉬면 줄 분리


def norm_len(text):
    """공백·문장부호 제외 글자수 — 정렬 소진 기준."""
    return len(re.sub(r"[\s.,!?~…·'\"()\[\]{}<>%*-]", "", text))


def transcribe_words(audio):
    """오디오 → [{"t","s","e"}]. 맥은 mlx_whisper, 그 외(윈도우·리눅스)는 faster_whisper."""
    try:
        import mlx_whisper
        r = mlx_whisper.transcribe(
            audio, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            language="ko", word_timestamps=True,
        )
        return [{"t": w["word"].strip(), "s": w["start"], "e": w["end"]}
                for seg in r["segments"] for w in seg.get("words", [])]
    except ImportError:
        pass

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("자막 엔진이 없습니다 — mlx-whisper(맥) 또는 faster-whisper(윈도우)를 설치하세요.")

    # GPU가 있으면 쓰고, 없으면 CPU int8 (윈도우 노트북 기준 실사용 가능한 속도)
    device, compute = "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "float16"
    except Exception:
        pass
    print(f"[자막] faster-whisper ({device}/{compute})", file=sys.stderr)
    model = WhisperModel("turbo", device=device, compute_type=compute)
    segments, _ = model.transcribe(audio, language="ko", word_timestamps=True)
    out = []
    for seg in segments:
        for w in (seg.words or []):
            out.append({"t": w.word.strip(), "s": w.start, "e": w.end})
    return out


def audio_duration(path):
    try:
        import soundfile as sf
        return sf.info(path).duration
    except Exception:
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True)
        return float(r.stdout.strip() or 0) or None


DUR = audio_duration(AUDIO) if os.path.exists(AUDIO) else None
words = json.load(open(WORDS, encoding="utf-8")) if WORDS else transcribe_words(AUDIO)
if not words:
    sys.exit("전사 결과가 비어 있습니다 — 오디오를 확인하세요.")

lines = []
if PHRASES:
    # 키네틱용 확장 문법 — "텍스트 | pos=x,y size=1.8 an=4" / 빈 줄 = 블록 경계(블록은 화면에 누적된다)
    raw_rows = open(PHRASES, encoding="utf-8").read().splitlines()
    entries, block = [], 0
    for row in raw_rows:
        if not row.strip():
            if entries: block += 1
            continue
        text, *dpart = row.split("|", 1)
        dirs = {}
        if dpart:
            for tok in dpart[0].split():
                if "=" in tok:
                    k, v = tok.split("=", 1); dirs[k] = v
        entries.append({"text": text.strip(), "dirs": dirs, "block": block})
    phrases = [e["text"] for e in entries]
    total_phrase = sum(norm_len(p) for p in phrases)
    total_words = sum(norm_len(w["t"]) for w in words)
    if abs(total_phrase - total_words) > max(4, total_words * 0.15):
        print(f"⚠️ 글자수 불일치: phrases {total_phrase} vs whisper {total_words} — 전사 검증 필요")
    # ⚠️ 자막은 실제 발화와 같아야 한다 — 전사에 없는 문구는 즉시 알린다
    spoken = re.sub(r"[\s.,!?~…·'\"()\[\]{}<>%*-]", "", "".join(w["t"] for w in words))
    ghosts = []
    for p_ in phrases:
        core = re.sub(r"[\s.,!?~…·'\"()\[\]{}<>%*-]", "", p_)
        if len(core) >= 2 and core not in spoken:
            ghosts.append(p_)
    if ghosts:
        print("⚠️ 발화에 없는 자막 문구 — 음성과 어긋납니다:", file=sys.stderr)
        for g_ in ghosts:
            print(f"     · {g_}", file=sys.stderr)
        print("   (대본에 실제로 있는 표현으로 바꾸세요)", file=sys.stderr)
    wi = 0
    for p in phrases:
        need = norm_len(p)
        got = 0
        s = e = None
        while wi < len(words) and (got < need or s is None):
            w = words[wi]
            if s is None:
                s = w["s"]
            e = w["e"]
            got += norm_len(w["t"])
            wi += 1
        lines.append({"text": p, "s": s if s is not None else (lines[-1]["e"] if lines else 0), "e": e or 0})
    if wi < len(words):
        print(f"⚠️ 남은 단어 {len(words)-wi}개 — 마지막 문구에 흡수")
        lines[-1]["e"] = words[-1]["e"]
else:
    cur = None
    for w in words:
        if cur is None:
            cur = {"text": w["t"], "s": w["s"], "e": w["e"]}
            continue
        if (w["s"] - cur["e"] > GAP_BREAK) or (len(cur["text"]) + 1 + len(w["t"]) > MAX_CHARS):
            lines.append(cur)
            cur = {"text": w["t"], "s": w["s"], "e": w["e"]}
        else:
            cur["text"] += " " + w["t"]
            cur["e"] = w["e"]
    if cur:
        lines.append(cur)

# 표준: 다음 줄 시작까지 유지 / 키네틱: 같은 블록 줄들은 화면에 누적 — 블록 끝까지 유지
if STYLE == "kinetic" and PHRASES:
    for i, ln in enumerate(lines):
        ln["dirs"] = entries[i]["dirs"]; ln["block"] = entries[i]["block"]
    n_blocks = max(e["block"] for e in entries) + 1
    for b in range(n_blocks):
        idx = [i for i, ln in enumerate(lines) if ln["block"] == b]
        nxt = [ln["s"] for ln in lines if ln["block"] == b + 1]
        b_end = nxt[0] if nxt else lines[idx[-1]]["e"] + 0.8
        for i in idx:
            lines[i]["e"] = b_end
else:
    for i, ln in enumerate(lines):
        ln["e"] = lines[i + 1]["s"] if i + 1 < len(lines) else ln["e"] + 0.6

# 끝 시각 클램프 — 배속 오디오는 마지막 단어 시각이 0으로 깨지거나, +0.6 여유가 영상 길이를 넘어 잘린다
if DUR:
    for ln in lines:
        ln["s"] = min(ln["s"], DUR - 0.3)
        if not ln["e"] or ln["e"] <= ln["s"] or ln["e"] > DUR:
            ln["e"] = DUR


def ts(sec):
    h = int(sec // 3600); m = int(sec % 3600 // 60); s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# 워터마크(상단 브랜드 텍스트) 넣지 않는다 — 2026-08-19 사용자 피드백
def pick_font():
    """자막 폰트 결정 — 기본은 동봉 가석원체. 잘난체를 직접 받아 넣었다면 최우선, 없으면 OS 기본 폴백.
    ⚠️ ASS의 Fontname은 파일명이 아니라 폰트 내부 이름이다.
    libass는 fontsdir로 지정한 폴더에서 폰트를 찾으므로, 폴백 시 해당 ttf를 작업 폴더에 복사해 둘 것."""
    # assets/fonts에 폰트가 있으면 그 이름을 쓴다 (ASS Fontname = 폰트 내부 이름)
    fdir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    if fdir.is_dir():
        cands = sorted(f for f in fdir.rglob("*")
                       if f.suffix.lower() in (".otf", ".ttf", ".ttc")
                       and "licenses" not in f.parts)
        want = os.environ.get("REEL_FONT", "").strip().lower()

        def _rank(f):   # REEL_FONT 지정 > 직접 넣은 잘난체 > 동봉 가석원체 > 나머지
            n = f.name.lower()
            if want and want in n:
                return -1
            return 0 if "jalnan" in n else (1 if "gasoekone" in n else 2)
        cands.sort(key=_rank)
        for f in cands:
            try:
                from PIL import ImageFont
                name = ImageFont.truetype(str(f), 40).getname()[0]
                USED_FONTS.append(f)
                return name
            except Exception:
                pass
    sysname = platform.system()
    if sysname == "Darwin":
        return "Apple SD Gothic Neo"
    if sysname == "Windows":
        return "Malgun Gothic"
    return "Noto Sans CJK KR"


USED_FONTS = []
FONT_NAME = pick_font()
print(f"[자막] '{FONT_NAME}' 폰트로 렌더합니다.", file=sys.stderr)

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},84,&H00FFFFFF,&H00FFFFFF,&H50000000,&H70000000,-1,0,0,0,100,100,0,0,{BSTYLE},60,60,{MARGV},1\nStyle: Kin,{KFONT},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,0,1,5,60,60,0,1\nStyle: KinB,{KFONT},84,&H00FFFFFF,&H00FFFFFF,&H78000000,&H78000000,-1,0,0,0,100,100,0,0,3,14,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def markup(text, acc=None, base="FFFFFF", dim="B8B8B8"):
    """*단어* → 강조색, ~단어~ → 디밍. base = 해당 줄의 기본 잉크색(복원용)."""
    acc = acc or ACCENT_ASS
    out, on = [], False
    for seg in text.split("*"):
        if on:
            if EMPH_SCALE > 1.001:
                big = int(round(BASE_SIZE * EMPH_SCALE))
                out.append("{\\fs" + str(big) + "\\c&H" + acc + "&}" + seg
                           + "{\\fs" + str(BASE_SIZE) + "\\c&H" + base + "&}")
            else:
                out.append("{\\c&H" + acc + "&}" + seg + "{\\c&H" + base + "&}")
        else:
            out.append(seg)
        on = not on
    text = "".join(out)
    out, on = [], False
    for seg in text.split("~"):
        out.append(("{\\c&H" + dim + "&}" + seg + "{\\c&H" + base + "&}") if on else seg)
        on = not on
    return "".join(out)


def kin_font():
    """키네틱은 산세리프 미디엄 — assets에서 pretendard 우선."""
    fdir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    if fdir.is_dir():
        for f in sorted(fdir.rglob("*")):
            if "pretendard" in f.name.lower() and f.suffix.lower() in (".otf", ".ttf"):
                try:
                    from PIL import ImageFont
                    return ImageFont.truetype(str(f), 40).getname()[0]
                except Exception:
                    pass
    return FONT_NAME


if STYLE == "kinetic":
    KIN_FONT = kin_font()
    events = []
    for ln in lines:
        d = ln.get("dirs", {})
        size = int(84 * float(d.get("size", 1)))
        an = d.get("an", "5")
        tag = "{\\an" + an + "\\fs" + str(size)
        if "pos" in d:
            x, y = d["pos"].split(","); tag += "\\pos(" + x + "," + y + ")"
        style = "Kin"
        base, acc, dim = "FFFFFF", None, "B8B8B8"
        if d.get("ink") == "dark":          # 밝은 배경 — 검정 잉크 + 빨강 강조 + 진회색 디밍
            tag += "\\c&H262626&"
            base, acc, dim = "262626", "1E1EEE", "8A8A8A"
        if d.get("box") == "1":
            style = "KinB"
        tag += "}"
        events.append(f"Dialogue: 0,{ts(ln['s'])},{ts(ln['e'])},{style},,0,0,0,,{tag}{markup(ln['text'], acc, base, dim)}")
else:
    _fx = "{\\fad(120,100)}" if ANIM == "fade" else ""
    events = [f"Dialogue: 0,{ts(ln['s'])},{ts(ln['e'])},Sub,,0,0,0,,{_fx}{markup(ln['text'])}" for ln in lines]

_align, _margv = ("5", "0") if POS == "center" else ("2", "758")   # 758 = 자막 y≈1073~1162 — 하단은 인스타 UI에 먹힌다 (2026-08-23 정본)
# 박스 스타일: BorderStyle 4 = 줄 전체를 하나의 사각형으로 (3은 색 구간마다 박스가 따로 그려져 윗변이 울퉁불퉁해진다)
if STYLE == "box":
    _bstyle = "4,16,0,2"
    _margv = "568" if POS != "center" else _margv
else:
    _bstyle = "1,5,2,{}".format(_align)
_kfont = kin_font() if STYLE == "kinetic" else FONT_NAME
_head = ASS_HEAD.replace("{FONT}", "Pretendard" if STYLE == "box" else FONT_NAME).replace("{KFONT}", _kfont).replace("{BSTYLE}", _bstyle).replace("{MARGV}", _margv)
with open("reel_subs.ass", "w", encoding="utf-8") as f:
    f.write(_head + "\n".join(events) + "\n")

with open("reel_lines.json", "w", encoding="utf-8") as f:
    json.dump(lines, f, ensure_ascii=False, indent=1)


def collect_fonts():
    """쓴 폰트만 작업 폴더 _fonts/ 에 모은다 — libass fontsdir 는 하위 폴더를 안 뒤진다."""
    fdir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    want = list(USED_FONTS) + [f for f in fdir.rglob("pretendard*") if f.suffix.lower() in (".otf", ".ttf")]
    out = Path("_fonts"); out.mkdir(exist_ok=True)
    for f in want:
        dst = out / f.name
        if dst.exists():
            continue
        try:
            dst.symlink_to(f)
        except OSError:          # 윈도우는 심볼릭 링크 권한이 없을 수 있다
            import shutil
            shutil.copy2(f, dst)
    return out


if collect_fonts().is_dir():
    print("[자막] 합성 시 → ass=reel_subs.ass:fontsdir=_fonts", file=sys.stderr)

total_end = lines[-1]["e"] if lines else 0
print(f"{len(lines)} 자막 줄, 총 {total_end:.1f}s ({'구 단위 정렬' if PHRASES else '폴백 그룹핑'})")
for ln in lines:
    print(f"  {ln['s']:5.2f}-{ln['e']:5.2f}  {ln['text']}")
