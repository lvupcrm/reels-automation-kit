#!/bin/bash
# 릴스 자동화 환경 세팅 — 관리자 비밀번호 없이, 홈 폴더 안에만 설치한다.
#   ffmpeg/ffprobe : ~/.local/bin  (Apple Silicon 네이티브 정적 빌드, libass 포함)
#   uv             : ~/.local/bin  (공식 설치 스크립트)
#   파이썬 도구     : <작업폴더>/.venv
# 사용법:  bash setup.sh [작업폴더]     (기본값 ~/reels)
set -u
TMPDIR="${TMPDIR:-/tmp}"

WORKDIR="${1:-$HOME/reels}"
BIN="$HOME/.local/bin"
FF_ARM_BASE="https://www.osxexperts.net"

say() { printf "\n\033[1;34m▶ %s\033[0m\n" "$1"; }
ok()  { printf "  \033[1;32m✔\033[0m %s\n" "$1"; }
bad() { printf "  \033[1;31m✘\033[0m %s\n" "$1"; }

say "1/5 작업 폴더 준비"
mkdir -p "$WORKDIR/input" "$WORKDIR/voice" "$BIN"
ok "$WORKDIR (input · voice)"

say "2/5 ffmpeg · ffprobe 설치"
arch="$(uname -m)"
if [ "$arch" != "arm64" ]; then
  bad "이 스크립트는 애플 실리콘(M1 이상) 전용입니다. 현재: $arch"
  bad "인텔 맥이라면 클로드에게 '인텔용 ffmpeg로 설치해줘'라고 알려주세요."
  exit 1
fi

install_ff() {           # $1 = ffmpeg | ffprobe
  local name="$1" zip="$TMPDIR/${1}9arm.zip"
  if [ -x "$BIN/$name" ] && "$BIN/$name" -version >/dev/null 2>&1; then
    ok "$name 이미 설치됨 — 건너뜀"; return 0
  fi
  curl -fsSL -o "$zip" "$FF_ARM_BASE/${name}9arm.zip" || { bad "$name 다운로드 실패"; return 1; }
  unzip -o -q "$zip" -d "$TMPDIR/ffx_$name" || { bad "$name 압축 해제 실패"; return 1; }
  mv -f "$TMPDIR/ffx_$name/$name" "$BIN/$name" || { bad "$name 이동 실패"; return 1; }
  chmod +x "$BIN/$name"
  xattr -dr com.apple.quarantine "$BIN/$name" 2>/dev/null   # Gatekeeper 격리 해제
  rm -rf "$zip" "$TMPDIR/ffx_$name"
  "$BIN/$name" -version >/dev/null 2>&1 && ok "$name 설치 완료" || { bad "$name 실행 실패"; return 1; }
}
install_ff ffmpeg || exit 1
install_ff ffprobe || exit 1

# 자막 렌더에 libass, 아이폰 HDR 톤매핑에 zscale(zimg)이 반드시 필요하다.
# ⚠️ Homebrew 기본 ffmpeg에는 둘 다 빠져 있어(2026-08 확인) 자막이 안 붙고 색이 물빠진다.
if "$BIN/ffmpeg" -filters 2>/dev/null | grep -qw "ass"; then
  ok "자막 엔진(libass) 확인"
else
  bad "이 ffmpeg 빌드에는 자막 필터(ass)가 없습니다"; exit 1
fi
if "$BIN/ffmpeg" -filters 2>/dev/null | grep -qw "zscale"; then
  ok "HDR 톤매핑(zscale) 확인"
else
  bad "zscale이 없습니다 — 아이폰 HDR 영상의 색이 바랩니다"; exit 1
fi

say "3/5 uv (파이썬 도구 관리자) 설치"
if command -v uv >/dev/null 2>&1 || [ -x "$BIN/uv" ]; then
  ok "uv 이미 설치됨 — 건너뜀"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
  [ -x "$BIN/uv" ] && ok "uv 설치 완료" || { bad "uv 설치 실패"; exit 1; }
fi
UV="$(command -v uv || echo "$BIN/uv")"

say "4/5 PATH 등록"
LINE='export PATH="$HOME/.local/bin:$PATH"'
if grep -qsF "$LINE" "$HOME/.zprofile"; then
  ok "이미 등록됨"
else
  printf '\n# 릴스 자동화 도구 경로\n%s\n' "$LINE" >> "$HOME/.zprofile"
  ok "~/.zprofile에 추가"
fi
export PATH="$BIN:$PATH"

say "5/5 파이썬 AI 도구 설치 (10~20분 — 수 GB를 받습니다)"
cd "$WORKDIR" || exit 1
[ -d .venv ] || "$UV" venv --python 3.12 .venv >/dev/null 2>&1
"$UV" pip install --python .venv/bin/python -q \
  qwen-tts soundfile numpy scipy onnxruntime mlx-whisper pillow fonttools yt-dlp || { bad "파이썬 도구 설치 실패"; exit 1; }

if .venv/bin/python -c "import qwen_tts, mlx_whisper, PIL, fontTools, scipy, onnxruntime" 2>/dev/null; then
  ok "목소리 클론 · 자막 싱크 · 타이포 렌더 도구 준비 완료"
else
  bad "파이썬 도구 검증 실패"; exit 1
fi

printf "\n\033[1;32m════ 세팅 완료 ════\033[0m\n"
printf "  작업 폴더 : %s\n" "$WORKDIR"
printf "  영상 넣는 곳 : %s\n" "$WORKDIR/input"
printf "  ffmpeg : %s\n" "$(command -v ffmpeg || echo "$BIN/ffmpeg")"
printf "\n  NEXT_STEP=PROFILE_INTERVIEW\n"
printf "  ▶ 다음 단계: 프로필·목표 인터뷰 — 클로드가 이어서 몇 가지 질문을 드립니다.\n"
printf "    (질문에 답하면 PROFILE.md·GOALS.md가 만들어지고 대본 품질이 크게 올라갑니다)\n\n"
