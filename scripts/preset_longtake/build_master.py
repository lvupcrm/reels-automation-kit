"""롱테이크·브이로그 마스터 렌더 — 원본 소스에서 단일 패스 (영상+현장음).
HDR 톤매핑 · 정규화 크롭(소스 해상도 무관) · fit 모드(블러 배경+4:5 프레임) · 슬로모(minterpolate) · concat(v+a) ·
담백한 그레이딩 · 오버레이 PNG 시퀀스 · 끝 페이드. 현장음은 컷 경계 0.08초 페이드 + loudnorm −16.
사용: python3 build_master.py out.mp4 [--preview]   (--preview = 프록시·540x960)
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import CUTS, FPS, HDR, SRC, SRC_LRF, TOTAL_FRAMES, TOTAL_SEC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
MINT = "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
GRADE = "eq=contrast=1.03:saturation=1.05"
FADE_D = 0.5
FADE_ST = round(TOTAL_SEC - FADE_D, 3)

def crop_expr(cx, cy, z, aspect=9 / 16):
  """소스 크기에 무관하게 aspect 비율 영역을 1/z 크기로 (cx,cy) 중심에서 잘라낸다 (가로·세로·화면녹화 모두)."""
  w = f"min(iw,ih*{aspect:.6f})/{z}"
  return (f"crop=w='2*trunc({w}/2)':h='2*trunc({w}/{aspect:.6f}/2)':"
          f"x='min(max(iw*{cx}-ow/2,0),iw-ow)':y='min(max(ih*{cy}-oh/2,0),ih-oh)'")

def video_chain(i, c, W, H, k):
  n, sp = c["n"], c["speed"]
  segs, f = [], []
  pre = f"[{i}:v]{TONEMAP}[tm{i}]" if c["src"] in HDR else None
  if pre:
    segs.append(pre)
  vin = f"[tm{i}]" if pre else f"[{i}:v]"
  if c["fit"]:
    cx, cy, z, asp = c["fit"]
    fw, fh = W, 2 * int(round(W / asp / 2))
    segs.append(f"{vin}split[bg{i}][fg{i}]")
    segs.append(f"[bg{i}]{crop_expr(0.5, 0.5, 1.0)},scale={W}:{H}:flags=bicubic,"
                f"gblur=sigma={26 * k:.1f},eq=brightness=-0.10:saturation=0.9[bgb{i}]")
    segs.append(f"[fg{i}]{crop_expr(cx, cy, z, asp)},scale={fw}:{fh}:flags=lanczos[fgs{i}]")
    segs.append(f"[bgb{i}][fgs{i}]overlay={(W - fw) // 2}:{(H - fh) // 2}:format=auto[m{i}]")
    head = f"[m{i}]"
  else:
    cx, cy, z = c["crop"]
    head = vin
    f += [crop_expr(cx, cy, z), f"scale={W}:{H}:flags=lanczos"]
  f.append("setsar=1")
  if sp < 1:
    f.append(f"setpts=(PTS-STARTPTS)/{sp},{MINT}")
  else:
    f.append(f"setpts=(PTS-STARTPTS)/{sp},fps={FPS}")
  amp = c["shake"] * k
  if amp:
    f.append(f"scale=w='2*trunc({W}*1.03/2)':h='2*trunc({H}*1.03/2)':flags=bicubic")
    f.append(f"crop={W}:{H}:x='(iw-{W})/2+{amp:.1f}*sin(t*97)':y='(ih-{H})/2+{amp * 0.8:.1f}*cos(t*73)'")
  f.append(f"tpad=stop=6:stop_mode=clone,trim=end_frame={n},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[c{i}]")
  segs.append(head + ",".join(f))
  return segs

def audio_chain(i, c):
  n, sp = c["n"], c["speed"]
  dsrc = n * sp / FPS
  dur = n / FPS
  a = [f"[{i}:a]atrim=0:{dsrc:.4f},asetpts=PTS-STARTPTS"]
  if abs(sp - 1) > 1e-6:
    a.append(f"atempo={sp}")
  a.append(f"volume={c['audio']}")
  a.append(f"afade=t=in:st=0:d=0.08,afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08")
  a.append("aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")
  a.append(f"apad,atrim=duration={dur:.4f},asetpts=PTS-STARTPTS[a{i}]")
  return ",".join(a)

def build(out, preview=False):
  W, H = (540, 960) if preview else (1080, 1920)
  k = W / 1080
  src = SRC_LRF if preview else SRC
  inputs, segs = [], []
  for i, c in enumerate(CUTS):
    n, sp = c["n"], c["speed"]
    dsrc = n * sp / FPS
    inputs += ["-ss", f"{c['start']:.3f}", "-t", f"{dsrc + (0.15 if sp < 1 else 0.06):.3f}", "-i", src[c["src"]]]
    segs += video_chain(i, c, W, H, k)
    segs.append(audio_chain(i, c))
  n_in = len(CUTS)
  inputs += ["-framerate", str(FPS), "-i", os.path.join(HERE, "ov", "%04d.png")]
  grade = GRADE
  pairs = "".join(f"[c{i}][a{i}]" for i in range(n_in))
  segs.append(f"{pairs}concat=n={n_in}:v=1:a=1[vc][ac]")
  segs.append(f"[vc]setpts=N/({FPS}*TB),{grade}[base]")
  segs.append(f"[ac]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,afade=t=out:st={FADE_ST}:d={FADE_D}[aout]")
  segs.append(f"[{n_in}:v]scale={W}:{H}:flags=lanczos[ov]" if preview else f"[{n_in}:v]null[ov]")
  segs.append(f"[base][ov]overlay=0:0:format=auto:eof_action=pass,fade=t=out:st={FADE_ST}:d={FADE_D},format=yuv420p[v]")
  fc = ";".join(segs)
  enc = (["-c:v", "libx264", "-crf", "24", "-preset", "veryfast"] if preview
         else ["-c:v", "libx264", "-crf", "18", "-preset", "slow"])
  cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats", *inputs,
         "-filter_complex", fc, "-map", "[v]", "-map", "[aout]", *enc, "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-t", f"{TOTAL_SEC:.3f}", out]
  with open(os.path.join(HERE, "last_cmd.txt"), "w") as fh:
    fh.write(" ".join(f"'{a}'" if " " in a or ";" in a else a for a in cmd))
  print(f"프레임 {TOTAL_FRAMES} = {TOTAL_SEC:.2f}s · 입력 {n_in}개 · {'PREVIEW' if preview else 'MASTER'} → {out}", flush=True)
  subprocess.run(cmd, check=True)

if __name__ == "__main__":
  a = sys.argv[1:]
  build(a[0], preview="--preview" in a)
