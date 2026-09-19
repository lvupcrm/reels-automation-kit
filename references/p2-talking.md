# P2 — 토킹헤드 자막형

말하는 영상의 **원음을 그대로 살리고**, 점프컷 + 자막 + 인트로 타이틀로 릴스화한다. TTS 없음.

**적용 조건**: 입력 영상에 사람 말소리가 있고, 화자가 카메라를 향해 이야기하는 구성일 때.

## 1. 전사 → 대본 확정
```bash
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 talk_raw.wav   # 오디오 추출
```
- mlx_whisper(large-v3-turbo, word_timestamps)로 전체 전사 → **전사문을 사용자 확인 게이트에 제시**한다(말실수·빼고 싶은 구간을 지정받기 위해).
- 훅 타이틀 문구(인트로 3.2초용)를 전사 내용에서 뽑아 함께 제안한다.

## 2. 점프컷 (scripts/jumpcut_plan.py)
```bash
python jumpcut_plan.py input.mp4                # 기본: 무음 0.6s+ 제거, 앞뒤 0.12s 패딩
python jumpcut_plan.py input.mp4 --min-silence 0.8 --noise -30   # 뜸이 많은 화자는 완화
```
- 산출: `jumpcut_segments.json`(keep 구간) + trim/concat filter 스니펫 + 전후 길이 비교.
- 사용자가 빼달라는 구간(말실수)은 세그먼트에서 수동 제외한다.
- 목표 길이 30~60초. 초과하면 내용 단위로 통삭제할 구간을 제안한다 — 무음 컷만으로 줄이려 하면 말이 숨 가빠진다.

> 💡 단어별 자막·키워드 팝·흐린 배경 위 모션그래픽까지 가려면 **제작 프리셋 C(`preset-talk-insert.md`)** — 이 문서의 상위 버전이다.

## 3. 자막 (점프컷 "이후" 타임라인 기준 — 순서 중요)
- **권장**: 원본을 한 번 전사해 단어 시각을 얻고 `word_subs.py map 원본words.json jumpcut_segments.json -o words.json`으로 컷 타임라인에 옮긴 뒤
  `make_subs.py talk_cut.wav phrases.txt --words words.json`. 재전사하면 "18번"↔"열여덟 번" 같은 표기 차이로 어긋나는데, 이 방식은 그럴 일이 없다.
- 재전사 방식(아래)도 여전히 동작한다:
1. keep 세그먼트로 **오디오만 먼저 렌더**(빠름): `aselect`/`atrim` concat → `talk_cut.wav`
2. `talk_cut.wav`를 whisper로 재전사 → 구 단위 문구 리스트(각 ≤16자) 작성 → `make_subs.py talk_cut.wav phrases.txt`
3. 원본 타임라인으로 자막을 만들면 컷마다 어긋난다 — 반드시 컷 적용 후 오디오 기준으로.

## 4. 오디오 후처리
- `loudnorm=I=-15:TP=-1.5` 기본. 현장 소음이 있으면 앞단에 `afftdn=nf=-25` 추가(과하면 목소리가 뭉개진다 — 귀로 확인).
- `atempo` 톤 업은 하지 않는다 — 원음의 자연스러움이 이 파이프라인의 강점이다.

## 4-b. 시선이 프롬프터로 내려간 구간
정면을 보는 프레임을 프리즈하고 zoompan 4.5% 줌인으로 덮는다(오디오는 그대로 흐른다). 정면 후보는 0.5초 간격 얼굴 크롭 시트로 고른다.

## 5. 합성
- 세로 변환: 가로 소스는 인물 중심 `crop=608:1080:X:0,scale=1080:1920`. HDR이면 공통 규약 톤매핑.
- 인서트(선택): 말 내용에 화면·타이포 오버레이가 맞는 구간이 있으면 라운드 카드/`overlay`로 2~3곳만. 토킹헤드는 얼굴이 주인공이라 과한 삽입은 역효과다.
- 타이틀 인트로 3.2초 + 커버 프레임 (공통 규약).
- 마스터 렌더: 원본에서 trim·crop·concat·자막·타이틀까지 단일 `filter_complex`로 1회 인코딩 (공통 규약).
