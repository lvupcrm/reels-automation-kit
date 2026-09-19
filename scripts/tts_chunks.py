"""클론 보이스 나레이션 생성 — 대본 청크별로 생성해 하나의 wav로 합친다.

사용법 (작업 폴더에서):
    .venv/bin/python tts_chunks.py --chunks chunks.txt     # chunks.txt = 청크 한 줄씩
목소리는 작업 폴더의 voice/voice.json 을 자동으로 찾는다 (현재 폴더부터 위로):
    {"ref_audio": "ref.wav", "ref_text": "레퍼런스 녹음에서 실제로 말한 그대로"}
    ref_audio 는 voice.json 이 있는 폴더 기준 상대경로 또는 절대경로.
⚠️ 이 스크립트 파일은 고쳐 쓰지 않는다 — 스킬 폴더는 업데이트(git pull)로 덮인다. 목소리·대본은 작업 폴더에 둔다.
   voice.json·--chunks 가 없으면 아래 설정 블록 상수로 돌아간다(예전 방식 호환).
산출:
    reel_chunk0.wav, reel_chunk1.wav, ...  (청크별)
    reel_narration.wav                     (0.35초 간격으로 이어붙인 최종본)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# ─────────────────────────────────────────────────────────────
# 여기만 수정하세요
# ─────────────────────────────────────────────────────────────

# 목소리 레퍼런스 — 15~20초 녹음 wav (릴스 톤으로 밝고 힘있게 녹음할 것)
REF_AUDIO = "ref_clean.wav"

# ⚠️ 레퍼런스 녹음에서 "실제로 말한 내용"을 한 글자도 틀리지 않게 적을 것.
#    한 단어라도 다르면 옹알이가 생성된다 — 클론 실패의 최다 원인.
#    추임새("어…", "그")까지 들린 그대로 옮긴다.
REF_TEXT = (
    "여기에 레퍼런스 녹음의 정확한 발화 내용을 적으세요 "
    "실제로 말한 그대로여야 합니다"
)

# 나레이션 대본 — 청크(문단) 단위로 나눈다. 청크당 3~5초가 적당.
# 숫자는 한글로 표기할 것("5~10분" ✗ → "오 분에서 십 분" ○) — 아라비아 숫자는 오독된다.
CHUNKS = [
    "첫 번째 청크 — 후킹 질문을 1인칭 공감으로.",
    "두 번째 청크 — 근거를 구체적으로.",
    "세 번째 청크 — 약속과 명확한 CTA로 마무리.",
]

# ─────────────────────────────────────────────────────────────


def _voice_json():
    for d in [Path.cwd(), *Path.cwd().parents]:
        f = d / "voice" / "voice.json"
        if f.exists():
            return f
    return None


_vj = _voice_json()
if _vj:
    _v = json.load(open(_vj, encoding="utf-8"))
    _ra = Path(_v["ref_audio"])
    REF_AUDIO = str(_ra if _ra.is_absolute() else (_vj.parent / _ra))
    REF_TEXT = _v["ref_text"]
    print(f"목소리: {_vj}", flush=True)
if "--chunks" in sys.argv:
    _cf = sys.argv[sys.argv.index("--chunks") + 1]
    CHUNKS = [ln.strip() for ln in open(_cf, encoding="utf-8") if ln.strip()]
if REF_TEXT.startswith("여기에 레퍼런스"):
    sys.exit("목소리가 등록되지 않았습니다 — 작업 폴더에 voice/voice.json 을 만드세요 (references/p1-narration.md §1-b)")

t0 = time.time()
model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="cpu",       # MPS(맥 GPU)는 출력이 깨질 수 있어 CPU fp32 고정
    torch_dtype=torch.float32,
)
print(f"model loaded in {time.time()-t0:.0f}s", flush=True)

parts = []
sr_out = 24000
for i, text in enumerate(CHUNKS):
    t1 = time.time()
    wavs, sr = model.generate_voice_clone(
        text=text, language="Korean",
        ref_audio=REF_AUDIO, ref_text=REF_TEXT,
        max_new_tokens=300,
    )
    sr_out = sr
    dur = len(wavs[0]) / sr
    print(f"chunk{i}: {time.time()-t1:.0f}s gen, {dur:.1f}s audio", flush=True)
    sf.write(f"reel_chunk{i}.wav", wavs[0], sr)
    parts.append(wavs[0])
    parts.append(np.zeros(int(sr * 0.35), dtype=wavs[0].dtype))

full = np.concatenate(parts[:-1])
sf.write("reel_narration.wav", full, sr_out)
print(f"WROTE reel_narration.wav total {len(full)/sr_out:.1f}s", flush=True)
print("→ 생성 후 mlx_whisper로 재전사해 대본과 대조할 것 (옹알이 검출)", flush=True)
