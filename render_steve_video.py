# -*- coding: utf-8 -*-
"""
render_steve_video.py — Motor Oficial de Video Promocional Rey Steve / Minecraft Gratis (FeatherTalk ONNX + ElevenLabs v4)
==========================================================================================================================
- Sin cortinilla de inicio (`logo_intro` omitido): entra directo al Rey Steve 3D sobre el fondo del Salón del Trono
  (`characters/03_steve/throne_bg.jpg`).
- Lip-Sync Neuronal Continuo (`FeatherTalk 144x144` + `FeatherHuBERT` en ONNX) en `characters/03_steve/feathertalk_onnx`.
- Voz generada con ElevenLabs API (`eleven_v4`, voz heroica masculina `TX3LPaxmHKxFdv7VOQHJ`) con ecualización brillante
  (sin compresión opaca) y música de fondo `Hero Power (Instrumental).wav`.
- Capturas móviles en TIEMPO REAL 1.0x (24 FPS exactos cuadro a cuadro, sin acelerar):
  1) Últimos 2 golpes críticos contra el Enderman y desbloqueo (`gameplay`)
  2) Recorrido completo de la invitación de Minecraft desbloqueada (`unlocked`)
  3) Dónde encontrarla en `dreamcrafters.lat` (`website`) con Box Blur central + Barra de Navegación tipeando
     letra por letra `dreamcrafters.lat` para que todos lean cómo se escribe.
"""

import os
import glob
import math
import json
import wave
import shutil
import hashlib
import argparse
import subprocess
import urllib.request
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHAR_03_DIR = os.path.join(REPO_ROOT, "characters", "03_steve")
CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
FEATHERTALK_ONNX_DIR = os.path.join(CHAR_03_DIR, "feathertalk_onnx")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
REAL_CAP_DIR = os.path.join(CHAR_03_DIR, "out", "real_mobile_capture")
THRONE_BG_PATH = os.path.join(CHAR_03_DIR, "throne_bg.jpg")
BGM_PATH = os.path.join(CHAR_03_DIR, "hero_power_bgm.wav")

ELEVENLABS_KEYS = [
    os.environ.get("ELEVENLABS_API_KEY", ""),
    "sk_23049c20908c037dcaacd577ec4524ad4ef9674756d8f67c",
    "sk_7a19a6c786e6ce5b518337ad562c31bb673e61403c048c3b",
    "sk_9518cdd9e61bdf93f3e9d2ad8f129c455c108cf487881505",
]
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "EUc6JnHerYSN3cTUss3Q")
ELEVENLABS_MODEL_ID = "eleven_v4"

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)

SCENES_STEVE = [
    {
        "type": "hook",
        "accent_rgb": (74, 222, 128),
        "bottom_pill": "¡INVITACIÓN MINECRAFT 100% GRATIS!",
        "voice_text": "¡Saludos, aventureros! Como soy un rey muy generoso, en Drim Crafters te tenemos una gran sorpresa: ¡crea totalmente gratis tu invitación interactiva con estilo de Maincraft!",
    },
    {
        "type": "gameplay",
        "accent_rgb": (192, 132, 252),
        "bottom_pill": "DERROTA AL ENDERMAN PARA ENTRAR",
        "voice_text": "¡Mira! Tus invitados entran desde su celular y derrotan al Enderman a espadazos para desbloquear tu fiesta.",
    },
    {
        "type": "unlocked",
        "accent_rgb": (74, 222, 128),
        "bottom_pill": "MÚSICA + MAPA GPS + WHATSAPP",
        "voice_text": "Al vencerlo, recorren toda tu invitación con música épica, cuenta regresiva, mapa en Gúgol Maps y confirmación directa a tu Guatsap.",
    },
    {
        "type": "website",
        "accent_rgb": (56, 189, 248),
        "bottom_pill": "ESCRIBE: DREAMCRAFTERS.LAT",
        "voice_text": "¿Dónde la encuentras? Escribe en tu navegador drim crafters punto lat, toca el botón verde de Crear invitación gratis y obtén tu enlace al instante.",
    },
    {
        "type": "cta",
        "accent_rgb": (250, 204, 21),
        "bottom_pill": "VISITA HOY DREAMCRAFTERS.LAT",
        "voice_text": "¡Haz tu fiesta épica hoy mismo! Te esperamos en drim crafters punto lat. ¡Drim Crafters, artificialmente hechos a mano!",
    },
]


def resolve_ffmpeg_path():
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _trim_silence_pcm(pcm, sr=24000):
    fl = pcm.astype(np.float32) / 32768.0
    win = int(0.02 * sr)
    active = [i for i in range(0, len(fl) - win, win) if np.sqrt(np.mean(fl[i : i + win] ** 2)) > 0.008]
    if not active:
        return pcm
    s_idx = max(0, active[0] - int(0.04 * sr))
    e_idx = min(len(pcm), active[-1] + win + int(0.06 * sr))
    out = pcm[s_idx:e_idx].copy()
    fade = int(0.015 * sr)
    if len(out) > fade * 2:
        out[:fade] = (out[:fade].astype(np.float32) * np.linspace(0, 1, fade)).astype(np.int16)
        out[-fade:] = (out[-fade:].astype(np.float32) * np.linspace(1, 0, fade)).astype(np.int16)
    return out


def _pick_working_elevenlabs_key():
    for k in ELEVENLABS_KEYS:
        k = (k or "").strip()
        if not k:
            continue
        try:
            req = urllib.request.Request(
                "https://api.elevenlabs.io/v1/user/subscription",
                headers={"xi-api-key": k},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
                rem = int(data.get("character_limit", 0)) - int(data.get("character_count", 0))
                if rem > 450:
                    print(f"[ElevenLabs] Usando key {k[:12]}... (saldo disponible: {rem} chars)")
                    return k
        except Exception:
            pass
    raise RuntimeError("No se encontró ninguna key de ElevenLabs con saldo suficiente.")


def synthesize_elevenlabs_scenes(scenes, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Genera la voz del Rey Steve usando ElevenLabs API (`eleven_v4`, brillante y clara, sin cortinilla de inicio).
    Guarda caché por escena en `characters/03_steve/out/elevenlabs_voice_cache`.
    """
    cache_dir = os.path.join(CHAR_03_DIR, "out", "elevenlabs_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.20 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []
    api_key = None

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"elevenlabs_steve_v4_bright|{ELEVENLABS_VOICE_ID}|{ELEVENLABS_MODEL_ID}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"steve_v4_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav):
            if api_key is None:
                api_key = _pick_working_elevenlabs_key()
            print(f"[ElevenLabs {ELEVENLABS_MODEL_ID}] Generando voz brillante del Rey Steve para Escena {idx+1}...")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"
            payload = json.dumps(
                {
                    "text": v_text,
                    "model_id": ELEVENLABS_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.38,
                        "similarity_boost": 0.85,
                        "style": 0.52,
                        "use_speaker_boost": True,
                    },
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                method="POST",
            )
            raw_mp3 = os.path.join(cache_dir, f"_tmp_sc_{idx+1}.mp3")
            raw_wav = os.path.join(cache_dir, f"_tmp_sc_{idx+1}.wav")
            with urllib.request.urlopen(req, timeout=35) as resp:
                with open(raw_mp3, "wb") as f_mp3:
                    f_mp3.write(resp.read())

            # Ecualización con presencia cristalina en 3.5kHz y aire en 7.5kHz (sin compresor que apague la voz)
            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    raw_mp3,
                    "-af",
                    "highpass=f=75,equalizer=f=3600:width_type=o:width=1.4:g=3.8,equalizer=f=7500:width_type=o:width=1.5:g=2.8,loudnorm=I=-12.5:TP=-0.8:LRA=8",
                    "-ac",
                    "1",
                    "-ar",
                    str(sr),
                    "-c:a",
                    "pcm_s16le",
                    raw_wav,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with wave.open(raw_wav, "rb") as wf_r:
                raw_pcm = np.frombuffer(wf_r.readframes(wf_r.getnframes()), dtype=np.int16).copy()
            trimmed_pcm = _trim_silence_pcm(raw_pcm, sr=sr)
            with wave.open(cached_wav, "wb") as wf_w:
                wf_w.setnchannels(1)
                wf_w.setsampwidth(2)
                wf_w.setframerate(sr)
                wf_w.writeframes(trimmed_pcm.tobytes())
            for tmp_f in (raw_mp3, raw_wav):
                if os.path.exists(tmp_f):
                    os.remove(tmp_f)

        with wave.open(cached_wav, "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

        dur = len(pcm) / float(sr)
        sc_copy = dict(sc)
        sc_copy["start"] = round(cur_time, 3)
        sc_copy["audio_duration"] = round(dur, 3)

        all_pcm.append(pcm)
        if idx < len(scenes) - 1:
            all_pcm.append(pause_samples)
            sc_copy["end"] = round(cur_time + dur + 0.20, 3)
            cur_time += dur + 0.20
        else:
            all_pcm.append(tail_samples)
            sc_copy["end"] = round(cur_time + dur + 0.45, 3)
            cur_time += dur + 0.45

        updated_scenes.append(sc_copy)

    full_pcm = np.concatenate(all_pcm)
    with wave.open(output_wav_path, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(sr)
        wf_out.writeframes(full_pcm.tobytes())

    return updated_scenes


def mix_voice_with_bgm(voice_wav_path, bgm_path, output_wav_path, bgm_vol=0.11, ffmpeg_path="ffmpeg"):
    if not bgm_path or not os.path.exists(bgm_path):
        shutil.copyfile(voice_wav_path, output_wav_path)
        return output_wav_path

    filter_complex = (
        f"[0:a]volume=1.18[v];"
        f"[1:a]volume={bgm_vol:.3f},aloop=loop=-1:size=2e+09[b];"
        f"[v][b]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.97[out]"
    )
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            voice_wav_path,
            "-i",
            bgm_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            output_wav_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_wav_path


def load_pil_rgba(path, size=None):
    if not path or not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    if size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    return img


def get_font(size, bold=True, mono=False):
    candidates = []
    if mono:
        candidates = [
            os.path.join(CHAR_02_DIR, "assets", "ShareTechMono-Regular.ttf"),
            r"C:\Windows\Fonts\consolab.ttf",
        ]
    elif bold:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _crop_face(image: np.ndarray, bbox: tuple[int, int, int, int], crop_size: int = FACE_CROP_SIZE) -> np.ndarray:
    xmin, ymin, xmax, ymax = bbox
    return cv2.resize(image[ymin:ymax, xmin:xmax], (crop_size, crop_size), interpolation=cv2.INTER_AREA)


def _extract_inner(face_crop: np.ndarray, inner_size: int = FACE_INNER_SIZE) -> np.ndarray:
    return face_crop[
        FACE_BORDER : FACE_BORDER + inner_size,
        FACE_BORDER : FACE_BORDER + inner_size,
    ].copy()


def _mask_mouth(image: np.ndarray, inner_size: int = FACE_INNER_SIZE) -> np.ndarray:
    scale = inner_size / float(GEOMETRY_BASE_SIZE)
    x, y, width, height = MASK_RECT
    rect = (
        round(x * scale),
        round(y * scale),
        round(width * scale),
        round(height * scale),
    )
    return cv2.rectangle(image, rect, (0, 0, 0), -1)


def _key_steve_green_screen(bgr: np.ndarray) -> Image.Image:
    b = bgr[:, :, 0].astype(np.float32)
    g = bgr[:, :, 1].astype(np.float32)
    r = bgr[:, :, 2].astype(np.float32)
    max_rb = np.maximum(r, b)
    excess = g - max_rb
    alpha = np.clip((62.0 - excess) / 38.0, 0.0, 1.0)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.65)
    g_despilled = np.where(excess > 0.0, max_rb + np.minimum(excess, 5.0), g)
    rgba = np.stack(
        [
            np.clip(r, 0, 255).astype(np.uint8),
            np.clip(g_despilled, 0, 255).astype(np.uint8),
            np.clip(b, 0, 255).astype(np.uint8),
            np.clip(alpha * 255.0, 0, 255).astype(np.uint8),
        ],
        axis=2,
    )
    return Image.fromarray(rgba, mode="RGBA")


class FeatherTalkSteveEngine:
    def __init__(self, onnx_dir: str, voice_wav_path: str, fps: int = 24, ffmpeg_path: str = "ffmpeg"):
        import onnxruntime as ort

        self.onnx_dir = onnx_dir
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path

        hubert_path = os.path.join(onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(onnx_dir, "closed_win.npy")
        video_path = os.path.join(onnx_dir, "steve_25fps.mp4")
        ref_0_path = os.path.join(onnx_dir, "ref_0.jpg")

        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 4
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.hubert_sess = ort.InferenceSession(hubert_path, sess_options=sess_opts, providers=["CPUExecutionProvider"])
        self.ft_sess = ort.InferenceSession(ft_path, sess_options=sess_opts, providers=["CPUExecutionProvider"])
        self.bboxes = np.load(bboxes_path)
        self.closed_win = np.load(closed_win_path).astype(np.float32)

        self.base_frames = []
        cap = cv2.VideoCapture(video_path)
        while True:
            ret, frm = cap.read()
            if not ret:
                break
            self.base_frames.append(frm)
        cap.release()

        ref_img = cv2.imread(ref_0_path) if os.path.exists(ref_0_path) else self.base_frames[0]
        ref_crop = _crop_face(ref_img, tuple(self.bboxes[0]), crop_size=FACE_CROP_SIZE)
        self.ref_inner = _extract_inner(ref_crop, inner_size=FACE_INNER_SIZE)

        base_seq = list(range(0, len(self.base_frames)))
        self.ping_pong = base_seq + base_seq[-2:0:-1]
        self.pp_cursor = 0

        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[18:108, 14:130] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (21, 21), 5.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio(voice_wav_path, fps=fps)

    def _analyze_audio(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k_steve.wav"
        subprocess.run(
            [
                self.ffmpeg_path,
                "-y",
                "-i",
                voice_wav_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                tmp_16k,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with wave.open(tmp_16k, "rb") as wf:
                pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            wav_f = pcm.astype(np.float32) / 32768.0
        finally:
            if os.path.exists(tmp_16k):
                os.remove(tmp_16k)

        sr = 16000
        dur_sec = len(wav_f) / float(sr)
        total_frames = int(round(dur_sec * fps))

        rms_arr = np.zeros(total_frames, dtype=np.float32)
        win_samples = int(0.05 * sr)
        for i in range(total_frames):
            c_idx = int((i / float(fps)) * sr)
            s_i = max(0, c_idx - win_samples // 2)
            e_i = min(len(wav_f), c_idx + win_samples // 2)
            if e_i > s_i:
                rms_arr[i] = float(np.sqrt(np.mean(wav_f[s_i:e_i] ** 2)))

        pad_16k = np.zeros(int(0.5 * sr), dtype=np.float32)
        wav_norm_global = (wav_f - wav_f.mean()) / np.sqrt(wav_f.var() + 1e-7)
        wav_padded = np.concatenate([pad_16k, wav_norm_global, pad_16k]).astype(np.float32)

        in_name = self.hubert_sess.get_inputs()[0].name
        chunk_samples = sr * 20
        overlap_samples = sr * 1

        if len(wav_padded) <= chunk_samples:
            hu_out = self.hubert_sess.run(None, {in_name: wav_padded[None, :]})[0][0]
        else:
            chunks_out = []
            pos = 0
            while pos < len(wav_padded):
                end = min(len(wav_padded), pos + chunk_samples)
                seg = wav_padded[pos:end]
                seg = (seg - seg.mean()) / np.sqrt(seg.var() + 1e-7)
                f_seg = self.hubert_sess.run(None, {in_name: seg.astype(np.float32)[None, :]})[0][0]
                if pos == 0:
                    chunks_out.append(f_seg)
                else:
                    chunks_out.append(f_seg[50:])
                if end >= len(wav_padded):
                    break
                pos = end - overlap_samples
            hu_out = np.concatenate(chunks_out, axis=0)

        if hu_out.shape[0] % 2 != 0:
            hu_out = hu_out[:-1]
        feats_25 = hu_out.reshape(-1, 2, 1024).astype(np.float32)
        return feats_25, rms_arr, total_frames

    def synthesize_steve_rgba(self, frame_idx: int) -> tuple[Image.Image, float]:
        t_sec = frame_idx / float(self.fps)
        rms_val = float(self.rms_24fps[min(frame_idx, len(self.rms_24fps) - 1)])
        is_silent = rms_val < 0.010

        bg_idx = self.ping_pong[self.pp_cursor % len(self.ping_pong)]
        self.pp_cursor += 1

        if is_silent:
            aud_in = self.closed_win
        else:
            idx_25 = int(round(t_sec * 25.0))
            center = min(max(10, idx_25 + 12), self.feats_25.shape[0] - 10)
            aud_win = self.feats_25[center - 10 : center + 10]
            aud_in = aud_win.reshape(1, 40, 1024).astype(np.float32)

        frame_bgr = self.base_frames[bg_idx].copy()
        xmin, ymin, xmax, ymax = [int(v) for v in self.bboxes[bg_idx]]

        crop_152 = _crop_face(frame_bgr, (xmin, ymin, xmax, ymax), crop_size=FACE_CROP_SIZE)
        inner = _extract_inner(crop_152, inner_size=FACE_INNER_SIZE)
        reference = inner.copy()
        masked = _mask_mouth(inner.copy(), inner_size=FACE_INNER_SIZE)

        inp_chw = np.concatenate([reference, masked], axis=2).transpose(2, 0, 1).astype(np.float32) / 255.0
        inp_chw = inp_chw[None, ...]

        pred = self.ft_sess.run(None, {"input": inp_chw, "audio": aud_in})[0][0]
        pred_bgr = np.clip(pred.transpose(1, 2, 0) * 255.0, 0.0, 255.0).astype(np.float32)

        blended_inner = (pred_bgr * self.mask_alpha + inner.astype(np.float32) * (1.0 - self.mask_alpha)).astype(np.uint8)
        b = FACE_BORDER
        crop_152[b : b + FACE_INNER_SIZE, b : b + FACE_INNER_SIZE] = blended_inner
        frame_bgr[ymin:ymax, xmin:xmax] = cv2.resize(
            crop_152, (xmax - xmin, ymax - ymin), interpolation=cv2.INTER_LANCZOS4
        )

        steve_rgba = _key_steve_green_screen(frame_bgr)
        return steve_rgba, rms_val


class SteveCommercialRenderer:
    def __init__(self, ft_engine: FeatherTalkSteveEngine):
        self.ft = ft_engine
        self.W = 720
        self.H = 1280

        self.throne_bg = load_pil_rgba(THRONE_BG_PATH, (self.W, self.H))
        if self.throne_bg is None:
            self.throne_bg = Image.new("RGBA", (self.W, self.H), (18, 16, 22, 255))

        d_icon_path = os.path.join(CHAR_02_DIR, "out", "real_mobile_capture", "d_icon_hd.png")
        self.d_icon_hd = load_pil_rgba(d_icon_path)
        self.d_icon_header = load_pil_rgba(d_icon_path, (54, 56))

        raw_logo = load_pil_rgba(os.path.join(LANDING_DIR, "logo-text.png"))
        if raw_logo:
            _, _, _, a_c = raw_logo.split()
            white_rgb = Image.new("RGB", raw_logo.size, (250, 246, 238))
            self.logo_text = Image.merge("RGBA", (*white_rgb.split(), a_c))
        else:
            self.logo_text = None

        self.gameplay_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "gameplay", "frame_*.png")))
        self.unlocked_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "unlocked", "frame_*.png")))
        self.website_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "website", "frame_*.png")))
        print(
            f"Frames móviles 1.0x reales cargados (720x1280): gameplay={len(self.gameplay_frames)}, "
            f"unlocked={len(self.unlocked_frames)}, website={len(self.website_frames)}"
        )

        self.f_pill = get_font(20, bold=True)
        self.f_url = get_font(18, mono=True)
        self.f_intro_sub = get_font(21, bold=True, mono=True)
        self.f_nav_label = get_font(19, bold=True)
        self.f_nav_url = get_font(33, bold=True, mono=True)
        self.f_nav_hint = get_font(17, bold=False)

    def _draw_floor_contact_shadow(self, canvas, cx, boot_y, rx, ry, alpha=155):
        shadow = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((cx - rx, boot_y - ry, cx + rx, boot_y + ry), fill=(8, 6, 4, alpha))
        sd.ellipse(
            (cx - int(rx * 0.65), boot_y - int(ry * 0.65), cx + int(rx * 0.65), boot_y + int(ry * 0.65)),
            fill=(4, 3, 2, int(alpha * 0.78)),
        )
        canvas.alpha_composite(shadow)

    def render_fullscreen_invitation_realtime(self, scene_type, local_frame_idx):
        """Reproduce los cuadros capturados a 24 FPS exactamente en relación 1:1 (velocidad 1.0x real, sin acelerar)."""
        if scene_type == "gameplay" and self.gameplay_frames:
            f_idx = min(len(self.gameplay_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.gameplay_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "unlocked" and self.unlocked_frames:
            f_idx = min(len(self.unlocked_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.unlocked_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "website" and self.website_frames:
            f_idx = min(len(self.website_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.website_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        return self.throne_bg.copy()

    def _overlay_typing_browser_box(self, canvas: Image.Image, t_in_sc: float, sc_dur: float) -> Image.Image:
        """
        Dibuja un Box Blur (frosted glass) en el centro de la pantalla con una barra de navegación
        tipeando letra por letra `dreamcrafters.lat` durante los primeros 3.6 segundos de la escena `website`,
        y luego hace fade-out suave para dejar ver el formulario gratuito en vivo.
        """
        show_until = min(3.75, sc_dur * 0.56)
        if t_in_sc > show_until:
            return canvas

        # Calcular opacidad de entrada/salida
        if t_in_sc < 0.22:
            alpha_u = t_in_sc / 0.22
        elif t_in_sc > show_until - 0.38:
            alpha_u = max(0.0, (show_until - t_in_sc) / 0.38)
        else:
            alpha_u = 1.0

        if alpha_u <= 0.02:
            return canvas

        target_text = "dreamcrafters.lat"
        # Tipear letra por letra entre t=0.20s y t=2.05s
        type_prog = min(1.0, max(0.0, (t_in_sc - 0.20) / 1.85))
        n_chars = int(round(type_prog * len(target_text)))
        typed_str = target_text[:n_chars]
        is_complete = n_chars >= len(target_text)

        # Región central para el Box Blur (x=28..692, y=460..760)
        bx0, by0, bx1, by1 = 28, 465, self.W - 28, 755
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=18))

        glass_card = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass_card.paste(crop_region, (0, 0))
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (10, 14, 22, int(218 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        # Aplicar máscara redondeada al Box Blur
        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (74, 222, 128, int(245 * alpha_u)) if is_complete else (56, 189, 248, int(235 * alpha_u))
        od.rounded_rectangle((bx0, by0, bx1, by1), radius=32, outline=border_col, width=3)

        # Etiqueta superior
        od.text(
            (self.W // 2, by0 + 42),
            "ESCRIBE EN TU NAVEGADOR:",
            font=self.f_nav_label,
            fill=(190, 205, 225, int(245 * alpha_u)),
            anchor="mm",
        )

        # Barra de direcciones interna
        bar_x0, bar_y0, bar_x1, bar_y1 = bx0 + 26, by0 + 78, bx1 - 26, by0 + 178
        od.rounded_rectangle(
            (bar_x0, bar_y0, bar_x1, bar_y1),
            radius=22,
            fill=(6, 9, 14, int(248 * alpha_u)),
            outline=border_col,
            width=2,
        )

        # Ícono de lupa / candado a la izquierda
        icon_cx, icon_cy = bar_x0 + 44, (bar_y0 + bar_y1) // 2
        od.ellipse(
            (icon_cx - 13, icon_cy - 13, icon_cx + 9, icon_cy + 9),
            outline=(74, 222, 128, int(245 * alpha_u)),
            width=3,
        )
        od.line(
            [(icon_cx + 6, icon_cy + 6), (icon_cx + 16, icon_cy + 16)],
            fill=(74, 222, 128, int(245 * alpha_u)),
            width=3,
        )

        # Texto tipeado + cursor parpadeante
        cursor_on = (not is_complete) or (int(t_in_sc * 6) % 2 == 0)
        display_url = typed_str + ("|" if cursor_on and not is_complete else "")
        text_col = (74, 222, 128, int(255 * alpha_u)) if is_complete else (250, 246, 238, int(255 * alpha_u))
        od.text(
            (bar_x0 + 82, (bar_y0 + bar_y1) // 2),
            display_url,
            font=self.f_nav_url,
            fill=text_col,
            anchor="lm",
        )

        # Badge derecho "IR" cuando termina de tipear
        if is_complete:
            go_x0, go_y0, go_x1, go_y1 = bar_x1 - 92, bar_y0 + 18, bar_x1 - 18, bar_y1 - 18
            od.rounded_rectangle(
                (go_x0, go_y0, go_x1, go_y1),
                radius=14,
                fill=(74, 222, 128, int(250 * alpha_u)),
            )
            od.text(
                ((go_x0 + go_x1) // 2, (go_y0 + go_y1) // 2),
                "IR →",
                font=self.f_nav_label,
                fill=(8, 20, 12, int(255 * alpha_u)),
                anchor="mm",
            )

        od.text(
            (self.W // 2, by1 - 42),
            "¡Crea tu invitación de Minecraft 100% gratis!",
            font=self.f_nav_hint,
            fill=(74, 222, 128, int(245 * alpha_u)),
            anchor="mm",
        )

        out.alpha_composite(ov)
        return out

    def render_logo_outro_frame(self, outro_prog):
        base = self.throne_bg.copy()
        dark_overlay = Image.new("RGBA", (self.W, self.H), (8, 10, 14, int(215 * min(1.0, outro_prog * 1.8))))
        canvas = Image.alpha_composite(base, dark_overlay)

        halo_alpha = int(145 * min(1.0, outro_prog * 2.2))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(185 + 40 * math.sin(outro_prog * math.pi * 2.0))
            cx, cy = self.W // 2, self.H // 2 - 55
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(74, 222, 128, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(56, 189, 248, halo_alpha // 4))
            canvas.alpha_composite(halo)

        if self.d_icon_hd:
            if outro_prog < 0.28:
                u = outro_prog / 0.28
                c1 = 1.70158
                c3 = c1 + 1.0
                scale = 0.18 + 0.84 * (1.0 + c3 * ((u - 1.0) ** 3) + c1 * ((u - 1.0) ** 2))
                cx = int((1.0 - u) * 59 + u * (self.W // 2))
                cy = int((1.0 - u) * 56 + u * (self.H // 2 - 55))
            else:
                scale = 1.02 + 0.03 * math.sin((outro_prog - 0.28) * 8.0)
                cx, cy = self.W // 2, self.H // 2 - 55

            target_w = max(48, int(330 * scale))
            target_h = max(50, int(340 * scale))
            d_img = self.d_icon_hd.resize((target_w, target_h), Image.Resampling.LANCZOS)
            canvas.alpha_composite(d_img, (cx - target_w // 2, cy - target_h // 2))

        txt_alpha = min(1.0, max(0.0, (outro_prog - 0.12) / 0.20))
        if txt_alpha > 0.04:
            if self.logo_text:
                lw, lh = self.logo_text.size
                th = 58
                tw = int(lw * (th / float(lh)))
                lt_resized = self.logo_text.resize((tw, th), Image.Resampling.LANCZOS)
                r, g, b, a = lt_resized.split()
                a = a.point(lambda p: int(p * txt_alpha))
                lt_faded = Image.merge("RGBA", (r, g, b, a))
                canvas.alpha_composite(lt_faded, ((self.W - tw) // 2, self.H // 2 + 148))

            txt_overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            tod = ImageDraw.Draw(txt_overlay)
            tod.text(
                (self.W // 2, self.H // 2 + 236),
                "INVITACIÓN MINECRAFT GRATIS",
                font=self.f_intro_sub,
                fill=(74, 222, 128, int(245 * txt_alpha)),
                anchor="mm",
            )
            pill_y0, pill_y1 = self.H - 126, self.H - 34
            tod.rounded_rectangle(
                (32, pill_y0, self.W - 32, pill_y1),
                radius=24,
                fill=(15, 19, 26, int(240 * txt_alpha)),
                outline=(74, 222, 128, int(215 * txt_alpha)),
                width=2,
            )
            tod.text(
                (self.W // 2, pill_y0 + 30),
                "CRÉALA GRATIS EN DREAMCRAFTERS.LAT",
                font=self.f_pill,
                fill=(74, 222, 128, int(255 * txt_alpha)),
                anchor="mm",
            )
            tod.text(
                (self.W // 2, pill_y0 + 64),
                ">> DREAMCRAFTERS.LAT <<",
                font=self.f_url,
                fill=(250, 246, 238, int(255 * txt_alpha)),
                anchor="mm",
            )
            canvas.alpha_composite(txt_overlay)

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def render_frame(self, idx, total_frames, fps, scene_info):
        sc = scene_info["scene"]
        sc_prog = scene_info["progress"]
        sc_type = sc["type"]
        sc_dur = max(0.1, sc["end"] - sc["start"])
        t_in_sc = (idx / float(fps)) - sc["start"]
        local_frame_idx = max(0, int(round(t_in_sc * fps)))

        if sc_type == "cta":
            ending_logo_start_sec = max(2.6, sc_dur - 2.5)
            if t_in_sc >= ending_logo_start_sec:
                outro_prog = min(1.0, (t_in_sc - ending_logo_start_sec) / max(0.1, sc_dur - ending_logo_start_sec))
                return self.render_logo_outro_frame(outro_prog)

        # ESCENAS GAMEPLAY / UNLOCKED / WEBSITE -> PANTALLA COMPLETA EN TIEMPO REAL 1.0x
        if sc_type in ("gameplay", "unlocked", "website"):
            canvas = self.render_fullscreen_invitation_realtime(sc_type, local_frame_idx)
            if sc_type == "website":
                canvas = self._overlay_typing_browser_box(canvas, t_in_sc, sc_dur)
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Rey Steve 3D sobre el Salón del Trono
        accent = sc["accent_rgb"]
        canvas = self.throne_bg.copy()

        steve_rgba, _ = self.ft.synthesize_steve_rgba(idx)
        self._draw_floor_contact_shadow(canvas, self.W // 2, 1142, rx=185, ry=24, alpha=165)
        canvas.alpha_composite(steve_rgba, (0, 0))

        grad = Image.new("RGBA", (self.W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(215 * ((gy / 240.0) ** 1.5))
            gd.line([(0, gy), (self.W, gy)], fill=(8, 10, 16, alpha_g))
        canvas.alpha_composite(grad, (0, self.H - 240))

        cd = ImageDraw.Draw(canvas)
        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (32, 28))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 34
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (98, 40))

        pill_y0, pill_y1 = self.H - 126, self.H - 34
        cd.rounded_rectangle(
            (32, pill_y0, self.W - 32, pill_y1),
            radius=24,
            fill=(15, 19, 26, 240),
            outline=accent + (215,),
            width=2,
        )
        cd.text((self.W // 2, pill_y0 + 30), sc["bottom_pill"], font=self.f_pill, fill=accent, anchor="mm")
        cd.text((self.W // 2, pill_y0 + 64), ">> DREAMCRAFTERS.LAT <<", font=self.f_url, fill=(250, 246, 238), anchor="mm")

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.path.join(REPO_ROOT, "out", "video_final_rey_steve_minecraft.mp4"))
    args = parser.parse_args()

    ffmpeg_path = resolve_ffmpeg_path()
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "steve_elevenlabs_v4_voice.wav")

    print("Generando narración del Rey Steve con ElevenLabs v4 (voz brillante y clara)...")
    scenes = synthesize_elevenlabs_scenes(SCENES_STEVE, clean_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    print("Inicializando motor FeatherTalk ONNX 144x144 para el Rey Steve 3D...")
    ft_engine = FeatherTalkSteveEngine(FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)

    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} frames ({total_frames/fps:.1f}s) a velocidad 1.0x real + Box Blur navegador...")

    renderer = SteveCommercialRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_visual_steve.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(temp_video, fourcc, fps, (720, 1280))

    for i in range(total_frames):
        t_sec = i / float(fps)
        active_sc = scenes[-1]
        for sc in scenes:
            if sc["start"] <= t_sec <= sc["end"]:
                active_sc = sc
                break
        dur = max(0.1, active_sc["end"] - active_sc["start"])
        prog = np.clip((t_sec - active_sc["start"]) / dur, 0.0, 1.0)

        bgr = renderer.render_frame(i, total_frames, fps, {"scene": active_sc, "progress": prog})
        vw.write(bgr)

    vw.release()

    mixed_wav = os.path.join(out_dir, "steve_elevenlabs_v4_mixed.wav")
    final_audio = mix_voice_with_bgm(clean_wav, BGM_PATH, mixed_wav, bgm_vol=0.11, ffmpeg_path=ffmpeg_path)

    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            temp_video,
            "-i",
            final_audio,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            args.output,
        ],
        check=True,
    )
    if os.path.exists(temp_video):
        os.remove(temp_video)

    videos_dir = os.path.join(REPO_ROOT, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    published_copy = os.path.join(videos_dir, "02_rey_steve_minecraft_gratis.mp4")
    if os.path.abspath(args.output) != os.path.abspath(published_copy):
        shutil.copyfile(args.output, published_copy)

    print(f"Video promocional v2 del Rey Steve finalizado con éxito: {args.output}")


if __name__ == "__main__":
    main()
