# 릴스 자동화 키트 (Reels Automation Kit)

**Claude Code에 "릴스 만들어줘" 한 줄이면** 대본 → 내 목소리 나레이션 → 자막 싱크 → 컷 편집 → 완성본 mp4까지 만들어 주는 스킬입니다.
편집 프로그램을 배우지 않아도 됩니다. 사람이 하는 일은 **촬영과 주제 정하기**, 그리고 결과를 보고 말로 고치는 것입니다.

- 영상 종류 6가지 자동 판별 — 말하는 영상 · 말 없는 현장 영상 · 분위기 영상 · 화면 녹화 · 제품 · 리액션
- **검증된 제작 프리셋 4종** — 실제로 발행해 반응까지 본 릴스의 구조 그대로: 모티베이션 몽타주(+프리즈 오프너) · 롱테이크 브이로그 · 인물 인서트 · 화면 전용 설명편
- 편집 스타일 10종 · 컷 레이아웃 6종 · 한글 폰트 39종 · 효과음 215종 동봉 — 전부 상업 이용 가능한 라이선스
- 모든 처리가 내 컴퓨터에서 무료 오픈소스로 돌아갑니다(목소리 클론 Qwen3-TTS · 자막 Whisper · 편집 FFmpeg)

만든 곳: **AI 마케터스** · 인스타그램 [@ai_mkters](https://instagram.com/ai_mkters)

## 필요한 것
| | |
|---|---|
| 컴퓨터 | **맥 M1 이상**(검증됨) · 윈도우 10 이상 64비트(스크립트는 있으나 아직 검증 안 됨) |
| 클로드 | **Pro(월 $20) 이상** 구독 + [Claude Code 앱](https://claude.com/claude-code) |
| 디스크 | 여유 20GB (AI 모델 6~8GB) |
| 시간 | 세팅부터 첫 릴스까지 약 1시간 (절반은 설치 대기) |

## 설치 — 클로드에게 이렇게 말하세요
Claude Code 앱에서 작업 폴더(예: `reels`)를 열고 붙여넣습니다.
```
https://github.com/lvupcrm/reels-automation-kit 를 ~/.claude/skills/reel 에 설치하고(git이 없으면 zip으로 받아서), 릴스 스킬의 세팅 스크립트까지 실행해줘. 작업 폴더는 이 폴더로 해줘.
```
터미널로 직접 하려면:
```bash
git clone https://github.com/lvupcrm/reels-automation-kit ~/.claude/skills/reel
bash ~/.claude/skills/reel/scripts/setup.sh ~/reels        # 윈도우: scripts/setup.ps1
```
- 세팅은 **관리자 비밀번호 없이** 사용자 폴더 안에만 설치합니다(ffmpeg·uv·파이썬 도구). Homebrew는 쓰지 않습니다 — 설치 중 비밀번호를 요구해 AI가 대신 진행할 수 없기 때문입니다.
- 세팅이 끝나면 클로드가 프로필 질문(업종·타깃·말투)을 시작합니다. 답하면 `PROFILE.md`·`GOALS.md`가 생기고 대본이 내 사업에 맞게 나옵니다.
- 처음부터 차근차근 따라 하려면 **[세팅 가이드 PDF](docs/세팅가이드.pdf)**(20쪽, 앱 설치부터 첫 릴스까지)를 보세요.

## 첫 릴스
작업 폴더의 `input`에 폰 영상 2~3개를 넣고:
```
input 폴더의 영상들로 릴스 만들어줘. 주제: "매일 아침 매장 오픈 준비 루틴 3가지"
```
클로드가 **대본과 컷 구성을 먼저 보여줍니다** — 고칠 점을 말하고 "좋아, 진행해"라고 하면 렌더합니다.
주문 문장 모음은 **[프롬프트 라이브러리](docs/프롬프트_라이브러리.md)** 에 있습니다(스타일 10종 · 제작 프리셋 4종 · 고치는 말).

## 어떤 퀄리티가 나오나요 (솔직하게)
- **같게 나오는 것** — 코드가 보장합니다: 해상도·아이폰 HDR 색 처리·자막 싱크와 폰트·인스타 UI를 피하는 배치·프리셋의 컷 구조와 효과.
- **사람 몫인 것** — 소재(무엇을 찍었나), 목소리(녹음 품질이 그대로 복제됩니다), 그리고 **결과를 보고 몇 번 피드백하느냐**.
  프리셋에는 수십 번 고쳐 확정한 최종값이 들어 있어 출발점은 높지만, 컷 선택·카피·크롭은 여러분이 봐주셔야 합니다. 첫 결과는 "기술적으로 깔끔한 80점"을 기대하세요.
- 고친 방식은 "앞으로 계속 그렇게 해 — 규칙으로 적어둬"라고 하면 작업 폴더의 `MY_RULES.md`에 쌓이고 다음 편부터 지켜집니다.

## 업데이트
```
릴스 스킬 최신 버전으로 업데이트해줘
```
git으로 설치했다면 `git -C ~/.claude/skills/reel pull` 후 세팅 스크립트를 한 번 더 돌리면 됩니다.
내 설정(`PROFILE.md`·`GOALS.md`·`MY_RULES.md`·목소리 `voice/`)은 **작업 폴더**에 있어서 스킬을 업데이트해도 그대로입니다.
직접 넣은 폰트(`assets/fonts/`)도 git이 추적하지 않는 파일이라 안전합니다. 바뀐 점은 [CHANGELOG](CHANGELOG.md).

## 구성
| 파일 | 역할 |
|---|---|
| `SKILL.md` | 매뉴얼 본체 — 파이프라인 판별 라우터와 공통 규약 |
| `references/p1-narration.md` | 나레이션 몽타주형 (주제 + 말 없는 영상) |
| `references/p2-talking.md` | 토킹헤드 자막형 (말하는 영상) |
| `references/p3-bgm-typo.md` | BGM + 타이포형 (분위기 소재) |
| `references/p4-demo.md` | 앱 데모 튜토리얼형 (화면 녹화) |
| `references/p5-product.md` | 제품 등장형 (실물·음식·공간) |
| `references/p6-reaction.md` | 리액션형 (원본 콘텐츠 + 내 반응) |
| `references/layouts.md` | **컷 레이아웃 6종** — 컷마다 고르는 화면 배치 |
| `references/presets.md` | **편집 스타일 프리셋 10종** — "N번 스타일로" 하면 적용 |
| `scripts/setup.sh` | 환경 세팅 — **macOS** (ffmpeg·uv·파이썬 도구, 비밀번호 불필요) |
| `scripts/setup.ps1` | 환경 세팅 — **Windows** (관리자 권한 불필요) |
| `scripts/tts_chunks.py` | 목소리 클론 나레이션 생성 |
| `scripts/make_subs.py` | 자막 타이밍 싱크 (ASS 자막 생성) |
| `scripts/make_typo.py` | 타이틀·강조 텍스트 이미지 렌더 |
| `scripts/make_cover.py` | 커버 생성 — 스타일 6종 + 그리드 미리보기 |
| `scripts/make_mockup.py` | 스크린샷 → 아이폰 목업 프레임 |
| `scripts/make_annot.py` | 화살표·원·박스 주석 그래픽 |
| `scripts/jumpcut_plan.py` | 무음 구간 점프컷 플래너 |
| `scripts/ref_profile.py` | 레퍼런스 릴스 자동 계측 — 컷 리듬·자막 위치·색 실측 |
| `scripts/make_sfx.sh` | 효과음 7종 합성 레시피 (원저작자 없는 효과음을 다시 만들 때) |
| `references/preset-motivation.md` + `scripts/preset_motivation/` | **제작 프리셋 A** — 모티베이션 몽타주 + 프리즈 오프너 |
| `references/preset-longtake.md` + `scripts/preset_longtake/` | **제작 프리셋 B** — 롱테이크·일상 브이로그 |
| `references/preset-talk-insert.md` | **제작 프리셋 C** — 인물 인서트(단어별 자막·모션그래픽·녹음 원음) |
| `references/preset-screen-only.md` | **제작 프리셋 D** — 화면 전용 설명편 |
| `references/craft-notes.md` | 수정 요청·오디오·목소리·렌더 함정 모음 |
| `scripts/word_subs.py` | 단어별 자막(키워드 팝) · 청크별 전사 · 점프컷 타임라인 매핑 |
| `scripts/mg_kit.py` | 인서트용 모션그래픽 4종(투명 MOV) |
| `scripts/voice_tools.py` | 목소리 검수 — 음색 드리프트·먹히는 청크·화자 구분·컷 지점·말 속도 |
| `scripts/screen_cards.py` | 화면 카드(브라우저·터미널) + 프레임 직접 합성 렌더 |
| `scripts/layout.py` | 인스타 UI 가림 영역·안전 좌표 + 오버레이 검사 |

## 라이선스
코드 **MIT** · 문서 **CC BY 4.0** · 폰트 **OFL 1.1** · 효과음 **CC0 / 자체 합성**. 자세한 표는 [LICENSES.md](LICENSES.md).
만든 릴스의 권리는 만든 사람에게 있습니다 — 영상에 넣은 촬영 소재·음원·제3자 목소리의 권리는 각자 확인해 주세요.
