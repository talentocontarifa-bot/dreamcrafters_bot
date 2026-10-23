# -*- coding: utf-8 -*-
"""
render_posada_santa_promo.py — Comercial Oficial Posada Navideña + Saludo de Santa + Amigo Secreto
==================================================================================================
- Entrada directa en el cuadro 0 con Santa Claus 3D (FeatherTalk ONNX 144x144 + FeatherHuBERT) sobre
  el escenario nevado del Polo Norte (`fondo_polo_norte.webp`) con copos de nieve + destellos dorados.
- Narración navideña con ElevenLabs `eleven_v4` (`nPczCjzI2devNBz1zQrb`) mezclada con
  `Rocking Christmas Cover.mp3` (`rocking_christmas.mp3`) a volumen suave (13%).
- Capturas móviles en TIEMPO REAL 1.0x (24 FPS exactos cuadro a cuadro) + PiP de Santa 3D hablando:
  1) `hero_video`: Titulares editables (Posada Familia Jiménez -> Gran Posada Refacciones Azur) +
     Santa bailando + Saludo Navideño Personalizado de Santa en Video.
  2) `secret_santa`: Gestor de Amigo Secreto con PIN de 4 dígitos + Tarjeta Dorada Rasca y Gana
     en vivo + Modo Organizador enviando pases cifrados por WhatsApp en 1 clic.
  3) `rsvp_website`: Mapa GPS + Pase de Abordaje VIP Polo Norte Express (`POSADA-2026-VIP`) +
     barra de navegador con Box Blur tipeando `dreamcrafters.lat`.
"""

import os
import sys
import glob
import json
import math
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
CHAR_04_DIR = os.path.join(REPO_ROOT, "characters", "04_santa")
CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
FEATHERTALK_ONNX_DIR = os.path.join(CHAR_04_DIR, "feathertalk_onnx")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
POSADA_WEB_DIR = os.path.abspath(os.path.join(REPO_ROOT, "..", "invitacion-posada-santa"))
REAL_CAP_DIR = os.path.join(CHAR_04_DIR, "out", "real_mobile_capture")

ELEVENLABS_KEYS = [
    os.environ.get("ELEVENLABS_API_KEY", ""),
    "sk_1a6f82b58f6110efdb8b0cce0b470505b9630bbdf8b69795",
    "sk_23049c20908c037dcaacd577ec4524ad4ef9674756d8f67c",
    "sk_7a19a6c786e6ce5b518337ad562c31bb673e61403c048c3b",
    "sk_9518cdd9e61bdf93f3e9d2ad8f129c455c108cf487881505",
]
ELEVENLABS_VOICE_ID = os.environ.get("SANTA_VOICE_ID", "nPczCjzI2devNBz1zQrb")
ELEVENLABS_MODEL_ID = "eleven_v4"

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)

SCENES_POSADA_SANTA = [
    {
        "type": "hook",
        "accent_rgb": (243, 198, 105),
        "promo_badge": "POSADAS 2026 · PAQUETE 3 EN 1",
        "bottom_pill": "FAMILIAS · EMPRESAS · AMIGO SECRETO",
        "voice_text": "¡Jo, jo, jo! ¿Organizando la posada de tu familia, amigos o empresa? Olvida las imágenes aburridas: este año sorprende a todos en WhatsApp con la nueva invitación interactiva navideña de Drim Crafters.",
    },
    {
        "type": "hero_video",
        "accent_rgb": (255, 51, 75),
        "promo_badge": "FAMILIAS O EMPRESAS + SALUDO VIP",
        "bottom_pill": "MÚSICA + VIDEO PERSONALIZADO DE SANTA",
        "voice_text": "Personaliza el título para tu familia o tu negocio, con música navideña y un video exclusivo donde yo mismo saludo e invito a todos tus asistentes.",
    },
    {
        "type": "secret_santa",
        "accent_rgb": (243, 198, 105),
        "promo_badge": "AMIGO SECRETO · RASCA Y GANA",
        "bottom_pill": "PIN DE 4 DÍGITOS + PASES POR WHATSAPP",
        "voice_text": "Además incluye un gestor de Amigo Secreto anti-trampas: envías cada pase por WhatsApp en un clic y tus invitados rascan su tarjeta dorada con PIN secreto para descubrir a quién le regalan y su lista de deseos.",
    },
    {
        "type": "rsvp_website",
        "accent_rgb": (52, 211, 153),
        "promo_badge": "MAPA GPS + PASE VIP POLO NORTE",
        "bottom_pill": "CONFIRMACIÓN CON QR A TU WHATSAPP",
        "voice_text": "También tiene mapa interactivo y pase de abordaje VIP directo a tu celular. Entra hoy a drim crafters punto lat y arma la mejor posada del año.",
    },
    {
        "type": "cta",
        "accent_rgb": (243, 198, 105),
        "promo_badge": "INVITACIÓN + VIDEO + INTERCAMBIO",
        "bottom_pill": "PÍDELA HOY EN DREAMCRAFTERS.LAT",
        "voice_text": "¡Haz que tu posada e intercambio sean inolvidables! Pídela ahora en drim crafters punto lat. ¡Jo, jo, jo, allá nos vemos!",
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


def load_pil_rgba(path, size=None):
    if not path or not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    if size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    return img


def get_font(size, bold=False, mono=False):
    candidates = []
    if mono:
        candidates.append(os.path.join(CHAR_02_DIR, "assets", "ShareTechMono-Regular.ttf"))
        candidates.append(r"C:\Windows\Fonts\consolab.ttf" if bold else r"C:\Windows\Fonts\consola.ttf")
    if bold:
        candidates.extend([r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"])
    else:
        candidates.extend([r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"])
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _pick_working_elevenlabs_key(min_chars=250):
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
                if rem >= min_chars:
                    print(f"[ElevenLabs Santa] Usando key {k[:12]}... (saldo disponible: {rem} chars)")
                    return k
        except Exception:
            pass
    raise RuntimeError("No se encontró ninguna key de ElevenLabs con saldo suficiente.")


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


def synthesize_santa_scenes(scenes, output_wav_path, ffmpeg_path="ffmpeg"):
    cache_dir = os.path.join(CHAR_04_DIR, "out", "elevenlabs_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.18 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)
    eq_filter = (
        "highpass=f=65,"
        "equalizer=f=180:width_type=o:width=1.2:g=2.2,"
        "equalizer=f=3600:width_type=o:width=1.4:g=3.5,"
        "loudnorm=I=-12.5:TP=-0.8:LRA=8"
    )

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []
    api_key = None

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"santa_posada_v4|{ELEVENLABS_VOICE_ID}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"santa_posada_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav) or os.path.getsize(cached_wav) < 1000:
            if not api_key:
                api_key = _pick_working_elevenlabs_key(min_chars=len(v_text) + 50)
            print(f"  [ElevenLabs v4 Santa] Sintetizando Escena {idx+1}: {v_text[:65]}...")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"
            payload = json.dumps(
                {
                    "text": v_text,
                    "model_id": ELEVENLABS_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.40,
                        "similarity_boost": 0.86,
                        "style": 0.56,
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
            raw_mp3 = cached_wav + ".raw.mp3"
            with urllib.request.urlopen(req, timeout=45) as resp:
                with open(raw_mp3, "wb") as f_mp3:
                    f_mp3.write(resp.read())

            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    raw_mp3,
                    "-af",
                    eq_filter,
                    "-ac",
                    "1",
                    "-ar",
                    str(sr),
                    "-c:a",
                    "pcm_s16le",
                    cached_wav,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if os.path.exists(raw_mp3):
                os.remove(raw_mp3)
        else:
            print(f"  [ElevenLabs Cache] Reusando Escena {idx+1} desde caché local")

        with wave.open(cached_wav, "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

        pcm = _trim_silence_pcm(pcm, sr=sr)
        seg_pcm = np.concatenate([pcm, pause_samples if idx < len(scenes) - 1 else tail_samples])
        dur = len(seg_pcm) / float(sr)

        sc_copy = dict(sc)
        sc_copy["start"] = round(cur_time, 3)
        sc_copy["end"] = round(cur_time + dur, 3)
        updated_scenes.append(sc_copy)

        all_pcm.append(seg_pcm)
        cur_time += dur

    full_pcm = np.concatenate(all_pcm)
    with wave.open(output_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(full_pcm.tobytes())

    return updated_scenes


def mix_voice_with_bgm(voice_wav_path, bgm_path, output_wav_path, bgm_vol=0.13, ffmpeg_path="ffmpeg"):
    if not bgm_path or not os.path.exists(bgm_path):
        shutil.copyfile(voice_wav_path, output_wav_path)
        return output_wav_path

    filter_complex = (
        f"[0:a]volume=1.0[v];"
        f"[1:a]volume={bgm_vol:.3f},aloop=loop=-1:size=2e+09[b];"
        f"[v][b]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.96[out]"
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


def _key_santa_green_screen(bgr: np.ndarray) -> Image.Image:
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


class FeatherTalkSantaEngine:
    def __init__(self, onnx_dir: str, voice_wav_path: str, fps: int = 24, ffmpeg_path: str = "ffmpeg"):
        import onnxruntime as ort

        self.onnx_dir = onnx_dir
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path

        hubert_path = os.path.join(onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(onnx_dir, "closed_win.npy")
        video_path = os.path.join(onnx_dir, "santa_25fps.mp4")
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
        ref_bbox = tuple(self.bboxes[72]) if len(self.bboxes) > 72 else tuple(self.bboxes[0])
        ref_crop = _crop_face(ref_img, ref_bbox, crop_size=FACE_CROP_SIZE)
        self.ref_inner = _extract_inner(ref_crop, inner_size=FACE_INNER_SIZE)

        base_seq = list(range(0, len(self.base_frames)))
        self.ping_pong = base_seq + base_seq[-2:0:-1]
        self.pp_cursor = 0

        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[16:112, 14:130] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (21, 21), 5.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio(voice_wav_path, fps=fps)

    def _analyze_audio(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k_santa.wav"
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
        chunk_samples = sr * 15
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

    def synthesize_santa_rgba(self, frame_idx: int) -> tuple[Image.Image, float]:
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

        santa_rgba = _key_santa_green_screen(frame_bgr)
        return santa_rgba, rms_val


class PosadaSantaCommercialRenderer:
    def __init__(self, ft_engine: FeatherTalkSantaEngine):
        self.ft = ft_engine
        self.W = 720
        self.H = 1280

        # Fondo del Polo Norte limpio (o christmas_bg.jpg como respaldo)
        north_pole_path = os.path.join(POSADA_WEB_DIR, "assets", "fondo_polo_norte.webp")
        christmas_bg_path = os.path.join(CHAR_04_DIR, "christmas_bg.jpg")
        bg_src = north_pole_path if os.path.exists(north_pole_path) else christmas_bg_path
        raw_bg = load_pil_rgba(bg_src)
        if raw_bg:
            gw, gh = raw_bg.size
            scale_g = max(self.W / float(gw), self.H / float(gh))
            nw, nh = int(gw * scale_g), int(gh * scale_g)
            g_res = raw_bg.resize((nw, nh), Image.Resampling.LANCZOS)
            lx = (nw - self.W) // 2
            ly = (nh - self.H) // 2
            g_crop = g_res.crop((lx, ly, lx + self.W, ly + self.H))
            dark_veil = Image.new("RGBA", (self.W, self.H), (7, 11, 25, 55))
            self.north_pole_bg = Image.alpha_composite(g_crop, dark_veil)
        else:
            self.north_pole_bg = Image.new("RGBA", (self.W, self.H), (7, 11, 25, 255))

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

        self.hero_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "hero_video", "frame_*.png")))
        self.secret_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "secret_santa", "frame_*.png")))
        self.rsvp_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "rsvp_website", "frame_*.png")))
        print(
            f"[Posada Renderer] Frames móviles 1.0x cargados: hero_video={len(self.hero_frames)}, "
            f"secret_santa={len(self.secret_frames)}, rsvp_website={len(self.rsvp_frames)}"
        )

        rng = np.random.RandomState(202612)
        self.snowflakes = []
        for _ in range(85):
            self.snowflakes.append(
                {
                    "x0": float(rng.uniform(0, self.W)),
                    "y0": float(rng.uniform(0, self.H)),
                    "r": float(rng.uniform(1.5, 4.2)),
                    "vy": float(rng.uniform(1.8, 4.5)),
                    "vx": float(rng.uniform(-0.8, 0.8)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "alpha": int(rng.uniform(125, 245)),
                }
            )

        self.gold_sparks = []
        spark_colors = [(243, 198, 105), (255, 255, 255), (255, 51, 75)]
        for _ in range(26):
            self.gold_sparks.append(
                {
                    "x0": float(rng.uniform(24, self.W - 24)),
                    "y0": float(rng.uniform(40, self.H * 0.80)),
                    "size": float(rng.uniform(6.0, 12.5)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "pulse": float(rng.uniform(0.08, 0.16)),
                    "color": spark_colors[int(rng.randint(0, len(spark_colors)))],
                }
            )

        self.f_pill = get_font(20, bold=True)
        self.f_badge = get_font(16, bold=True, mono=True)
        self.f_url = get_font(18, mono=True)
        self.f_intro_sub = get_font(20, bold=True, mono=True)
        self.f_nav_label = get_font(19, bold=True)
        self.f_nav_url = get_font(33, bold=True, mono=True)
        self.f_nav_hint = get_font(17, bold=True)

    def _draw_four_point_spark(self, draw_obj, cx, cy, size, color_rgb, alpha_float):
        if alpha_float <= 0.05 or size < 1.5:
            return
        a_main = int(max(0, min(255, round(alpha_float * 255))))
        a_glow = int(max(0, min(255, round(alpha_float * 95))))
        r_glow = int(round(size * 1.35))
        draw_obj.ellipse(
            (cx - r_glow, cy - r_glow, cx + r_glow, cy + r_glow),
            fill=color_rgb + (a_glow,),
        )
        inner = size * 0.24
        pts = [
            (cx, cy - size),
            (cx + inner, cy - inner),
            (cx + size, cy),
            (cx + inner, cy + inner),
            (cx, cy + size),
            (cx - inner, cy + inner),
            (cx - size, cy),
            (cx - inner, cy - inner),
        ]
        draw_obj.polygon(pts, fill=color_rgb + (a_main,))

    def render_north_pole_stage_bg(self, idx):
        canvas = self.north_pole_bg.copy()
        overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        for sf in self.snowflakes:
            x = (sf["x0"] + idx * sf["vx"] + 8.0 * math.sin(idx * 0.05 + sf["phase"])) % self.W
            y = (sf["y0"] + idx * sf["vy"]) % self.H
            r = sf["r"]
            od.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, sf["alpha"]))

        for sp in self.gold_sparks:
            s_val = math.sin(idx * sp["pulse"] + sp["phase"])
            alpha = 0.28 + 0.72 * (0.5 + 0.5 * s_val)
            cur_size = sp["size"] * (0.74 + 0.32 * s_val)
            self._draw_four_point_spark(od, sp["x0"], sp["y0"], cur_size, sp["color"], alpha)

        canvas.alpha_composite(overlay)
        return canvas

    def _draw_top_bar_and_bottom_pill(self, canvas: Image.Image, sc: dict):
        accent = sc["accent_rgb"]

        # Sombra superior suave y gradiente inferior para lectura impecable
        top_grad = Image.new("RGBA", (self.W, 115), (0, 0, 0, 0))
        tgd = ImageDraw.Draw(top_grad)
        for gy in range(115):
            a_t = int(185 * ((1.0 - gy / 115.0) ** 1.4))
            tgd.line([(0, gy), (self.W, gy)], fill=(7, 11, 25, a_t))
        canvas.alpha_composite(top_grad, (0, 0))

        grad = Image.new("RGBA", (self.W, 235), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(235):
            alpha_g = int(222 * ((gy / 235.0) ** 1.5))
            gd.line([(0, gy), (self.W, gy)], fill=(7, 11, 25, alpha_g))
        canvas.alpha_composite(grad, (0, self.H - 235))

        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (26, 26))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 30
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (88, 39))

        cd = ImageDraw.Draw(canvas)
        badge_x0, badge_y0, badge_x1, badge_y1 = self.W - 350, 26, self.W - 22, 82
        cd.rounded_rectangle(
            (badge_x0, badge_y0, badge_x1, badge_y1),
            radius=18,
            fill=(15, 19, 33, 240),
            outline=accent + (235,),
            width=2,
        )
        cd.text(
            ((badge_x0 + badge_x1) // 2, (badge_y0 + badge_y1) // 2),
            sc.get("promo_badge", "POSADAS 2026"),
            font=self.f_badge,
            fill=accent,
            anchor="mm",
        )

        pill_y0, pill_y1 = self.H - 126, self.H - 34
        cd.rounded_rectangle(
            (28, pill_y0, self.W - 28, pill_y1),
            radius=24,
            fill=(15, 19, 33, 244),
            outline=accent + (230,),
            width=2,
        )
        cd.text((self.W // 2, pill_y0 + 30), sc["bottom_pill"], font=self.f_pill, fill=accent, anchor="mm")
        cd.text((self.W // 2, pill_y0 + 64), ">> DREAMCRAFTERS.LAT · POSADAS 2026 <<", font=self.f_url, fill=(248, 250, 252), anchor="mm")

    def _overlay_santa_pip(self, canvas: Image.Image, santa_rgba: Image.Image, accent_rgb: tuple[int, int, int]):
        """Incrusta un círculo Picture-in-Picture de Santa 3D hablando en la esquina inferior derecha."""
        pip_size = 196
        pip_x = self.W - pip_size - 24
        pip_y = self.H - pip_size - 144

        pip_bg = self.north_pole_bg.crop((180, 180, 540, 540)).resize((pip_size, pip_size), Image.Resampling.LANCZOS)
        # Recortar el busto de Santa (centrado en su rostro y barba)
        sw, sh = santa_rgba.size
        santa_bust = santa_rgba.crop((int(sw * 0.16), int(sh * 0.08), int(sw * 0.84), int(sh * 0.62))).resize(
            (pip_size, pip_size), Image.Resampling.LANCZOS
        )
        pip_bg.alpha_composite(santa_bust)

        mask = Image.new("L", (pip_size, pip_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, pip_size - 1, pip_size - 1), fill=255)

        # Halo y borde circular dorado/rubí
        ring = Image.new("RGBA", (pip_size + 16, pip_size + 16), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse((2, 2, pip_size + 13, pip_size + 13), fill=(7, 11, 25, 195), outline=accent_rgb + (245,), width=4)
        canvas.alpha_composite(ring, (pip_x - 8, pip_y - 8))
        canvas.paste(pip_bg, (pip_x, pip_y), mask)

    def _overlay_typing_browser_box(self, canvas: Image.Image, t_in_sc: float, sc_dur: float) -> Image.Image:
        show_start = max(1.6, sc_dur * 0.36)
        if t_in_sc < show_start:
            return canvas

        el = t_in_sc - show_start
        rem = sc_dur - t_in_sc
        if el < 0.25:
            alpha_u = el / 0.25
        elif rem < 0.30:
            alpha_u = max(0.0, rem / 0.30)
        else:
            alpha_u = 1.0

        if alpha_u <= 0.02:
            return canvas

        target_text = "dreamcrafters.lat"
        type_prog = min(1.0, max(0.0, (el - 0.15) / 1.45))
        n_chars = int(round(type_prog * len(target_text)))
        typed_str = target_text[:n_chars]
        is_complete = n_chars >= len(target_text)

        bx0, by0, bx1, by1 = 28, 455, self.W - 28, 755
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=18))

        glass_card = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass_card.paste(crop_region, (0, 0))
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (7, 11, 25, int(226 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (243, 198, 105, int(245 * alpha_u)) if is_complete else (255, 51, 75, int(235 * alpha_u))
        od.rounded_rectangle((bx0, by0, bx1, by1), radius=32, outline=border_col, width=3)

        od.text(
            (self.W // 2, by0 + 42),
            "PIDE TU INVITACIÓN DE POSADA EN:",
            font=self.f_nav_label,
            fill=(248, 250, 252, int(245 * alpha_u)),
            anchor="mm",
        )

        bar_x0, bar_y0, bar_x1, bar_y1 = bx0 + 26, by0 + 78, bx1 - 26, by0 + 178
        od.rounded_rectangle(
            (bar_x0, bar_y0, bar_x1, bar_y1),
            radius=22,
            fill=(5, 8, 18, int(248 * alpha_u)),
            outline=border_col,
            width=2,
        )

        icon_cx, icon_cy = bar_x0 + 44, (bar_y0 + bar_y1) // 2
        od.ellipse(
            (icon_cx - 13, icon_cy - 13, icon_cx + 9, icon_cy + 9),
            outline=(243, 198, 105, int(245 * alpha_u)),
            width=3,
        )
        od.line(
            [(icon_cx + 6, icon_cy + 6), (icon_cx + 16, icon_cy + 16)],
            fill=(243, 198, 105, int(245 * alpha_u)),
            width=3,
        )

        cursor_on = (not is_complete) or (int(el * 6) % 2 == 0)
        display_url = typed_str + ("|" if cursor_on and not is_complete else "")
        text_col = (243, 198, 105, int(255 * alpha_u)) if is_complete else (250, 246, 238, int(255 * alpha_u))
        od.text(
            (bar_x0 + 82, (bar_y0 + bar_y1) // 2),
            display_url,
            font=self.f_nav_url,
            fill=text_col,
            anchor="lm",
        )

        if is_complete:
            go_x0, go_y0, go_x1, go_y1 = bar_x1 - 92, bar_y0 + 18, bar_x1 - 18, bar_y1 - 18
            od.rounded_rectangle(
                (go_x0, go_y0, go_x1, go_y1),
                radius=14,
                fill=(225, 29, 56, int(250 * alpha_u)),
            )
            od.text(
                ((go_x0 + go_x1) // 2, (go_y0 + go_y1) // 2),
                "IR →",
                font=self.f_nav_label,
                fill=(255, 255, 255, int(255 * alpha_u)),
                anchor="mm",
            )

        od.text(
            (self.W // 2, by1 - 44),
            "POSADA · SALUDO DE SANTA · AMIGO SECRETO",
            font=self.f_nav_hint,
            fill=(243, 198, 105, int(250 * alpha_u)),
            anchor="mm",
        )
        self._draw_four_point_spark(od, bx0 + 82, by1 - 44, 8.5, (243, 198, 105), alpha_u)
        self._draw_four_point_spark(od, bx1 - 82, by1 - 44, 8.5, (243, 198, 105), alpha_u)

        out.alpha_composite(ov)
        return out

    def render_logo_outro_frame(self, outro_prog, idx=0):
        canvas = self.render_north_pole_stage_bg(idx)
        dark_overlay = Image.new("RGBA", (self.W, self.H), (7, 11, 25, int(212 * min(1.0, outro_prog * 1.8))))
        canvas = Image.alpha_composite(canvas, dark_overlay)

        halo_alpha = int(160 * min(1.0, outro_prog * 2.2))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(185 + 45 * math.sin(outro_prog * math.pi * 2.0))
            cx, cy = self.W // 2, self.H // 2 - 55
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(225, 29, 56, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(243, 198, 105, halo_alpha // 3))
            canvas.alpha_composite(halo)

        if self.d_icon_hd:
            if outro_prog < 0.26:
                u = outro_prog / 0.26
                c1 = 1.70158
                c3 = c1 + 1.0
                scale = 0.18 + 0.84 * (1.0 + c3 * ((u - 1.0) ** 3) + c1 * ((u - 1.0) ** 2))
                cx = int((1.0 - u) * 59 + u * (self.W // 2))
                cy = int((1.0 - u) * 56 + u * (self.H // 2 - 55))
            else:
                scale = 1.02 + 0.03 * math.sin((outro_prog - 0.26) * 8.0)
                cx, cy = self.W // 2, self.H // 2 - 55

            target_w = max(48, int(330 * scale))
            target_h = max(50, int(340 * scale))
            d_img = self.d_icon_hd.resize((target_w, target_h), Image.Resampling.LANCZOS)

            if 0.15 <= outro_prog <= 0.78:
                sweep_u = (outro_prog - 0.15) / 0.63
                _, _, _, d_alpha = d_img.split()
                sweep_layer = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                sw_d = ImageDraw.Draw(sweep_layer)
                band_x = int(-target_w * 0.4 + sweep_u * (target_w * 1.8))
                poly = [
                    (band_x - 36, 0),
                    (band_x + 36, 0),
                    (band_x - 24, target_h),
                    (band_x - 96, target_h),
                ]
                sw_d.polygon(poly, fill=(243, 198, 105, 195))
                masked_sweep = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                masked_sweep.paste(sweep_layer, (0, 0), d_alpha)
                d_img = Image.alpha_composite(d_img, masked_sweep)

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
                "POSADAS · SALUDO DE SANTA · INTERCAMBIO",
                font=self.f_intro_sub,
                fill=(243, 198, 105, int(250 * txt_alpha)),
                anchor="mm",
            )
            pill_y0, pill_y1 = self.H - 126, self.H - 34
            tod.rounded_rectangle(
                (32, pill_y0, self.W - 32, pill_y1),
                radius=24,
                fill=(15, 19, 33, int(242 * txt_alpha)),
                outline=(255, 51, 75, int(230 * txt_alpha)),
                width=2,
            )
            tod.text(
                (self.W // 2, pill_y0 + 30),
                "PÍDELA HOY EN DREAMCRAFTERS.LAT",
                font=self.f_pill,
                fill=(243, 198, 105, int(255 * txt_alpha)),
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
        sc_type = sc["type"]
        sc_dur = max(0.1, sc["end"] - sc["start"])
        t_in_sc = (idx / float(fps)) - sc["start"]
        local_frame_idx = max(0, int(round(t_in_sc * fps)))

        # Siempre avanzamos el motor de Santa 3D para mantener sincronía labial perfecta cuadro a cuadro
        santa_rgba, _ = self.ft.synthesize_santa_rgba(idx)

        if sc_type == "cta":
            ending_logo_start_sec = max(2.4, sc_dur - 2.3)
            if t_in_sc >= ending_logo_start_sec:
                outro_prog = min(1.0, (t_in_sc - ending_logo_start_sec) / max(0.1, sc_dur - ending_logo_start_sec))
                return self.render_logo_outro_frame(outro_prog, idx=idx)

        if sc_type in ("hero_video", "secret_santa", "rsvp_website"):
            frames_list = (
                self.hero_frames
                if sc_type == "hero_video"
                else (self.secret_frames if sc_type == "secret_santa" else self.rsvp_frames)
            )
            if frames_list:
                f_idx = min(len(frames_list) - 1, max(0, local_frame_idx))
                canvas = Image.open(frames_list[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)
            else:
                canvas = self.render_north_pole_stage_bg(idx)

            if sc_type == "rsvp_website":
                canvas = self._overlay_typing_browser_box(canvas, t_in_sc, sc_dur)

            # Agregar PiP de Santa 3D hablando y la barra/píldora informativa
            self._overlay_santa_pip(canvas, santa_rgba, sc["accent_rgb"])
            self._draw_top_bar_and_bottom_pill(canvas, sc)

            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Santa 3D a pantalla completa sobre el Polo Norte nevado
        canvas = self.render_north_pole_stage_bg(idx)

        shadow = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((self.W // 2 - 220, 1138 - 28, self.W // 2 + 220, 1138 + 28), fill=(10, 16, 34, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
        canvas.alpha_composite(shadow)

        canvas.alpha_composite(santa_rgba, (0, 0))
        self._draw_top_bar_and_bottom_pill(canvas, sc)

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=os.path.join(REPO_ROOT, "out", "promo_posada_santa_2026.mp4"),
    )
    parser.add_argument("--recapture", action="store_true", help="Forzar recaptura móvil con Playwright")
    args = parser.parse_args()

    # Asegurar bboxes exactos de Santa para cero desplazamiento facial
    ft_root = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\FeatherTalk"
    if os.path.exists(ft_root):
        sys.path.insert(0, ft_root)
        try:
            from face_utils import read_landmarks, compute_face_bbox
            lms_dir = os.path.join(ft_root, "santa_dataset", "landmarks")
            if os.path.exists(lms_dir):
                exact_bboxes = np.array(
                    [compute_face_bbox(read_landmarks(os.path.join(lms_dir, f"{i}.lms"))) for i in range(250)],
                    dtype=np.int32,
                )
                np.save(os.path.join(FEATHERTALK_ONNX_DIR, "bboxes_240.npy"), exact_bboxes)
        except Exception as e:
            print(f"[Aviso bboxes]: {e}")

    hero_cap_dir = os.path.join(REAL_CAP_DIR, "hero_video")
    if args.recapture or not os.path.exists(hero_cap_dir) or len(os.listdir(hero_cap_dir)) < 50:
        from capture_real_posada_mobile import capture_all
        capture_all()

    ffmpeg_path = resolve_ffmpeg_path()
    bgm_path = os.path.join(POSADA_WEB_DIR, "assets", "rocking_christmas.mp3")

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "posada_santa_2026_voice.wav")

    print("1/3 Sintetizando voz navideña de Santa (ElevenLabs v4) por escenas...")
    scenes = synthesize_santa_scenes(SCENES_POSADA_SANTA, clean_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    print("2/3 Inicializando motor FeatherTalk ONNX 144x144 para Santa 3D...")
    ft_engine = FeatherTalkSantaEngine(FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)

    total_frames = ft_engine.total_frames
    print(f"3/3 Renderizando {total_frames} frames ({total_frames/fps:.1f}s) a 24 FPS...")

    renderer = PosadaSantaCommercialRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_visual_posada_santa.mp4")
    vw = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (720, 1280))

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

    mixed_wav = os.path.join(out_dir, "posada_santa_2026_mixed.wav")
    final_audio = mix_voice_with_bgm(clean_wav, bgm_path, mixed_wav, bgm_vol=0.13, ffmpeg_path=ffmpeg_path)

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

    web_copy = os.path.join(POSADA_WEB_DIR, "assets", "promo_posada_santa_2026.mp4")
    shutil.copyfile(args.output, web_copy)
    print(f"Comercial oficial Posada + Santa + Amigo Secreto listo en:\n  - {args.output}\n  - {web_copy}")


if __name__ == "__main__":
    main()
