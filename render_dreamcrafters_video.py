# -*- coding: utf-8 -*-
"""
render_dreamcrafters_video.py — Motor Oficial de Video Promocional Exclusivo Super Mario Galaxy ($100 MXN)
===========================================================================================================
- Entrada directa en el cuadro 0 con Mario 3D (FeatherTalk ONNX 144x144 + FeatherHuBERT) sobre un escenario
  galáctico animado de Super Mario Galaxy (`Galaxy_back.webp` + `Starlight_stage.webp` + cometas + Star Bits 4 puntas +
  insignia dorada flotante `PROMO $100 MXN`).
- Clonación de Voz de Alta Fidelidad de Mario (`ResembleAI/Chatterbox-Multilingual-TTS` con `mario_ref_8s.wav`)
  con ecualización brillante y clara sobre el tema orquestal de Super Mario Galaxy.
- Capturas móviles en TIEMPO REAL 1.0x (24 FPS exactos cuadro a cuadro):
  1) `gameplay`: Minijuego Runner Espacial saltando sobre Bowser y Goombas hasta alcanzar 50/50 PTS con confeti.
  2) `unlocked`: Recorrido por la invitación galáctica desbloqueada + Pase de Abordaje Galáctico (`¡MISIÓN CONFIRMADA!`).
  3) `website`: `dreamcrafters.lat` enfocando la promoción de Super Mario Galaxy en $100 MXN con Box Blur central +
     barra de navegador tipeando letra por letra `dreamcrafters.lat`.
"""

import os
import sys
import glob
import math
import wave
import shutil
import hashlib
import argparse
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
FEATHERTALK_ONNX_DIR = os.path.join(CHAR_02_DIR, "feathertalk_onnx")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
MARIO_WEB_DIR = os.path.join(WEB_ASSETS_DIR, "invitacionmario")
REF_WAV = os.path.join(CHAR_02_DIR, "mario_ref_8s.wav")
REAL_CAP_DIR = os.path.join(CHAR_02_DIR, "out", "real_mobile_capture")

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)

DEFAULT_HF_TOKEN = os.environ.get("HF_API_KEY", "")

SCENES_MARIO_100 = [
    {
        "type": "hook",
        "accent_rgb": (56, 189, 248),
        "promo_badge": "PAQUETE $100: JUEGO + VIDEO",
        "bottom_pill": "¡MARIO FELICITA A TU PEQUE POR SU NOMBRE!",
        "voice_text": "¡Hola amigos! Soy yo, Mario. ¿Sabías que por solo cien pesos tu peque puede tener una invitación que es un videojuego real y además un video mío saludándolo por su nombre?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "MINIJUEGO JUGABLE EN CELULAR",
        "bottom_pill": "SALTA SOBRE BOWSER Y ATRAPA 50 PTS",
        "voice_text": "¡Mira qué increíble! Tus invitados abren el enlace en su teléfono, atrapan monedas espaciales y juegan para desbloquear las coordenadas de la fiesta.",
    },
    {
        "type": "unlocked",
        "accent_rgb": (56, 189, 248),
        "promo_badge": "INCLUYE SALUDO DE MARIO + MAPA",
        "bottom_pill": "VIDEO CON SU NOMBRE + PASE A WHATSAPP",
        "voice_text": "Adentro incluye un video exclusivo donde yo felicito al cumpleañero por su nombre y edad, invito a todos sus amigos, y les doy el mapa en Google Maps con confirmación a tu WhatsApp.",
    },
    {
        "type": "website",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "COMBO 2 EN 1: SOLO $100 MXN",
        "bottom_pill": "CÓMPRALA POR $100 EN DREAMCRAFTERS.LAT",
        "voice_text": "Olvida las imágenes aburridas. Entra a dreamcrafters punto lat y llévate el paquete completo de Super Mario Galaxy de doscientos cincuenta a solo cien pesos.",
    },
    {
        "type": "cta",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "SOLO $100 MXN · ENTREGA INMEDIATA",
        "bottom_pill": "ACTIVA TU MISIÓN EN DREAMCRAFTERS.LAT",
        "voice_text": "¡Sorprende a todos en el grupo de WhatsApp! Pídela ahora en dreamcrafters punto lat. ¡Allá nos vemos!",
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


def mix_voice_with_bgm(voice_wav_path, bgm_path, output_wav_path, bgm_vol=0.12, ffmpeg_path="ffmpeg"):
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


def synthesize_cloned_scenes_local(scenes, ref_wav_path, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Clona la voz de Mario (`ResembleAI/Chatterbox-Multilingual-TTS` con `mario_ref_8s.wav`)
    sin cortinilla de inicio (entra directo en el segundo 0.0) y aplica ecualización brillante.
    """
    cache_dir = os.path.join(CHAR_02_DIR, "out", "cloned_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.20 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []

    hf_token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HF_API_KEY")
        or os.environ.get("HUGGINGFACE_TOKEN")
        or DEFAULT_HF_TOKEN
    )

    local_model = None
    eq_filter = "highpass=f=75,equalizer=f=3600:width_type=o:width=1.4:g=3.6,equalizer=f=7500:width_type=o:width=1.5:g=2.6,loudnorm=I=-12.8:TP=-0.8:LRA=7"

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"chatterbox_mario_100_bright|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"mario_100_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav):
            print(f"[Chatterbox-Multilingual-TTS] Clonando voz de Mario para Escena {idx+1}...")
            raw_tmp = os.path.join(cache_dir, f"_raw_cb_sc_{idx+1}.wav")
            cloned_ok = False
            try:
                from gradio_client import Client, handle_file

                c = Client("ResembleAI/Chatterbox-Multilingual-TTS", token=hf_token)
                wav_out = c.predict(
                    text_input=v_text,
                    language_id="es",
                    audio_prompt_path_input=handle_file(ref_wav_path),
                    exaggeration_input=0.55,
                    temperature_input=0.7,
                    seed_num_input=42,
                    cfgw_input=0.5,
                    api_name="/generate_tts_audio",
                )
                if wav_out and os.path.exists(wav_out):
                    subprocess.run(
                        [
                            ffmpeg_path,
                            "-y",
                            "-i",
                            wav_out,
                            "-af",
                            eq_filter,
                            "-ac",
                            "1",
                            "-ar",
                            str(sr),
                            "-c:a",
                            "pcm_s16le",
                            raw_tmp,
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    cloned_ok = True
            except Exception as e:
                print(f"  [Aviso HF Space Chatterbox, usando modelo local]: {e}")

            if not cloned_ok:
                import torch
                import torchaudio
                import perth

                class _DummyWatermarker:
                    def apply_watermark(self, wav, sample_rate=None):
                        return wav

                perth.PerthImplicitWatermarker = _DummyWatermarker
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS

                if local_model is None:
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    local_model = ChatterboxMultilingualTTS.from_pretrained(device=device)

                torch.manual_seed(42)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed(42)
                wav_tensor = local_model.generate(
                    v_text,
                    language_id="es",
                    audio_prompt_path=ref_wav_path,
                    exaggeration=0.55,
                    temperature=0.7,
                    cfg_weight=0.5,
                )
                raw_src = os.path.join(cache_dir, f"_src_cb_sc_{idx+1}.wav")
                torchaudio.save(raw_src, wav_tensor.cpu(), local_model.sr)
                subprocess.run(
                    [
                        ffmpeg_path,
                        "-y",
                        "-i",
                        raw_src,
                        "-af",
                        eq_filter,
                        "-ac",
                        "1",
                        "-ar",
                        str(sr),
                        "-c:a",
                        "pcm_s16le",
                        raw_tmp,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if os.path.exists(raw_src):
                    os.remove(raw_src)

            with wave.open(raw_tmp, "rb") as wf_r:
                raw_pcm = np.frombuffer(wf_r.readframes(wf_r.getnframes()), dtype=np.int16).copy()
            trimmed_pcm = _trim_silence_pcm(raw_pcm, sr=sr)
            with wave.open(cached_wav, "wb") as wf_w:
                wf_w.setnchannels(1)
                wf_w.setsampwidth(2)
                wf_w.setframerate(sr)
                wf_w.writeframes(trimmed_pcm.tobytes())
            if os.path.exists(raw_tmp):
                os.remove(raw_tmp)

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
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        ]
    elif bold:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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


def _key_mario_green_screen(bgr: np.ndarray) -> Image.Image:
    """Extrae a Mario del fondo verde (720x1280) con despill suave y sin halo verde."""
    b = bgr[:, :, 0].astype(np.float32)
    g = bgr[:, :, 1].astype(np.float32)
    r = bgr[:, :, 2].astype(np.float32)
    max_rb = np.maximum(r, b)
    excess = g - max_rb
    alpha = np.clip((58.0 - excess) / 40.0, 0.0, 1.0)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.7)
    g_despilled = np.where(excess > 0.0, max_rb + np.minimum(excess, 6.0), g)
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


class FeatherTalkMarioEngine:
    """Motor ONNX (FeatherHuBERT + FeatherTalk 144x144) para Mario 3D en el comercial."""

    def __init__(self, onnx_dir: str, voice_wav_path: str, fps: int = 24, ffmpeg_path: str = "ffmpeg"):
        import onnxruntime as ort

        self.onnx_dir = onnx_dir
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path

        hubert_path = os.path.join(onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(onnx_dir, "closed_win.npy")
        video_path = os.path.join(onnx_dir, "mario_25fps.mp4")
        ref_194_path = os.path.join(onnx_dir, "ref_194.jpg")

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

        ref_img = cv2.imread(ref_194_path) if os.path.exists(ref_194_path) else self.base_frames[194]
        ref_crop = _crop_face(ref_img, tuple(self.bboxes[194]), crop_size=FACE_CROP_SIZE)
        self.ref_inner = _extract_inner(ref_crop, inner_size=FACE_INNER_SIZE)

        base_seq = list(range(24, min(249, len(self.base_frames))))
        ping_pong = base_seq + base_seq[-2:0:-1]
        start_offset = ping_pong.index(194) if 194 in ping_pong else 0
        self.ping_pong = ping_pong[start_offset:] + ping_pong[:start_offset]
        self.pp_cursor = 0

        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[50:128, 15:129] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (27, 27), 7.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio(voice_wav_path, fps=fps)

    def _analyze_audio(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k_ft.wav"
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

    def synthesize_mario_rgba(self, frame_idx: int) -> tuple[Image.Image, float]:
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

        mario_rgba = _key_mario_green_screen(frame_bgr)
        return mario_rgba, rms_val


class MarioGalaxyCommercialRenderer:
    def __init__(self, ft_engine: FeatherTalkMarioEngine):
        self.ft = ft_engine
        self.W = 720
        self.H = 1280

        # Fondo Galáctico Super Mario Galaxy (Galaxy_back.webp + Starlight_stage.webp)
        galaxy_path = os.path.join(MARIO_WEB_DIR, "Galaxy_back.webp")
        raw_galaxy = load_pil_rgba(galaxy_path)
        if raw_galaxy:
            gw, gh = raw_galaxy.size
            scale_g = max(self.W / float(gw), self.H / float(gh))
            nw, nh = int(gw * scale_g), int(gh * scale_g)
            g_res = raw_galaxy.resize((nw, nh), Image.Resampling.LANCZOS)
            lx = (nw - self.W) // 2
            ly = (nh - self.H) // 2
            g_crop = g_res.crop((lx, ly, lx + self.W, ly + self.H)).filter(ImageFilter.GaussianBlur(radius=3.5))
            dark_veil = Image.new("RGBA", (self.W, self.H), (4, 8, 22, 110))
            self.galaxy_stage_bg = Image.alpha_composite(g_crop, dark_veil)
        else:
            self.galaxy_stage_bg = Image.new("RGBA", (self.W, self.H), (6, 12, 28, 255))

        self.mario_coin = load_pil_rgba(os.path.join(MARIO_WEB_DIR, "Mario_coin.webp"), (54, 54))
        self.mario_star = load_pil_rgba(os.path.join(MARIO_WEB_DIR, "Mario_star.webp"), (68, 68))
        self.lumalee = load_pil_rgba(os.path.join(MARIO_WEB_DIR, "Lumalee.webp"), (110, 110))

        d_icon_path = os.path.join(REAL_CAP_DIR, "d_icon_hd.png")
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

        rng = np.random.RandomState(2026)
        palette_rgb = [
            (255, 255, 255),
            (255, 224, 85),
            (56, 232, 255),
            (255, 61, 127),
        ]
        self.cosmic_dots = []
        for _ in range(72):
            self.cosmic_dots.append(
                {
                    "x0": float(rng.uniform(0, self.W)),
                    "y0": float(rng.uniform(0, self.H * 0.88)),
                    "r": float(rng.uniform(1.0, 2.5)),
                    "speed": float(rng.uniform(0.6, 2.2)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "twinkle": float(rng.uniform(0.08, 0.18)),
                    "color": palette_rgb[int(rng.randint(0, len(palette_rgb)))],
                }
            )

        self.cosmic_sparks = []
        for _ in range(30):
            self.cosmic_sparks.append(
                {
                    "x0": float(rng.uniform(20, self.W - 20)),
                    "y0": float(rng.uniform(35, self.H * 0.84)),
                    "size": float(rng.uniform(5.8, 12.0)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "pulse_speed": float(rng.uniform(0.07, 0.15)),
                    "drift_speed": float(rng.uniform(0.35, 1.1)),
                    "color": palette_rgb[int(rng.randint(0, len(palette_rgb)))],
                }
            )

        self.comet_palettes = [
            {"head": (255, 255, 255), "tail": (56, 232, 255)},
            {"head": (255, 224, 85), "tail": (255, 224, 85)},
            {"head": (255, 157, 226), "tail": (255, 61, 127)},
        ]

        self.f_pill = get_font(20, bold=True)
        self.f_badge = get_font(17, bold=True, mono=True)
        self.f_url = get_font(18, mono=True)
        self.f_intro_sub = get_font(21, bold=True, mono=True)
        self.f_nav_label = get_font(19, bold=True)
        self.f_nav_url = get_font(33, bold=True, mono=True)
        self.f_nav_hint = get_font(18, bold=True)

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

    def render_cosmic_galaxy_bg(self, idx):
        canvas = self.galaxy_stage_bg.copy()
        overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        for st in self.cosmic_dots:
            x = (st["x0"] - idx * st["speed"]) % self.W
            y = st["y0"]
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(idx * st["twinkle"] + st["phase"]))
            alpha = int(round(235 * tw))
            r = st["r"]
            od.ellipse((x - r, y - r, x + r, y + r), fill=st["color"] + (alpha,))

        for sp in self.cosmic_sparks:
            x = (sp["x0"] - idx * sp["drift_speed"]) % self.W
            y = sp["y0"]
            s_val = math.sin(idx * sp["pulse_speed"] + sp["phase"])
            alpha = 0.30 + 0.70 * (0.5 + 0.5 * s_val)
            cur_size = sp["size"] * (0.72 + 0.34 * s_val)
            self._draw_four_point_spark(od, x, y, cur_size, sp["color"], alpha)

        for slot in range(2):
            period = 40
            local_f = (idx + slot * 20) % period
            cycle_id = (idx + slot * 20) // period
            if local_f < 28:
                prog_c = local_f / 28.0
                life = math.sin(prog_c * math.pi)
                pal = self.comet_palettes[(cycle_id + slot) % len(self.comet_palettes)]

                start_x = self.W * (0.88 if slot == 0 else 0.62) + ((cycle_id * 97) % 140) - 50
                start_y = 70 + ((cycle_id * 73 + slot * 160) % 340)
                angle = math.pi * (0.74 if slot == 0 else 0.77)
                speed_c = 16.0
                dist_c = local_f * speed_c
                cx = start_x + math.cos(angle) * dist_c
                cy = start_y + math.sin(angle) * dist_c
                tail_len = 130.0
                tx = cx - math.cos(angle) * tail_len
                ty = cy - math.sin(angle) * tail_len

                steps = 16
                for s_i in range(steps):
                    u0 = s_i / float(steps)
                    u1 = (s_i + 1) / float(steps)
                    p0x = cx + (tx - cx) * u0
                    p0y = cy + (ty - cy) * u0
                    p1x = cx + (tx - cx) * u1
                    p1y = cy + (ty - cy) * u1
                    seg_alpha = int(round(235 * life * ((1.0 - u0) ** 1.5)))
                    width_s = max(1, int(round(4.4 * (1.0 - u0 * 0.7))))
                    if seg_alpha > 4:
                        od.line([(p0x, p0y), (p1x, p1y)], fill=pal["tail"] + (seg_alpha,), width=width_s)

                self._draw_four_point_spark(od, cx, cy, 9.8, pal["head"], min(1.0, life * 1.15))

        # Piso de puente estelar brillante bajo los pies de Mario
        floor_y = 1095
        od.line([(0, floor_y), (self.W, floor_y)], fill=(56, 232, 255, 195), width=4)
        od.line([(0, floor_y + 4), (self.W, floor_y + 4)], fill=(250, 204, 21, 110), width=2)

        canvas.alpha_composite(overlay)

        # Elementos 3D flotantes (Lumalee y Super Estrella orbitando suavemente en el fondo)
        if self.lumalee:
            bob_luma = int(12 * math.sin(idx * 0.11))
            canvas.alpha_composite(self.lumalee, (48, 225 + bob_luma))
        if self.mario_star:
            bob_star = int(10 * math.cos(idx * 0.13))
            canvas.alpha_composite(self.mario_star, (self.W - 116, 255 + bob_star))

        return canvas

    def _draw_floor_contact_shadow(self, canvas, cx, boot_y, rx, ry, alpha=165):
        shadow = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((cx - rx, boot_y - ry, cx + rx, boot_y + ry), fill=(4, 8, 18, alpha))
        sd.ellipse(
            (cx - int(rx * 0.65), boot_y - int(ry * 0.65), cx + int(rx * 0.65), boot_y + int(ry * 0.65)),
            fill=(56, 189, 248, 55),
        )
        canvas.alpha_composite(shadow)

    def render_fullscreen_invitation_realtime(self, scene_type, local_frame_idx):
        """Reproduce los cuadros capturados a 24 FPS en relación 1:1 (velocidad 1.0x real)."""
        if scene_type == "gameplay" and self.gameplay_frames:
            f_idx = min(len(self.gameplay_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.gameplay_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "unlocked" and self.unlocked_frames:
            f_idx = min(len(self.unlocked_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.unlocked_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "website" and self.website_frames:
            f_idx = min(len(self.website_frames) - 1, max(0, local_frame_idx))
            return Image.open(self.website_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        return self.galaxy_stage_bg.copy()

    def _overlay_typing_browser_box(self, canvas: Image.Image, t_in_sc: float, sc_dur: float) -> Image.Image:
        """
        Box Blur (frosted glass) en el centro de la pantalla con una barra de navegador
        tipeando letra por letra `dreamcrafters.lat` y destacando `PROMO $100 MXN` durante
        los primeros 3.5s de la escena `website`, antes de mostrar la tarjeta de compra en vivo.
        """
        show_until = min(3.55, sc_dur * 0.54)
        if t_in_sc > show_until:
            return canvas

        if t_in_sc < 0.22:
            alpha_u = t_in_sc / 0.22
        elif t_in_sc > show_until - 0.36:
            alpha_u = max(0.0, (show_until - t_in_sc) / 0.36)
        else:
            alpha_u = 1.0

        if alpha_u <= 0.02:
            return canvas

        target_text = "dreamcrafters.lat"
        type_prog = min(1.0, max(0.0, (t_in_sc - 0.18) / 1.75))
        n_chars = int(round(type_prog * len(target_text)))
        typed_str = target_text[:n_chars]
        is_complete = n_chars >= len(target_text)

        bx0, by0, bx1, by1 = 28, 465, self.W - 28, 765
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=18))

        glass_card = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass_card.paste(crop_region, (0, 0))
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (8, 14, 28, int(222 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (250, 204, 21, int(245 * alpha_u)) if is_complete else (56, 189, 248, int(235 * alpha_u))
        od.rounded_rectangle((bx0, by0, bx1, by1), radius=32, outline=border_col, width=3)

        od.text(
            (self.W // 2, by0 + 42),
            "ESCRIBE EN TU NAVEGADOR:",
            font=self.f_nav_label,
            fill=(190, 215, 240, int(245 * alpha_u)),
            anchor="mm",
        )

        bar_x0, bar_y0, bar_x1, bar_y1 = bx0 + 26, by0 + 78, bx1 - 26, by0 + 178
        od.rounded_rectangle(
            (bar_x0, bar_y0, bar_x1, bar_y1),
            radius=22,
            fill=(5, 9, 18, int(248 * alpha_u)),
            outline=border_col,
            width=2,
        )

        icon_cx, icon_cy = bar_x0 + 44, (bar_y0 + bar_y1) // 2
        od.ellipse(
            (icon_cx - 13, icon_cy - 13, icon_cx + 9, icon_cy + 9),
            outline=(56, 189, 248, int(245 * alpha_u)),
            width=3,
        )
        od.line(
            [(icon_cx + 6, icon_cy + 6), (icon_cx + 16, icon_cy + 16)],
            fill=(56, 189, 248, int(245 * alpha_u)),
            width=3,
        )

        cursor_on = (not is_complete) or (int(t_in_sc * 6) % 2 == 0)
        display_url = typed_str + ("|" if cursor_on and not is_complete else "")
        text_col = (250, 204, 21, int(255 * alpha_u)) if is_complete else (250, 246, 238, int(255 * alpha_u))
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
                fill=(250, 204, 21, int(250 * alpha_u)),
            )
            od.text(
                ((go_x0 + go_x1) // 2, (go_y0 + go_y1) // 2),
                "IR →",
                font=self.f_nav_label,
                fill=(12, 16, 24, int(255 * alpha_u)),
                anchor="mm",
            )

        od.text(
            (self.W // 2, by1 - 44),
            "★ SUPER MARIO GALAXY · PROMO $100 MXN ★",
            font=self.f_nav_hint,
            fill=(250, 204, 21, int(250 * alpha_u)),
            anchor="mm",
        )

        out.alpha_composite(ov)
        return out

    def render_logo_outro_frame(self, outro_prog, idx=0):
        canvas = self.render_cosmic_galaxy_bg(idx)
        dark_overlay = Image.new("RGBA", (self.W, self.H), (6, 10, 20, int(205 * min(1.0, outro_prog * 1.8))))
        canvas = Image.alpha_composite(canvas, dark_overlay)

        halo_alpha = int(155 * min(1.0, outro_prog * 2.2))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(185 + 45 * math.sin(outro_prog * math.pi * 2.0))
            cx, cy = self.W // 2, self.H // 2 - 55
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(56, 189, 248, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(250, 204, 21, halo_alpha // 4))
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
                sw_d.polygon(poly, fill=(250, 204, 21, 195))
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
                "SUPER MARIO GALAXY · PROMO $100 MXN",
                font=self.f_intro_sub,
                fill=(250, 204, 21, int(250 * txt_alpha)),
                anchor="mm",
            )
            pill_y0, pill_y1 = self.H - 126, self.H - 34
            tod.rounded_rectangle(
                (32, pill_y0, self.W - 32, pill_y1),
                radius=24,
                fill=(15, 19, 26, int(240 * txt_alpha)),
                outline=(56, 189, 248, int(220 * txt_alpha)),
                width=2,
            )
            tod.text(
                (self.W // 2, pill_y0 + 30),
                "ACTÍVALA POR $100 EN DREAMCRAFTERS.LAT",
                font=self.f_pill,
                fill=(56, 189, 248, int(255 * txt_alpha)),
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

        if sc_type == "cta":
            ending_logo_start_sec = max(2.6, sc_dur - 2.5)
            if t_in_sc >= ending_logo_start_sec:
                outro_prog = min(1.0, (t_in_sc - ending_logo_start_sec) / max(0.1, sc_dur - ending_logo_start_sec))
                return self.render_logo_outro_frame(outro_prog, idx=idx)

        # ESCENAS GAMEPLAY / UNLOCKED / WEBSITE -> PANTALLA COMPLETA EN TIEMPO REAL 1.0x
        if sc_type in ("gameplay", "unlocked", "website"):
            canvas = self.render_fullscreen_invitation_realtime(sc_type, local_frame_idx)
            if sc_type == "website":
                canvas = self._overlay_typing_browser_box(canvas, t_in_sc, sc_dur)
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Mario 3D (FeatherTalk ONNX) sobre el Escenario Galáctico Animado
        accent = sc["accent_rgb"]
        canvas = self.render_cosmic_galaxy_bg(idx)

        mario_rgba, _ = self.ft.synthesize_mario_rgba(idx)
        self._draw_floor_contact_shadow(canvas, self.W // 2, 1132, rx=175, ry=24, alpha=170)
        canvas.alpha_composite(mario_rgba, (0, 0))

        grad = Image.new("RGBA", (self.W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(218 * ((gy / 240.0) ** 1.5))
            gd.line([(0, gy), (self.W, gy)], fill=(6, 10, 20, alpha_g))
        canvas.alpha_composite(grad, (0, self.H - 240))

        cd = ImageDraw.Draw(canvas)
        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (32, 28))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 34
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (98, 40))

        # Insignia superior derecha con la Promo de $100 MXN + Moneda Estrella
        badge_x0, badge_y0, badge_x1, badge_y1 = self.W - 332, 26, self.W - 26, 84
        cd.rounded_rectangle(
            (badge_x0, badge_y0, badge_x1, badge_y1),
            radius=18,
            fill=(10, 15, 28, 238),
            outline=(250, 204, 21, 235),
            width=2,
        )
        if self.mario_coin:
            coin_sm = self.mario_coin.resize((38, 38), Image.Resampling.LANCZOS)
            canvas.alpha_composite(coin_sm, (badge_x0 + 12, badge_y0 + 10))
        cd.text(
            (badge_x0 + 60, (badge_y0 + badge_y1) // 2),
            sc.get("promo_badge", "PROMO $100 MXN"),
            font=self.f_badge,
            fill=(250, 204, 21),
            anchor="lm",
        )

        pill_y0, pill_y1 = self.H - 126, self.H - 34
        cd.rounded_rectangle(
            (32, pill_y0, self.W - 32, pill_y1),
            radius=24,
            fill=(12, 16, 26, 242),
            outline=accent + (225,),
            width=2,
        )
        cd.text((self.W // 2, pill_y0 + 30), sc["bottom_pill"], font=self.f_pill, fill=accent, anchor="mm")
        cd.text((self.W // 2, pill_y0 + 64), ">> DREAMCRAFTERS.LAT · SOLO $100 MXN <<", font=self.f_url, fill=(250, 246, 238), anchor="mm")

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def synthesize_elevenlabs_v4_scenes(scenes, api_key, voice_id, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Sintetiza las escenas del comercial usando ElevenLabs `eleven_v4` sobre la voz clonada de Mario.
    SOLO se invoca cuando el usuario pasa explícitamente --elevenlabs-key.
    """
    import requests

    cache_dir = os.path.join(CHAR_02_DIR, "out", "elevenlabs_mario_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.18 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.42 * sr), dtype=np.int16)
    eq_filter = "highpass=f=80,equalizer=f=3400:width_type=o:width=1.4:g=2.8,loudnorm=I=-13.0:TP=-0.8:LRA=7"

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"el_v4_comm|{voice_id}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"el_v4_comm_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav) or os.path.getsize(cached_wav) < 1000:
            print(f"  [ElevenLabs v4 Mario] Generando Escena {idx+1}: {v_text}")
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": v_text,
                    "model_id": "eleven_v4",
                    "voice_settings": {
                        "stability": 0.40,
                        "similarity_boost": 0.92,
                        "style": 0.52,
                        "use_speaker_boost": True,
                    },
                },
                timeout=60,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Error ElevenLabs v4 ({resp.status_code}): {resp.text}")

            raw_mp3 = cached_wav + ".raw.mp3"
            with open(raw_mp3, "wb") as f:
                f.write(resp.content)

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
            print(f"  [ElevenLabs v4 Cache] Reusando Escena {idx+1} desde caché local")

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.path.join(REPO_ROOT, "out", "video_final_dreamcrafters.mp4"))
    parser.add_argument("--recapture", action="store_true", help="Recapturar vistas móviles reales antes de renderizar")
    parser.add_argument(
        "--elevenlabs-key",
        default=os.environ.get(
            "ELEVENLABS_API_KEY_RESTRICTED_CLONING",
            "sk_1a6f82b58f6110efdb8b0cce0b470505b9630bbdf8b69795",
        ),
        help="Llave ElevenLabs con voz clonada de Mario por defecto",
    )
    parser.add_argument("--elevenlabs-voice-id", default="UjVFP9j28dAsNPGkXXOT", help="Voice ID de Mario clonado en ElevenLabs")
    args = parser.parse_args()

    if args.recapture or not os.path.exists(os.path.join(REAL_CAP_DIR, "d_icon_hd.png")):
        from capture_real_mario_mobile import capture_all
        capture_all()

    ffmpeg_path = resolve_ffmpeg_path()
    bgm_rel = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "mario_galaxy_100_voice.wav")

    print("Ensamblando narración clonada de Mario para Super Mario Galaxy ($100 MXN)...")
    if args.elevenlabs_key:
        scenes = synthesize_elevenlabs_v4_scenes(
            SCENES_MARIO_100,
            api_key=args.elevenlabs_key,
            voice_id=args.elevenlabs_voice_id,
            output_wav_path=clean_wav,
            ffmpeg_path=ffmpeg_path,
        )
    else:
        scenes = synthesize_cloned_scenes_local(SCENES_MARIO_100, REF_WAV, clean_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    print("Inicializando motor FeatherTalk ONNX 144x144 para Mario 3D...")
    ft_engine = FeatherTalkMarioEngine(FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)

    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} frames ({total_frames/fps:.1f}s) a velocidad 1.0x real + Escenario Galáctico...")

    renderer = MarioGalaxyCommercialRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_visual_mario_100.mp4")
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

    mixed_wav = os.path.join(out_dir, "mario_galaxy_100_mixed.wav")
    final_audio = mix_voice_with_bgm(clean_wav, bgm_rel, mixed_wav, bgm_vol=0.12, ffmpeg_path=ffmpeg_path)

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
    published_copy = os.path.join(videos_dir, "01_mario_galaxy.mp4")
    if os.path.abspath(args.output) != os.path.abspath(published_copy):
        shutil.copyfile(args.output, published_copy)
    print(f"Video exclusivo Super Mario Galaxy ($100 MXN) listo: {args.output} (y actualizado en {published_copy})")


if __name__ == "__main__":
    main()
