"""모티베이션 몽타주 마스터 렌더 — 원본 소스에서 단일 패스 (+ 프리즈 홀드).
HDR 톤매핑 · 펀치인 크롭 · 속도/슬로모 · 비트 범프 줌 · 흔들림 · 휩 블러 · 프리즈 홀드 · concat · 그레이딩 · 오버레이.
사용: python3 build_master.py out.mp4 [--preview]   (--preview = 540x960 빠른 확인본, 약 45초)
무음 마스터다 — 음원은 인스타 업로드 때 입힌다.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import BEAT, CUTS, FPS, HDR, SRC, TOTAL_FRAMES, TOTAL_SEC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MINT = "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
GRADE = ("eq=contrast=1.08:brightness=0.02:saturation=0.95,colorbalance=rs=-0.04:bs=0.05:rm=-0.02:bm=0.03,"
         "vignette=angle=PI/7")

TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def crop_expr(crop):
  """소스 해상도와 무관하게 9:16 창을 1/zoom 크기로 (cx,cy) 중심에서 잘라낸다 — 가로 소스도 그대로 된다."""
  cx, cy, z = crop
  w = f"min(iw,ih*9/16)/{z}"
  return (f"crop=w='2*trunc({w}/2)':h='2*trunc({w}*16/9/2)':"
          f"x='min(max(iw*{cx}-ow/2,0),iw-ow)':y='min(max(ih*{cy}-oh/2,0),ih-oh)'")


def src_chain(c):
  """HDR 톤매핑(해당 소스만) + 크롭. freeze_card.py 도 같은 체인을 써야 이음매가 안 보인다."""
  f = [TONEMAP] if c["src"] in HDR else []
  f.append(crop_expr(c["crop"] or (0.5, 0.5, 1.0)))
  return f

def build(out, preview=False):
  W, H = (540, 960) if preview else (1080, 1920)
  k = W / 1080
  inputs, chains = [], []
  fstart = 0
  for i, c in enumerate(CUTS):
    n, sp = c["n"], c["speed"]
    fz = c.get("freeze")
    f = []
    if fz:
      # 프리즈 오프너 — 영상 대신 스틸 1장을 n프레임 홀드.
      # 채도를 살짝 빼 '정지' 신호를 주고, 1.00→1.03 아주 느린 푸시인으로 죽은 화면을 막는다.
      inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{(n + 6) / FPS:.3f}", "-i", fz]
      f.append(f"scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}")
      f.append("eq=saturation=0.85")
      z = f"(1+0.030*min(t/{n / FPS:.4f},1))"
      f.append(f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic")
      f.append(f"crop={W}:{H}")
    else:
      dsrc = n * sp / FPS
      inputs += ["-ss", f"{c['start']:.3f}", "-t", f"{dsrc + (0.15 if sp < 1 else 0.06):.3f}", "-i", SRC[c["src"]]]
      f += src_chain(c)
      f.append(f"scale={W}:{H}:flags=lanczos,setsar=1")
      if sp < 1:
        f.append(f"setpts=(PTS-STARTPTS)/{sp},{MINT}")
      else:
        f.append(f"setpts=(PTS-STARTPTS)/{sp},fps={FPS}")
    amp = c["shake"] * k
    if c["bump"] or amp:
      phase = (fstart % BEAT) / FPS
      beat = BEAT / FPS
      bump = f"(1+0.05*exp(-14*mod(t+{phase:.4f},{beat:.4f})))" if c["bump"] else "1"
      margin = 1.03 if amp else 1.0
      z = f"({margin}*{bump})"
      f.append(f"scale=w='2*trunc({W}*{z}/2)':h='2*trunc({H}*{z}/2)':eval=frame:flags=bicubic")
      if amp:
        f.append(f"crop={W}:{H}:x='(iw-{W})/2+{amp:.1f}*sin(t*97)':y='(ih-{H})/2+{amp*0.8:.1f}*cos(t*73)'")
      else:
        f.append(f"crop={W}:{H}")
    wi, wo = c["whip_in"], c["whip_out"]
    if wi or wo:
      conds = []
      if wi: conds.append(f"lt(t,{wi/FPS:.4f})")
      if wo: conds.append(f"gte(t,{(n-wo)/FPS:.4f})")
      f.append(f"avgblur=sizeX={int(71*k)|1}:sizeY=1:enable='{'+'.join(conds)}'")
    f.append(f"tpad=stop=6:stop_mode=clone,trim=end_frame={n},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[c{i}]")
    chains.append(f"[{i}:v]" + ",".join(f))
    fstart += n
  n_in = len(CUTS)
  inputs += ["-framerate", str(FPS), "-i", os.path.join(HERE, "ov", "%04d.png")]
  grade = GRADE + ("" if preview else ",noise=alls=4:allf=t")
  concat = "".join(f"[c{i}]" for i in range(n_in)) + f"concat=n={n_in}:v=1:a=0,setpts=N/({FPS}*TB),{grade}[base]"
  ov = f"[{n_in}:v]scale={W}:{H}:flags=lanczos[ov]" if preview else f"[{n_in}:v]null[ov]"
  fc = ";".join(chains + [concat, ov, "[base][ov]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[v]"])
  enc = (["-c:v", "libx264", "-crf", "24", "-preset", "veryfast"] if preview
         else ["-c:v", "libx264", "-crf", "18", "-preset", "slow"])
  cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats", *inputs,
         "-filter_complex", fc, "-map", "[v]", "-an", *enc, "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-t", f"{TOTAL_SEC:.3f}", out]
  with open(os.path.join(HERE, "last_cmd.txt"), "w") as fh:
    fh.write(" ".join(f"'{a}'" if " " in a or ";" in a else a for a in cmd))
  print(f"프레임 {TOTAL_FRAMES} = {TOTAL_SEC:.2f}s · 입력 {n_in}개 · {'PREVIEW' if preview else 'MASTER'} → {out}", flush=True)
  subprocess.run(cmd, check=True)

if __name__ == "__main__":
  a = sys.argv[1:]
  build(a[0], preview="--preview" in a)
