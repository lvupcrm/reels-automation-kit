"""스킬 동봉 에셋(폰트·효과음) 경로 — 프리셋 스크립트 공용.

스킬 폴더를 어디에 두든 이 파일 위치를 기준으로 찾으므로 경로를 하드코딩하지 않는다.
  from reel_assets import font_path, sfx_path
  F_BODY = font_path("pretendard")                 # Pretendard Black (자막·본문)
  F_TITLE = font_path("jalnan", "dohyeon")         # 직접 넣은 잘난체가 있으면 그것, 없으면 도현
"""
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FONTS = SKILL / "assets" / "fonts"
SFX = SKILL / "assets" / "sfx"
_EXT = (".otf", ".ttf", ".ttc")


def _all_fonts():
  if not FONTS.is_dir():
    return []
  return sorted(f for f in FONTS.rglob("*") if f.suffix.lower() in _EXT and "licenses" not in f.parts)


def font_path(*keys):
  """파일명에 key가 들어간 폰트를 앞에서부터 찾는다. REEL_FONT 환경변수는 여기서 쓰지 않는다
  (프리셋은 역할별 폰트가 정해져 있어서 — 사용자가 바꾸라고 하면 스크립트 상단 상수를 고친다)."""
  fonts = _all_fonts()
  for k in keys:
    for f in fonts:
      if k.lower() in f.name.lower():
        return str(f)
  raise SystemExit(f"폰트를 찾지 못했습니다: {keys} — {FONTS} 를 확인하세요")


def sfx_path(name):
  """역할 이름(whoosh_in·tick·pop·impact·riser·ding·whoosh_out) 또는 역할 폴더 안 파일명 일부."""
  p = SFX / f"{name}.wav"
  if p.exists():
    return str(p)
  for f in sorted(SFX.rglob("*.wav")):
    if name.lower() in f.name.lower():
      return str(f)
  return None


def fontsdir(*paths):
  """ffmpeg ass= 필터의 fontsdir — libass는 하위 폴더를 안 뒤져서, assets/fonts 를 그대로 주면 오류 없이
  시스템 고딕으로 바뀐다. 쓸 폰트만 작업 폴더 _fonts/ 에 모아 그 경로를 반환한다."""
  out = Path(os.environ.get("REEL_FONTSDIR", Path.cwd() / "_fonts"))
  out.mkdir(parents=True, exist_ok=True)
  for f in (Path(p) for p in paths):
    dst = out / f.name
    if not dst.exists():
      try:
        dst.symlink_to(f)
      except OSError:
        import shutil
        shutil.copy2(f, dst)
  return str(out)
