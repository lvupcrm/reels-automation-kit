#!/bin/bash
# make_sfx.sh — 릴스용 효과음 팩 합성 (ffmpeg 파형 생성 = 저작권 발생 없음)
# 사용: bash make_sfx.sh [출력폴더]   기본 출력: ../assets/sfx
set -euo pipefail

OUT="${1:-$(cd "$(dirname "$0")/.." && pwd)/assets/sfx}"
mkdir -p "$OUT"
SR=48000
Q="-hide_banner -loglevel error -y"

# 피크를 -3 dBFS로 맞춘다 (짧은 파일은 loudnorm이 불안정 → 피크 정규화)
norm() {
  local f="$1"
  local peak
  peak=$(ffmpeg -hide_banner -i "$f" -af volumedetect -f null - 2>&1 \
         | sed -n 's/.*max_volume: \(-*[0-9.]*\) dB.*/\1/p' | head -1)
  [ -z "$peak" ] && return 0
  local gain
  gain=$(python3 -c "print(round(-3.0 - ($peak), 2))")
  ffmpeg $Q -i "$f" -af "volume=${gain}dB" "${f%.wav}_n.wav"
  mv "${f%.wav}_n.wav" "$f"
}

# ── 1. whoosh_in — 컷 전환(상승). 노이즈 대역을 400→1200→3000Hz로 크로스페이드해 스윕 근사
ffmpeg $Q \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -filter_complex "\
    [0:a]bandpass=f=400:width_type=o:w=2[a]; \
    [1:a]bandpass=f=1200:width_type=o:w=2[b]; \
    [2:a]bandpass=f=3000:width_type=o:w=2[c]; \
    [a][b]acrossfade=d=0.22:c1=tri:c2=tri[ab]; \
    [ab][c]acrossfade=d=0.22:c1=tri:c2=tri[s]; \
    [s]volume='pow(t/0.46\,1.4)':eval=frame,afade=t=out:st=0.40:d=0.06[out]" \
  -map "[out]" -ar $SR -ac 1 "$OUT/whoosh_in.wav"
norm "$OUT/whoosh_in.wav"

# ── 2. whoosh_out — 컷 전환(하강). 대역을 3000→1200→400Hz 역순
ffmpeg $Q \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -f lavfi -i "anoisesrc=c=pink:d=0.30:a=0.9:r=$SR" \
  -filter_complex "\
    [0:a]bandpass=f=3000:width_type=o:w=2[a]; \
    [1:a]bandpass=f=1200:width_type=o:w=2[b]; \
    [2:a]bandpass=f=400:width_type=o:w=2[c]; \
    [a][b]acrossfade=d=0.22:c1=tri:c2=tri[ab]; \
    [ab][c]acrossfade=d=0.22:c1=tri:c2=tri[s]; \
    [s]volume='pow(1-t/0.46\,0.8)':eval=frame,afade=t=in:st=0:d=0.03[out]" \
  -map "[out]" -ar $SR -ac 1 "$OUT/whoosh_out.wav"
norm "$OUT/whoosh_out.wav"

# ── 3. pop — 타이포 카드 등장. 900→300Hz 하강 사인 + 급감쇠
ffmpeg $Q \
  -f lavfi -i "aevalsrc='0.9*sin(2*PI*(900*t-3750*t*t))':d=0.09:s=$SR:c=mono" \
  -af "volume='exp(-26*t)':eval=frame,lowpass=f=6000" \
  -ar $SR -ac 1 "$OUT/pop.wav"
norm "$OUT/pop.wav"

# ── 4. tick — 자막/포인트 강조. 초단타 고역 노이즈 클릭
ffmpeg $Q \
  -f lavfi -i "anoisesrc=c=white:d=0.05:a=0.9:r=$SR" \
  -af "highpass=f=2200,volume='exp(-90*t)':eval=frame" \
  -ar $SR -ac 1 "$OUT/tick.wav"
norm "$OUT/tick.wav"

# ── 5. impact — 훅/강조 임팩트. 90→20Hz 저역 붐 + 어택 노이즈
ffmpeg $Q \
  -f lavfi -i "aevalsrc='sin(2*PI*(90*t-70*t*t))':d=0.55:s=$SR:c=mono" \
  -f lavfi -i "anoisesrc=c=white:d=0.55:a=0.5:r=$SR" \
  -filter_complex "\
    [0:a]volume='exp(-5.5*t)':eval=frame[low]; \
    [1:a]highpass=f=900,volume='0.45*exp(-45*t)':eval=frame[att]; \
    [low][att]amix=inputs=2:duration=first:normalize=0[out]" \
  -map "[out]" -ar $SR -ac 1 "$OUT/impact.wav"
norm "$OUT/impact.wav"

# ── 6. riser — CTA 직전 긴장 상승. 200→3000Hz 상승 사인 + 노이즈 레이어
ffmpeg $Q \
  -f lavfi -i "aevalsrc='0.5*sin(2*PI*(200*t+933*t*t))':d=1.5:s=$SR:c=mono" \
  -f lavfi -i "anoisesrc=c=pink:d=1.5:a=0.6:r=$SR" \
  -filter_complex "\
    [0:a]volume='pow(t/1.5\,2)':eval=frame[tone]; \
    [1:a]highpass=f=1500,volume='0.5*pow(t/1.5\,3)':eval=frame[air]; \
    [tone][air]amix=inputs=2:duration=first:normalize=0,afade=t=out:st=1.42:d=0.08[out]" \
  -map "[out]" -ar $SR -ac 1 "$OUT/riser.wav"
norm "$OUT/riser.wav"

# ── 7. ding — CTA 확정/완료. 1200Hz 기음 + 배음 2개, 종 감쇠
ffmpeg $Q \
  -f lavfi -i "aevalsrc='0.6*sin(2*PI*1200*t)+0.28*sin(2*PI*2400*t)+0.12*sin(2*PI*3620*t)':d=1.2:s=$SR:c=mono" \
  -af "volume='exp(-4.2*t)':eval=frame,afade=t=in:st=0:d=0.004" \
  -ar $SR -ac 1 "$OUT/ding.wav"
norm "$OUT/ding.wav"

echo "완료 → $OUT"
for f in "$OUT"/*.wav; do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  printf "  %-16s %.2fs\n" "$(basename "$f")" "$d"
done
