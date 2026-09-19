"""단어별 자막 — 인물 인서트형 문법 (references/preset-talk-insert.md).

단어(또는 구)마다 화면 위치를 박아 두고, *키워드*는 **말하는 순간** 강조색으로 팝한다.
한 줄이 통째로 뜨는 일반 자막보다 말과 화면이 딱 붙어 보인다.

하위 명령
  words  <오디오>[@시작초] ... [--gap 0.35] [--tempo 1.0] [-o words.json]
      청크 파일마다 따로 전사해 절대 타임라인으로 합친다. @시작초를 안 주면 앞 청크 끝 + gap 에 이어 붙인다.
      ⚠️ 합본을 한 번에 전사하면 뒤로 갈수록 1~2.7초씩 밀린다 — 청크 단위가 정본이다.
      --tempo: 배속 전 파일을 전사했으면 시각을 ÷tempo 한다 (배속한 파일을 전사하면 1.0).
  map    <원본words.json> <keep.json> [-o words.json]
      원본 녹음의 단어 시각을 점프컷 뒤 타임라인으로 옮긴다. keep = jumpcut_segments.json([{"s","e"}]) 또는 [[s,e],…]
      컷에 걸려 빠진 단어는 버린다. 재전사보다 정확하다(표기 차이·배속 끝 누락이 없다).
  ass    <words.json> <phrases.txt> [-o captions.ass] [--insert 3.2-7.8 ...] [--y 1080] [--insert-y 1660]
         [--size 66] [--accent 00FB98] [--neg FF5762] [--no-italic]
      phrases.txt 한 줄 = 화면 한 줄(≤16자 권장). 문법:
        *키워드*   말하는 순간 강조색(민트) + 90→110→100% 팝 — 줄마다 1~2개, 숫자·핵심 명사
        ^부정어^   코랄 + 짧은 흔들림 — "안 됩니다"·"틀렸다" 같은 반전어에만
        > 문장     줄 전체 강조색 — 실제 원음(인터뷰·반응) 구간 표시
      --insert a-b: 모션그래픽 인서트 창(초). 줄의 **중간 시각**이 창 안이면 자막을 아래(insert-y)로 내린다
                    (시작 시각으로 판정하면 인서트 직전에 시작한 줄이 카드와 겹친다).

합성: ass=captions.ass:fontsdir=_fonts   (이 스크립트가 Pretendard를 _fonts/ 에 모아둔다)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reel_assets import font_path, fontsdir  # noqa: E402

PUNCT = r"[\s.,!?~…·'\"()\[\]{}<>%*^\-]"
MAXW = 885          # 줄 폭 한도 — 우측 버튼·좌우 여백 안
POP = r"\fscx90\fscy90\t(0,65,\fscx110\fscy110)\t(65,160,\fscx100\fscy100)"


def norm(t):
  return re.sub(PUNCT, "", t)


def opt(args, name, default=None, many=False):
  vals = [args[i + 1] for i, a in enumerate(args[:-1]) if a == name]
  return vals if many else (vals[-1] if vals else default)


def positional(args):
  flags_with_value = {"-o", "--gap", "--tempo", "--insert", "--y", "--insert-y", "--size", "--accent", "--neg"}
  out, skip = [], False
  for a in args:
    if skip:
      skip = False; continue
    if a in flags_with_value:
      skip = True; continue
    if a.startswith("--"):
      continue
    out.append(a)
  return out


# ── words ────────────────────────────────────────────────────────────
def transcribe(path):
  try:
    import mlx_whisper
    r = mlx_whisper.transcribe(path, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                               language="ko", word_timestamps=True)
    return [{"t": w["word"].strip(), "s": w["start"], "e": w["end"]}
            for seg in r["segments"] for w in seg.get("words", [])]
  except ImportError:
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel("turbo", device="cpu", compute_type="int8").transcribe(path, language="ko", word_timestamps=True)
    return [{"t": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in (s.words or [])]


def duration(path):
  import soundfile as sf
  return sf.info(path).duration


def cmd_words(args):
  gap, tempo = float(opt(args, "--gap", 0.35)), float(opt(args, "--tempo", 1.0))
  out, cursor = [], 0.0
  for spec in positional(args):
    path, _, at = spec.partition("@")
    t0 = float(at) if at else cursor
    ws = transcribe(path)
    for w in ws:
      out.append({"t": w["t"], "s": round(t0 + w["s"] / tempo, 3), "e": round(t0 + w["e"] / tempo, 3)})
    cursor = t0 + duration(path) / tempo + gap
    print(f"  {os.path.basename(path)} @{t0:.2f}s  단어 {len(ws)}개: {''.join(w['t'] for w in ws)[:40]}")
  dst = opt(args, "-o", "words.json")
  json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
  print(f"→ {dst} ({len(out)}단어)")


# ── map ──────────────────────────────────────────────────────────────
def cmd_map(args):
  src, keep = positional(args)[:2]
  words = json.load(open(src, encoding="utf-8"))
  segs = [(k["s"], k["e"]) if isinstance(k, dict) else tuple(k) for k in json.load(open(keep, encoding="utf-8"))]
  out, base = [], 0.0
  for s, e in segs:
    for w in words:
      mid = (w["s"] + w["e"]) / 2
      if s <= mid < e:
        out.append({"t": w["t"], "s": round(base + max(w["s"], s) - s, 3), "e": round(base + min(w["e"], e) - s, 3)})
    base += e - s
  dst = opt(args, "-o", "words.json")
  json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
  print(f"→ {dst} ({len(words)}단어 중 {len(out)}개 유지, 컷 타임라인 {base:.2f}s)")


# ── 정렬 ─────────────────────────────────────────────────────────────
def align(texts, words):
  """문구 리스트를 단어 시각에 서열 정렬한다 → 문구마다 (시작초, 끝초, 글자별 시작초 리스트).
  글자수 소진 방식은 whisper가 "다섯 개"를 "5개"로 적는 순간 뒤 문구가 전부 밀린다 — difflib로 짝을 맞춘다."""
  import difflib
  wchars, wmap = [], []
  for i, w in enumerate(words):
    for ch in norm(w["t"]):
      wchars.append(ch); wmap.append(i)
  pchars = []
  for k, t in enumerate(texts):
    pchars += [(ch, k) for ch in norm(t)]
  P, Wc = "".join(c for c, _ in pchars), "".join(wchars)
  pm = [None] * len(P)
  for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, P, Wc, autojunk=False).get_opcodes():
    for n, i in enumerate(range(i1, i2)):
      if tag == "equal":
        pm[i] = j1 + n
      elif tag == "replace":
        pm[i] = j1 + min(j2 - j1 - 1, int(n * (j2 - j1) / (i2 - i1)))
      elif tag == "delete" and j1 < len(Wc):
        pm[i] = j1
  for i in range(len(pm)):              # 못 짝지은 글자는 앞 글자 위치를 물려받는다
    if pm[i] is None:
      pm[i] = pm[i - 1] if i and pm[i - 1] is not None else 0
  out, i = [], 0
  for k, t in enumerate(texts):
    n = len(norm(t))
    if n == 0 or not words:
      out.append(None); continue
    idx = [wmap[min(pm[j], len(wmap) - 1)] for j in range(i, i + n)]
    out.append((words[idx[0]]["s"], words[idx[-1]]["e"], [words[w]["s"] for w in idx]))
    i += n
  return out


# ── ass ──────────────────────────────────────────────────────────────
def libass_ratio(path):
  """libass는 폰트 크기를 (winAscent+winDescent) 기준으로 잡는다 — PIL 폭에 이 비율을 곱해야 화면 폭과 맞는다."""
  from fontTools.ttLib import TTFont
  f = TTFont(path, lazy=True)
  os2 = f["OS/2"]
  return f["head"].unitsPerEm / (os2.usWinAscent + os2.usWinDescent)


def ts(t):
  c = round(max(0.0, t) * 100)
  return f"{c // 360000}:{c // 6000 % 60:02}:{c // 100 % 60:02}.{c % 100:02}"


def bgr(hexrgb):
  h = hexrgb.lstrip("#")
  return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&"


def parse_line(raw):
  """→ (전체강조 여부, [(조각, 종류)]) 종류: n=보통 · a=강조 · x=부정"""
  whole = raw.startswith(">")
  text = raw[1:].strip() if whole else raw.strip()
  pieces, mode = [], "n"
  for tok in re.split(r"([*^])", text):
    if tok == "*":
      mode = "n" if mode == "a" else "a"
    elif tok == "^":
      mode = "n" if mode == "x" else "x"
    elif tok:
      if mode == "n":
        pieces.append((tok, "n"))
      else:   # 강조 구간은 어절 단위로 쪼개 각자 팝한다
        pieces += [(w, mode if not w.isspace() else "n") for w in re.split(r"(\s+)", tok) if w]
  return whole, pieces


def cmd_ass(args):
  from PIL import ImageFont
  wpath, ppath = positional(args)[:2]
  words = json.load(open(wpath, encoding="utf-8"))
  rows = [r for r in open(ppath, encoding="utf-8").read().splitlines() if r.strip()]
  y_base, y_ins = int(opt(args, "--y", 1080)), int(opt(args, "--insert-y", 1660))
  size0 = int(opt(args, "--size", 66))
  acc, neg = bgr(opt(args, "--accent", "00FB98")), bgr(opt(args, "--neg", "FF5762"))
  ins = [tuple(float(x) for x in w.split("-")) for w in opt(args, "--insert", many=True)]
  fpath = font_path("pretendard")
  ratio = libass_ratio(fpath)
  fam = ImageFont.truetype(fpath, 40).getname()[0]

  # 1) 줄마다 단어 시각을 서열 정렬로 붙인다
  parsed = [parse_line(r) for r in rows]
  timed = align(["".join(p for p, _ in pc) for _, pc in parsed], words)
  lines = []
  for raw, (whole, pieces), tm in zip(rows, parsed, timed):
    if tm is None:
      continue
    lines.append(dict(raw=raw, whole=whole, pieces=pieces, chars=tm[2], a=tm[0] - 0.05, b=tm[1] + 0.15))
  spoken = norm("".join(w["t"] for w in words))
  for ln in lines:
    core = norm("".join(p for p, _ in ln["pieces"]))
    if len(core) >= 2 and core not in spoken:
      print(f"⚠️ 발화와 다른 자막: {ln['raw']} — 대본에 없는 말이면 고친다 (숫자 표기 차이 '다섯'↔'5'면 무시해도 된다)")
  for cur, nxt in zip(lines, lines[1:]):
    cur["b"] = min(cur["b"], nxt["a"] - 0.02)

  # 2) 조각마다 위치를 박는다
  ev = []

  def emit(a, b, tags, text):
    if b - a > 0.01:
      ev.append(f"Dialogue: 2,{ts(a)},{ts(b)},Sub,,0,0,0,,{{{tags}}}{text}")

  for ln in lines:
    a, b = ln["a"], ln["b"]
    plain = "".join(p for p, _ in ln["pieces"])
    size = size0
    f = ImageFont.truetype(fpath, size)
    while f.getlength(plain) * ratio > MAXW and size > 40:
      size -= 1; f = ImageFont.truetype(fpath, size)
    y = y_ins if any(s <= (a + b) / 2 < e for s, e in ins) else y_base
    def spoken_at(prefix, chars=ln["chars"]):   # 그 조각의 첫 글자를 말하기 시작한 시각
      n = len(norm(prefix))
      return max(a, chars[min(n, len(chars) - 1)])

    x = (1080 - f.getlength(plain) * ratio) / 2
    done = ""
    for piece, kind in ln["pieces"]:
      w = f.getlength(piece) * ratio
      if piece.isspace():
        x += w; done += piece; continue
      cx = x + w / 2
      disp = piece.replace(" ", r"\h")
      pos = f"\\an5\\pos({cx:.1f},{y})\\fs{size}"
      if ln["whole"]:
        emit(a, b, pos + f"\\c{acc}" + POP, disp)
      elif kind == "a":
        at = spoken_at(done)
        emit(a, at, pos, disp)
        emit(at, b, pos + f"\\c{acc}" + POP, disp)
      elif kind == "x":
        at = spoken_at(done)
        emit(a, at, pos, disp)
        jit = [(-7, 2), (6, -3), (-5, -2), (4, 3), (-2, 1)]   # 1/15초 간격 흔들림 후 정지
        for k, (dx, dy) in enumerate(jit):
          t0 = at + k / 15
          emit(t0, min(b, t0 + 1 / 15), f"\\an5\\pos({cx + dx:.1f},{y + dy})\\fs{size}\\c{neg}", disp)
        emit(at + len(jit) / 15, b, pos + f"\\c{neg}", disp)
      else:
        emit(a, b, pos, disp)
      x += w; done += piece

  italic = "0" if "--no-italic" in args else "-1"
  head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
          "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
          "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
          "MarginR, MarginV, Encoding\n"
          f"Style: Sub,{fam},{size0},&H00FFFFFF,&H00FFFFFF,&H00131513,&H90000000,-1,{italic},0,0,100,100,0,0,1,2.5,3,5,0,0,0,1\n\n"
          "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
  dst = opt(args, "-o", "captions.ass")
  open(dst, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
  fontsdir(fpath)
  print(f"→ {dst} ({len(lines)}줄 · 이벤트 {len(ev)}개 · 폰트 '{fam}') — 합성: ass={dst}:fontsdir=_fonts")
  for ln in lines:
    print(f"  {ln['a']:6.2f}-{ln['b']:6.2f}  {ln['raw']}")


if __name__ == "__main__":
  if len(sys.argv) < 2 or sys.argv[1] not in ("words", "map", "ass"):
    sys.exit(__doc__)
  {"words": cmd_words, "map": cmd_map, "ass": cmd_ass}[sys.argv[1]](sys.argv[2:])
