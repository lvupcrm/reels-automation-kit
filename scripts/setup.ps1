# 릴스 자동화 환경 세팅 (Windows) — 관리자 권한 없이 사용자 폴더 안에만 설치한다.
#   ffmpeg/ffprobe : %USERPROFILE%\.local\bin  (gyan.dev essentials 빌드, libass·zimg 포함)
#   uv             : 공식 설치 스크립트
#   파이썬 도구     : <작업폴더>\.venv   (자막은 faster-whisper — mlx는 애플 실리콘 전용)
# 실행:  powershell -ExecutionPolicy Bypass -File setup.ps1 [작업폴더]

param([string]$WorkDir = "$env:USERPROFILE\reels")

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Bin = "$env:USERPROFILE\.local\bin"
$FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

function Say($m) { Write-Host ""; Write-Host "> $m" -ForegroundColor Cyan }
function Ok($m)  { Write-Host "  [OK] $m" -ForegroundColor Green }
function Bad($m) { Write-Host "  [X] $m" -ForegroundColor Red }

Say "1/5 작업 폴더 준비"
New-Item -ItemType Directory -Force -Path "$WorkDir\input", "$WorkDir\voice", $Bin | Out-Null
Ok "$WorkDir (input, voice)"

Say "2/5 ffmpeg / ffprobe 설치"
if ((Test-Path "$Bin\ffmpeg.exe") -and (Test-Path "$Bin\ffprobe.exe")) {
    Ok "이미 설치됨 — 건너뜀"
} else {
    $zip  = Join-Path $env:TEMP "ffmpeg-essentials.zip"
    $dest = Join-Path $env:TEMP "ffx"
    Write-Host "  내려받는 중... (약 110MB, 몇 분 걸립니다)"
    $ProgressPreference = 'SilentlyContinue'   # 진행률 표시가 다운로드를 크게 느리게 만든다
    Invoke-WebRequest -Uri $FFMPEG_URL -OutFile $zip -UseBasicParsing
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    $ff = Get-ChildItem -Path $dest -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $ff) { Bad "압축 안에서 ffmpeg.exe를 찾지 못했습니다"; exit 1 }
    Copy-Item $ff.FullName "$Bin\ffmpeg.exe" -Force
    Copy-Item (Join-Path $ff.DirectoryName "ffprobe.exe") "$Bin\ffprobe.exe" -Force
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
    Ok "ffmpeg / ffprobe 설치 완료"
}

# 자막(libass)과 아이폰 HDR 톤매핑(zscale)은 필수다 — 빌드에 실제로 있는지 확인한다.
$filters = & "$Bin\ffmpeg.exe" -hide_banner -filters 2>$null | Out-String
if ($filters -match '(?m)^\s*\S*\s+ass\s') { Ok "자막 엔진(libass) 확인" }
else { Bad "이 빌드에는 자막 필터(ass)가 없습니다"; exit 1 }
if ($filters -match '(?m)^\s*\S*\s+zscale\s') { Ok "HDR 톤매핑(zscale) 확인" }
else { Bad "zscale이 없습니다 — 아이폰 HDR 영상의 색이 바랩니다"; exit 1 }

Say "3/5 uv (파이썬 도구 관리자) 설치"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Ok "이미 설치됨 — 건너뜀"
    $UvExe = $uv.Source
} else {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $UvExe = "$Bin\uv.exe"
    if (-not (Test-Path $UvExe)) {
        $found = Get-ChildItem "$env:USERPROFILE" -Recurse -Filter "uv.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $UvExe = $found.FullName } else { Bad "uv 설치 실패"; exit 1 }
    }
    Ok "uv 설치 완료"
}

Say "4/5 PATH 등록"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$Bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$Bin;$userPath", "User")
    Ok "사용자 PATH에 추가"
} else {
    Ok "이미 등록됨"
}
$env:Path = "$Bin;$env:Path"

Say "5/5 파이썬 AI 도구 설치 (10~20분 — 수 GB를 받습니다)"
Set-Location $WorkDir
$VenvPy = Join-Path $WorkDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { & $UvExe venv --python 3.12 .venv | Out-Null }
& $UvExe pip install --python $VenvPy qwen-tts soundfile numpy scipy onnxruntime faster-whisper pillow fonttools yt-dlp
if ($LASTEXITCODE -ne 0) { Bad "파이썬 도구 설치 실패"; exit 1 }

& $VenvPy -c "import qwen_tts, faster_whisper, PIL, fontTools, scipy, onnxruntime"
if ($LASTEXITCODE -ne 0) { Bad "파이썬 도구 검증 실패"; exit 1 }
Ok "목소리 클론 · 자막 싱크 · 타이포 렌더 도구 준비 완료"

Write-Host ""
Write-Host "==== 세팅 완료 ====" -ForegroundColor Green
Write-Host "  작업 폴더    : $WorkDir"
Write-Host "  영상 넣는 곳 : $WorkDir\input"
Write-Host "  ffmpeg       : $Bin\ffmpeg.exe"
Write-Host ""
Write-Host "  NEXT_STEP=PROFILE_INTERVIEW"
Write-Host "  > 다음 단계: 프로필·목표 인터뷰 — 클로드가 이어서 몇 가지 질문을 드립니다."
Write-Host "    (질문에 답하면 PROFILE.md·GOALS.md가 만들어지고 대본 품질이 크게 올라갑니다)"
Write-Host ""
