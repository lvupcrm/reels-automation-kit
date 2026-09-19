"""ai_mkters 이펙트 헬퍼 v1 — ffmpeg filter 문자열 생성기.

  punch(times)  강조어 타이밍 스냅 줌 (팍 확대 → 0.3초 감쇠 복귀)
  shake(times)  임팩트 순간 화면 흔들림 (감쇠 지터)
  glitch(times) 컷 경계 RGB 스플릿 글리치 (프레임 교차 플리커)

모두 1080x1920 입력 기준. punch·shake는 같은 체인에서 순서대로 이어 붙일 수 있다.
속도 램핑은 필터가 아니라 레시피: 구간을 trim 두 개로 나눠 setpts 배율을 달리 주고 concat.
  예) 슬로우 진입: [v]trim=0:0.6,setpts=PTS*1.8[a]; [v]trim=0.6:3,setpts=(PTS-STARTPTS)/1.15[b]; [a][b]concat
"""


def _envelope(times, amp, decay):
    """이벤트 시점마다 즉시 상승 후 지수 감쇠하는 합성 포락선 식."""
    terms = [f"if(gte(t,{t:.3f}),{amp}*exp(-{decay}*(t-{t:.3f})),0)" for t in times]
    return "(" + "+".join(terms) + ")" if terms else "0"


def punch(times, amp=0.10, decay=9):
    """강조어 스냅 줌 — crop 폭/높이를 순간 줄였다 복귀(중앙 고정) 후 원해상도 복원."""
    e = _envelope(times, amp, decay)
    return (f"crop=w='floor(iw/(1+{e})/2)*2':h='floor(ih/(1+{e})/2)*2',"
            f"scale=1080:1920:flags=bicubic,setsar=1")


def shake(times, amp=14, decay=11, freq=52):
    """임팩트 셰이크 — 1.03배 확대 후 감쇠 지터 크롭."""
    e = _envelope(times, amp, decay)
    return (f"scale=1124:1998,"
            f"crop=1080:1920:"
            f"x='(iw-1080)/2+{e}*sin(t*{freq})':"
            f"y='(ih-1920)/2+{e}*cos(t*{freq}*1.3)',setsar=1")


def glitch(times, span=0.14):
    """컷 경계 글리치 — RGB 채널 어긋남을 짝/홀 프레임 교차로 플리커."""
    wins = "+".join(f"between(t,{t - span:.3f},{t + span:.3f})" for t in times)
    a = f"rgbashift=rh=14:bv=-10:gh=-6:enable='({wins})*lt(mod(n,2),1)'"
    b = f"rgbashift=rh=-10:bv=12:gv=8:enable='({wins})*gte(mod(n,2),1)'"
    return a + "," + b


if __name__ == "__main__":
    import sys
    kind = sys.argv[1]
    times = [float(x) for x in sys.argv[2].split(",")]
    print({"punch": punch, "shake": shake, "glitch": glitch}[kind](times))
