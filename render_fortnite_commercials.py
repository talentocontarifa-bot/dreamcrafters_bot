# -*- coding: utf-8 -*-
"""
render_fortnite_commercials.py
==============================
Genera los 4 Videos Promocionales Oficiales de Fortnite Battle Royale (720x1280 @ 24 FPS, velocidad 1.0x real):
1) `juego_150_hombre`: Comercial Invitación del Juego ($150 MXN) — Versión Hombre (Capitán Jonesy, Voz PRO ElevenLabs + FeatherTalk ONNX)
2) `juego_150_mujer`:  Comercial Invitación del Juego ($150 MXN) — Versión Mujer (Brite Bomber, Voz PRO ElevenLabs + FeatherTalk ONNX)
3) `afiliados_20_hombre`: Comercial Programa de Afiliados 20% — Versión Hombre (Capitán Jonesy)
4) `afiliados_20_mujer`:  Comercial Programa de Afiliados 20% — Versión Mujer (Brite Bomber)
"""

import os
import sys
import glob
import math
import wave
import json
import shutil
import hashlib
import urllib.request
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from render_dreamcrafters_video import (
    REPO_ROOT,
    WEB_ASSETS_DIR,
    LANDING_DIR,
    REAL_CAP_DIR as MARIO_CAP_DIR,
    _crop_face,
    _extract_inner,
    _mask_mouth,
    _trim_silence_pcm,
    load_pil_rgba,
    get_font,
    resolve_ffmpeg_path,
)
from render_fortnite_greetings import (
    _key_green_screen,
    apply_cctv_and_glitch_fx,
)

INV_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\invitacion-fortnite"
FN_ASSETS_DIR = os.path.join(INV_DIR, "assets")
FN_ICONS_DIR = os.path.join(FN_ASSETS_DIR, "icons")
FN_MUSIC_DIR = os.path.join(FN_ASSETS_DIR, "music")
DC_CHAR_05_DIR = os.path.join(REPO_ROOT, "characters", "05_fortnite")
FN_CAP_DIR = os.path.join(DC_CHAR_05_DIR, "real_mobile_capture")
REC_DIR = r"C:\Users\rufin\OneDrive\Documentos\DreamCrafters\Invitaciones\01-Fortnite\00-recursos"
ARTIFACT_DIR = r"C:\Users\rufin\.gemini\antigravity\brain\10e4db52-4bc5-4325-8917-6fe3620cc025"

ELEVENLABS_API_KEY = os.environ.get(
    "ELEVENLABS_API_KEY",
    "sk_1a6f82b58f6110efdb8b0cce0b470505b9630bbdf8b69795",
)

VOICE_IDS = {
    "jonesy": "TX3LPaxmHKxFdv7VOQHJ",  # Liam PRO (Capitán Jonesy)
    "bomber": "FGY2WhTYpPnrIDTdsKH5",  # Laura PRO (Brite Bomber)
}

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4

# ==============================================================================
# GUIONES DE LAS 4 VERSIONES (JUEGO $150 HOMBRE/MUJER + AFILIADOS 20% HOMBRE/MUJER)
# ==============================================================================

SCENES_JUEGO_150_HOMBRE = [
    {
        "type": "hook",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "PAQUETE $150: JUEGO + VIDEO",
        "bottom_pill": "¡JONESY FELICITA A TU PEQUE POR SU NOMBRE!",
        "voice_text": "[excited] ¡¡Atención escuadrón!! ¡Aquí el Capitán Jonesy! [enthusiastic] ¿¡Sabías que por solo ciento cincuenta pesos tu peque puede tener una invitación de Fortnite que es un videojuego real en tres D y además un video mío felicitándolo por su nombre!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "DISPARA A LA PIÑATA 3D",
        "bottom_pill": "MIRA TÁCTICA + GRIETA Y CONFETTI",
        "voice_text": "[excited] ¡¡Mira qué locura!! Tus invitados abren el enlace en su celular, apuntan con la mira táctica, ¡le disparan cinco balazos a la Piñata de Llama tres D y abren una Grieta Dimensional épica de Victoria Magistral con lluvia de confetti!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (217, 70, 239),
        "promo_badge": "SALUDO HD + PASE VIP",
        "bottom_pill": "VIDEO PERSONALIZADO + PASE DESCARGABLE",
        "voice_text": "[enthusiastic] ¡Y eso no es todo! Adentro incluye mi saludo en video de alta definición, el radar con Google Maps y Waze, ¡y un Pase de Batalla V I P descargable con código Q R y confirmación a tu WhatsApp!",
    },
    {
        "type": "website",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "COMBO 2 EN 1: SOLO $150 MXN",
        "bottom_pill": "CÓMPRALA POR $150 EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡Olvida las imágenes aburridas de siempre! Entra ahora mismo a dreamcrafters punto lat y llévate el combo completo de Fortnite con minijuego tres D y saludo en video por solo ciento cincuenta pesos.",
    },
    {
        "type": "cta",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "SOLO $150 MXN · ENTREGA INMEDIATA",
        "bottom_pill": "ACTIVA TU MISIÓN EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡¡Sorprende a todo el escuadrón en el grupo de WhatsApp!! Pídela hoy mismo en dreamcrafters punto lat. ¡¡Nos vemos en la isla!!",
    },
]

SCENES_JUEGO_150_MUJER = [
    {
        "type": "hook",
        "accent_rgb": (217, 70, 239),
        "promo_badge": "PAQUETE $150: JUEGO + VIDEO",
        "bottom_pill": "¡BRITE BOMBER SALUDA A TU PEQUE EN VIDEO!",
        "voice_text": "[excited] ¡¡Hola escuadrón!! ¡Soy Brite Bomber! [enthusiastic] ¿¡Sabías que por solo ciento cincuenta pesos tu peque puede tener una invitación interactiva de Fortnite con minijuego tres D y un video personalizado felicitándolo por su nombre!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "ROMPE LA LLAMA 3D A BALAZOS",
        "bottom_pill": "MIRA TÁCTICA + GRIETA DIMENSIONAL",
        "voice_text": "[excited] ¡¡Mira qué increíble está esto!! Tus invitados entran desde su celular, apuntan con la mira táctica, ¡y le disparan cinco veces a la Piñata de Llama tres D hasta abrir una Grieta Dimensional épica de Victoria Magistral llena de confetti!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "SALUDO HD + PASE VIP",
        "bottom_pill": "MAPA GPS + BOLETO VIP DESCARGABLE",
        "voice_text": "[enthusiastic] ¡Al entrar al lobby ven nuestro saludo en video de alta definición, la ubicación exacta en Google Maps y Waze, y descargan su propio Pase de Batalla V I P para confirmar asistencia por WhatsApp!",
    },
    {
        "type": "website",
        "accent_rgb": (217, 70, 239),
        "promo_badge": "COMBO 2 EN 1: SOLO $150 MXN",
        "bottom_pill": "CÓMPRALA POR $150 EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡Deja atrás las invitaciones estáticas! Entra ya a dreamcrafters punto lat y consigue el combo completo de Fortnite con juego tres D y video por solo ciento cincuenta pesos.",
    },
    {
        "type": "cta",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "SOLO $150 MXN · ENTREGA INMEDIATA",
        "bottom_pill": "ACTIVA TU MISIÓN EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡¡Haz que la fiesta de tu peque sea una Victoria Magistral!! Pídela ahora en dreamcrafters punto lat. ¡¡Allá nos vemos!!",
    },
]

SCENES_AFILIADOS_20_HOMBRE = [
    {
        "type": "hook",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "GANA 20% EN EFECTIVO",
        "bottom_pill": "¡TE PAGAMOS A TI EN VEZ DE A LAS REDES!",
        "voice_text": "[excited] ¡¡Atención escuadrón!! ¡Aquí el Capitán Jonesy! [enthusiastic] Oye, ¿¡y si en lugar de pagarle publicidad a las redes sociales, te pagamos ese dinero directamente a tu cuenta bancaria!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "INVITACIONES QUE SE JUEGAN",
        "bottom_pill": "LA MANDAS AL GRUPO Y TODAS QUIEREN UNA",
        "voice_text": "[excited] ¡En DreamCrafters creamos invitaciones que son videojuegos reales en el celular, donde disparas a la piñata tres D y abres una Grieta Dimensional! Cuando una mamá la manda al grupo de WhatsApp, ¡todas las demás quieren una igual!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (34, 229, 102),
        "promo_badge": "20% DIRECTO A TU CLABE",
        "bottom_pill": "COMISIÓN DIRECTA VÍA SPEI SIN PREGUNTAS",
        "voice_text": "[enthusiastic] ¡Por cada invitación que se compre desde tu enlace personal, te depositamos el veinte por ciento de comisión directa vía transferencia SPEI a tu cuenta, sin preguntas y sin letras chiquitas!",
    },
    {
        "type": "website",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "ALTA GRATIS EN 30 SEGUNDOS",
        "bottom_pill": "DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡Solo entra a dreamcrafters punto lat diagonal socios, registra tu nombre y tu cuenta CLABE, y genera tu link único de afiliado completamente gratis en treinta segundos!",
    },
    {
        "type": "cta",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "PROGRAMA DE SOCIOS 20%",
        "bottom_pill": "ACTIVA TU LINK EN DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡¡Si estás en grupos de mamás del cole o trabajas en fiestas infantiles, entra ya a dreamcrafters punto lat diagonal socios y gana con cada fiesta!! ¡¡Cambio y fuera!!",
    },
]

SCENES_AFILIADOS_20_MUJER = [
    {
        "type": "hook",
        "accent_rgb": (217, 70, 239),
        "promo_badge": "GANA 20% EN EFECTIVO",
        "bottom_pill": "¡TE PAGAMOS A TI EN VEZ DE A LAS REDES!",
        "voice_text": "[excited] ¡¡Hola escuadrón!! ¡Soy Brite Bomber! [enthusiastic] Oigan, ¿¡y si en vez de pagarle publicidad a las redes sociales, te pagamos ese dinero directamente a ti!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "INVITACIONES QUE SE JUEGAN",
        "bottom_pill": "LA MANDAS AL GRUPO Y TODAS QUIEREN UNA",
        "voice_text": "[excited] ¡En DreamCrafters hacemos invitaciones que son videojuegos reales en el celular, con piñata tres D que explota en una Grieta Dimensional! Cuando la mandan al grupo del salón, ¡todas las mamás preguntan dónde la hicieron!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (34, 229, 102),
        "promo_badge": "20% DIRECTO A TU CLABE",
        "bottom_pill": "COMISIÓN DIRECTA VÍA SPEI SIN PREGUNTAS",
        "voice_text": "[enthusiastic] ¡Por cada venta que llegue desde tu link personal, te transferimos el veinte por ciento de comisión directa a tu cuenta bancaria vía SPEI, rápido y sin complicaciones!",
    },
    {
        "type": "website",
        "accent_rgb": (255, 230, 0),
        "promo_badge": "ALTA GRATIS EN 30 SEGUNDOS",
        "bottom_pill": "DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡Activa tu enlace sin costo entrando a dreamcrafters punto lat diagonal socios! Solo pon tu nombre y la cuenta donde quieres recibir tus comisiones en treinta segundos.",
    },
    {
        "type": "cta",
        "accent_rgb": (217, 70, 239),
        "promo_badge": "PROGRAMA DE SOCIOS 20%",
        "bottom_pill": "ACTIVA TU LINK EN DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡¡Comparte tu link en tus grupos de WhatsApp y convierte cada cumpleaños en una Victoria Magistral para tu bolsillo!! Entra ya a dreamcrafters punto lat diagonal socios.",
    },
]


def synthesize_elevenlabs_pro_scenes(scenes, skin_key, output_wav_path, ffmpeg_path="ffmpeg"):
    """Sintetiza cada escena con ElevenLabs `eleven_v4` e histrionismo alto (Liam para Jonesy, Laura para Brite Bomber)."""
    cache_dir = os.path.join(DC_CHAR_05_DIR, "elevenlabs_v4_comm_cache")
    os.makedirs(cache_dir, exist_ok=True)

    voice_id = VOICE_IDS[skin_key]
    sr = 24000
    pause_samples = np.zeros(int(0.18 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)
    eq_filter = "highpass=f=75,equalizer=f=3500:width_type=o:width=1.4:g=3.2,equalizer=f=7500:width_type=o:width=1.5:g=2.4,loudnorm=I=-13.0:TP=-0.8:LRA=7"

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"el_v4_histrionic|{skin_key}|{voice_id}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"fn_v4_{skin_key}_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav) or os.path.getsize(cached_wav) < 1000:
            print(f"  [ElevenLabs v4 Histrionic {skin_key}] Generando Escena {idx+1}: {v_text[:68]}...")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
            payload = {
                "text": v_text,
                "model_id": "eleven_v4",
                "voice_settings": {
                    "stability": 0.20 if skin_key == "jonesy" else 0.18,
                    "similarity_boost": 0.90,
                    "style": 0.88 if skin_key == "jonesy" else 0.90,
                    "use_speaker_boost": True,
                },
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                mp3_bytes = resp.read()

            raw_mp3 = cached_wav + ".raw.mp3"
            with open(raw_mp3, "wb") as f:
                f.write(mp3_bytes)

            subprocess.run(
                [
                    ffmpeg_path, "-y",
                    "-i", raw_mp3,
                    "-af", eq_filter,
                    "-ac", "1",
                    "-ar", str(sr),
                    "-c:a", "pcm_s16le",
                    cached_wav,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if os.path.exists(raw_mp3):
                os.remove(raw_mp3)
        else:
            print(f"  [ElevenLabs Cache {skin_key}] Reusando Escena {idx+1}")

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


class FeatherTalkFortniteCommercialEngine:
    """Motor FeatherTalk ONNX con soporte para audios largos (en bloques de 20s) para Jonesy y Brite Bomber."""

    def __init__(self, skin_key: str, voice_wav_path: str, fps: int = 24, ffmpeg_path: str = "ffmpeg"):
        import onnxruntime as ort

        self.skin_key = skin_key
        self.onnx_dir = os.path.join(DC_CHAR_05_DIR, f"{skin_key}_onnx")
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path

        hubert_path = os.path.join(self.onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(self.onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(self.onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(self.onnx_dir, "closed_win.npy")
        video_path = os.path.join(self.onnx_dir, f"{skin_key}_25fps.mp4")
        ref_0_path = os.path.join(self.onnx_dir, "ref_0.jpg")

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

        n_valid = min(len(self.base_frames), len(self.bboxes))
        base_seq = list(range(0, n_valid))
        self.ping_pong = base_seq + base_seq[-2:0:-1]
        self.pp_cursor = 0

        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[16:134, 14:130] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (17, 17), 4.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio_chunked(voice_wav_path, fps=fps)

    def _analyze_audio_chunked(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k_comm.wav"
        subprocess.run(
            [
                self.ffmpeg_path, "-y",
                "-i", voice_wav_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
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

    def synthesize_char_rgba(self, frame_idx: int) -> tuple[Image.Image, float]:
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

        mod_f = frame_idx % 28
        glitch = 0.48 if mod_f == 14 else (0.24 if mod_f == 15 else 0.0)
        return _key_green_screen(frame_bgr), glitch


class FortniteCommercialRenderer:
    def __init__(self, ft_engine: FeatherTalkFortniteCommercialEngine, skin_key: str, mode: str = "juego_150"):
        self.ft = ft_engine
        self.skin_key = skin_key
        self.mode = mode  # "juego_150" or "afiliados_20"
        self.W = 720
        self.H = 1280

        # Fondo Isla de Fortnite
        island_path = os.path.join(FN_ASSETS_DIR, "island_bg.webp")
        raw_island = load_pil_rgba(island_path)
        if raw_island:
            iw, ih = raw_island.size
            scale_i = max(self.W / float(iw), self.H / float(ih))
            nw, nh = int(iw * scale_i), int(ih * scale_i)
            i_res = raw_island.resize((nw, nh), Image.Resampling.LANCZOS)
            lx = (nw - self.W) // 2
            ly = (nh - self.H) // 2
            i_crop = i_res.crop((lx, ly, lx + self.W, ly + self.H)).filter(ImageFilter.GaussianBlur(radius=2.2))
            dark_veil = Image.new("RGBA", (self.W, self.H), (7, 10, 24, 105))
            self.island_stage_bg = Image.alpha_composite(i_crop, dark_veil)
        else:
            self.island_stage_bg = Image.new("RGBA", (self.W, self.H), (7, 10, 24, 255))

        self.battle_bus = load_pil_rgba(os.path.join(FN_ASSETS_DIR, "battle_bus.webp"), (145, 256))
        self.victory_crown = load_pil_rgba(os.path.join(FN_ICONS_DIR, "10-icon-pase-vip.webp"), (52, 52))
        self.vip_icon = load_pil_rgba(os.path.join(FN_ICONS_DIR, "06-icon-botin-cofre.webp"), (68, 68))

        d_icon_path = os.path.join(MARIO_CAP_DIR, "d_icon_hd.png")
        self.d_icon_hd = load_pil_rgba(d_icon_path)
        self.d_icon_header = load_pil_rgba(d_icon_path, (54, 56))

        raw_logo = load_pil_rgba(os.path.join(LANDING_DIR, "logo-text.png"))
        if raw_logo:
            _, _, _, a_c = raw_logo.split()
            white_rgb = Image.new("RGB", raw_logo.size, (250, 246, 238))
            self.logo_text = Image.merge("RGBA", (*white_rgb.split(), a_c))
        else:
            self.logo_text = None

        self.gameplay_frames = sorted(glob.glob(os.path.join(FN_CAP_DIR, "gameplay", "frame_*.png")))
        unlocked_sub = f"unlocked_{skin_key}"
        self.unlocked_frames = sorted(glob.glob(os.path.join(FN_CAP_DIR, unlocked_sub, "frame_*.png")))

        rng = np.random.RandomState(2026)
        palette_rgb = [(0, 229, 255), (255, 230, 0), (217, 70, 239), (255, 255, 255)]
        self.storm_particles = []
        for _ in range(55):
            self.storm_particles.append(
                {
                    "x0": float(rng.uniform(0, self.W)),
                    "y0": float(rng.uniform(0, self.H * 0.85)),
                    "r": float(rng.uniform(1.2, 2.8)),
                    "speed": float(rng.uniform(0.8, 2.5)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "color": palette_rgb[int(rng.randint(0, len(palette_rgb)))],
                }
            )

        self.f_pill = get_font(20, bold=True)
        self.f_badge = get_font(17, bold=True, mono=True)
        self.f_url = get_font(18, mono=True)
        self.f_intro_sub = get_font(21, bold=True, mono=True)
        self.f_nav_label = get_font(19, bold=True)
        self.f_nav_url = get_font(30, bold=True, mono=True)
        self.f_nav_hint = get_font(18, bold=True)

    def render_fortnite_stage_bg(self, idx):
        canvas = self.island_stage_bg.copy()
        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        for pt in self.storm_particles:
            x = (pt["x0"] - idx * pt["speed"]) % self.W
            y = (pt["y0"] + math.sin(idx * 0.08 + pt["phase"]) * 8.0) % (self.H * 0.88)
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(idx * 0.14 + pt["phase"]))
            alpha = int(round(220 * tw))
            r = pt["r"]
            od.ellipse((x - r, y - r, x + r, y + r), fill=pt["color"] + (alpha,))

        floor_y = 1095
        od.line([(0, floor_y), (self.W, floor_y)], fill=(0, 229, 255, 200), width=4)
        od.line([(0, floor_y + 4), (self.W, floor_y + 4)], fill=(217, 70, 239, 130), width=2)
        canvas.alpha_composite(ov)

        if self.battle_bus:
            bob_bus = int(12 * math.sin(idx * 0.10))
            canvas.alpha_composite(self.battle_bus, (30, 140 + bob_bus))
        if self.vip_icon:
            bob_vip = int(10 * math.cos(idx * 0.12))
            canvas.alpha_composite(self.vip_icon, (self.W - 108, 220 + bob_vip))

        return canvas

    def _overlay_typing_browser_box(self, canvas: Image.Image, t_in_sc: float, sc_dur: float) -> Image.Image:
        alpha_u = 1.0
        if t_in_sc < 0.22:
            alpha_u = t_in_sc / 0.22
        elif t_in_sc > sc_dur - 0.28:
            alpha_u = max(0.0, (sc_dur - t_in_sc) / 0.28)

        if alpha_u <= 0.02:
            return canvas

        is_aff = self.mode == "afiliados_20"
        target_text = "dreamcrafters.lat/socios" if is_aff else "dreamcrafters.lat"
        type_prog = min(1.0, max(0.0, (t_in_sc - 0.15) / 1.85))
        n_chars = int(round(type_prog * len(target_text)))
        typed_str = target_text[:n_chars]
        is_complete = n_chars >= len(target_text)

        bx0, by0, bx1, by1 = 24, 445, self.W - 24, 785
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=18))

        glass_card = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass_card.paste(crop_region, (0, 0))
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (8, 12, 30, int(232 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (255, 230, 0, int(248 * alpha_u)) if is_complete else (0, 229, 255, int(235 * alpha_u))
        od.rounded_rectangle((bx0, by0, bx1, by1), radius=32, outline=border_col, width=3)

        top_label = "GENERA TU LINK EN 30 SEGUNDOS:" if is_aff else "ESCRIBE EN TU NAVEGADOR:"
        od.text(
            (self.W // 2, by0 + 44),
            top_label,
            font=self.f_nav_label,
            fill=(0, 229, 255, int(245 * alpha_u)),
            anchor="mm",
        )

        bar_x0, bar_y0, bar_x1, bar_y1 = bx0 + 22, by0 + 82, bx1 - 22, by0 + 182
        od.rounded_rectangle(
            (bar_x0, bar_y0, bar_x1, bar_y1),
            radius=22,
            fill=(5, 8, 20, int(248 * alpha_u)),
            outline=border_col,
            width=2,
        )

        cursor_on = (not is_complete) or (int(t_in_sc * 6) % 2 == 0)
        display_url = typed_str + ("|" if cursor_on and not is_complete else "")
        text_col = (255, 230, 0, int(255 * alpha_u)) if is_complete else (255, 255, 255, int(255 * alpha_u))
        od.text(
            (bar_x0 + 28, (bar_y0 + bar_y1) // 2),
            display_url,
            font=self.f_pill if is_aff else self.f_nav_url,
            fill=text_col,
            anchor="lm",
        )

        if is_complete and not is_aff:
            go_x0, go_y0, go_x1, go_y1 = bar_x1 - 92, bar_y0 + 18, bar_x1 - 18, bar_y1 - 18
            od.rounded_rectangle((go_x0, go_y0, go_x1, go_y1), radius=14, fill=(255, 230, 0, int(250 * alpha_u)))
            od.text(((go_x0 + go_x1) // 2, (go_y0 + go_y1) // 2), "IR →", font=self.f_nav_label, fill=(10, 14, 26, int(255 * alpha_u)), anchor="mm")

        line1 = "★ GANA 20% DE COMISIÓN DIRECTA VÍA SPEI ★" if is_aff else "★ FORTNITE BATTLE ROYALE · COMBO $150 MXN ★"
        line2 = "REGISTRA TU CLABE Y COMPARTE EN WHATSAPP" if is_aff else "PIÑATA 3D + SALUDO EN VIDEO + PASE VIP HD"
        od.text((self.W // 2, by1 - 68), line1, font=self.f_nav_hint, fill=(255, 230, 0, int(250 * alpha_u)), anchor="mm")
        od.text((self.W // 2, by1 - 32), line2, font=self.f_url, fill=(0, 229, 255, int(245 * alpha_u)), anchor="mm")

        out.alpha_composite(ov)
        return out

    def render_logo_outro_frame(self, outro_prog, idx=0):
        canvas = self.render_fortnite_stage_bg(idx)
        dark_overlay = Image.new("RGBA", (self.W, self.H), (6, 9, 22, int(212 * min(1.0, outro_prog * 1.8))))
        canvas = Image.alpha_composite(canvas, dark_overlay)

        halo_alpha = int(160 * min(1.0, outro_prog * 2.2))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(185 + 45 * math.sin(outro_prog * math.pi * 2.0))
            cx, cy = self.W // 2, self.H // 2 - 55
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(0, 229, 255, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(255, 230, 0, halo_alpha // 4))
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

            is_aff = self.mode == "afiliados_20"
            txt_overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            tod = ImageDraw.Draw(txt_overlay)
            sub_txt = "PROGRAMA DE SOCIOS · GANA 20% VÍA SPEI" if is_aff else "FORTNITE BATTLE ROYALE · COMBO $150 MXN"
            tod.text(
                (self.W // 2, self.H // 2 + 236),
                sub_txt,
                font=self.f_intro_sub,
                fill=(255, 230, 0, int(250 * txt_alpha)),
                anchor="mm",
            )
            pill_y0, pill_y1 = self.H - 126, self.H - 34
            tod.rounded_rectangle(
                (32, pill_y0, self.W - 32, pill_y1),
                radius=24,
                fill=(10, 14, 28, int(242 * txt_alpha)),
                outline=(0, 229, 255, int(225 * txt_alpha)),
                width=2,
            )
            pill_top = "ACTIVA TU LINK EN DREAMCRAFTERS.LAT/SOCIOS" if is_aff else "PÍDELA POR $150 EN DREAMCRAFTERS.LAT"
            pill_bot = ">> DREAMCRAFTERS.LAT/SOCIOS <<" if is_aff else ">> DREAMCRAFTERS.LAT <<"
            tod.text((self.W // 2, pill_y0 + 30), pill_top, font=self.f_pill, fill=(0, 229, 255, int(255 * txt_alpha)), anchor="mm")
            tod.text((self.W // 2, pill_y0 + 64), pill_bot, font=self.f_url, fill=(255, 230, 0, int(255 * txt_alpha)), anchor="mm")
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
            ending_logo_start_sec = max(2.4, sc_dur - 2.3)
            if t_in_sc >= ending_logo_start_sec:
                outro_prog = min(1.0, (t_in_sc - ending_logo_start_sec) / max(0.1, sc_dur - ending_logo_start_sec))
                return self.render_logo_outro_frame(outro_prog, idx=idx)

        if sc_type == "gameplay" and self.gameplay_frames:
            f_idx = min(len(self.gameplay_frames) - 1, local_frame_idx)
            canvas = Image.open(self.gameplay_frames[f_idx]).convert("RGBA")
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if sc_type == "unlocked" and self.unlocked_frames:
            f_idx = min(len(self.unlocked_frames) - 1, local_frame_idx)
            canvas = Image.open(self.unlocked_frames[f_idx]).convert("RGBA")
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if sc_type == "website" and self.unlocked_frames:
            # Mostrar el final de la invitación (tarjeta de Pase VIP y promo $150) con el navegador tipeando encima
            f_idx = min(len(self.unlocked_frames) - 1, max(0, len(self.unlocked_frames) - 65 + (local_frame_idx % 65)))
            canvas = Image.open(self.unlocked_frames[f_idx]).convert("RGBA")
            canvas = self._overlay_typing_browser_box(canvas, t_in_sc, sc_dur)
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Personaje Fortnite (Jonesy o Brite Bomber) con Lip-Sync + CCTV atenuado
        accent = sc["accent_rgb"]
        canvas = self.render_fortnite_stage_bg(idx)

        char_rgba, glitch_lvl = self.ft.synthesize_char_rgba(idx)
        canvas.alpha_composite(char_rgba, (0, 20))

        cam_id = "CAM-01 // JONESY-HQ" if self.skin_key == "jonesy" else "CAM-02 // BOMBER-HQ"
        canvas = apply_cctv_and_glitch_fx(
            canvas,
            frame_idx=idx,
            glitch_level=glitch_lvl,
            accent_rgb=accent,
            cam_id=cam_id,
            intensity=0.45,
        )

        grad = Image.new("RGBA", (self.W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(222 * ((gy / 240.0) ** 1.5))
            gd.line([(0, gy), (self.W, gy)], fill=(6, 10, 22, alpha_g))
        canvas.alpha_composite(grad, (0, self.H - 240))

        cd = ImageDraw.Draw(canvas)
        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (32, 24))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 34
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (98, 36))

        badge_x0, badge_y0, badge_x1, badge_y1 = self.W - 344, 22, self.W - 24, 80
        cd.rounded_rectangle(
            (badge_x0, badge_y0, badge_x1, badge_y1),
            radius=18,
            fill=(9, 13, 28, 242),
            outline=(255, 230, 0, 240),
            width=2,
        )
        if self.victory_crown:
            crown_sm = self.victory_crown.resize((38, 38), Image.Resampling.LANCZOS)
            canvas.alpha_composite(crown_sm, (badge_x0 + 12, badge_y0 + 10))
        cd.text(
            (badge_x0 + 58, (badge_y0 + badge_y1) // 2),
            sc.get("promo_badge", "PROMO $150 MXN"),
            font=self.f_badge,
            fill=(255, 230, 0),
            anchor="lm",
        )

        pill_y0, pill_y1 = self.H - 126, self.H - 34
        cd.rounded_rectangle(
            (28, pill_y0, self.W - 28, pill_y1),
            radius=24,
            fill=(10, 14, 28, 245),
            outline=accent + (235,),
            width=2,
        )
        cd.text((self.W // 2, pill_y0 + 30), sc["bottom_pill"], font=self.f_pill, fill=accent, anchor="mm")
        bot_url = ">> DREAMCRAFTERS.LAT/SOCIOS · GANA 20% <<" if self.mode == "afiliados_20" else ">> DREAMCRAFTERS.LAT · SOLO $150 MXN <<"
        cd.text((self.W // 2, pill_y0 + 64), bot_url, font=self.f_url, fill=(250, 246, 238), anchor="mm")

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def mix_commercial_audio_with_sfx(voice_wav_path, bgm_path, gameplay_start_sec, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Mezcla la narración PRO con la música Funk Breakbeat de Fortnite + los 5 disparos reales (`sfx_gunshot.mp3`)
    y la explosión de la Grieta Dimensional (`sfx_victory_rift.mp3`) sincronizados con la escena `gameplay`.
    """
    shot_mp3 = os.path.join(FN_ASSETS_DIR, "sfx_gunshot.mp3")
    rift_mp3 = os.path.join(FN_ASSETS_DIR, "sfx_victory_rift.mp3")

    # Tiempos de disparo en `capture_real_fortnite_mobile.py` (1.0x): frames 12, 30, 48, 66, 84 (@24fps)
    shot_delays_ms = [int(round((gameplay_start_sec + f / 24.0) * 1000)) for f in (12, 30, 48, 66, 84)]
    rift_delay_ms = int(round((gameplay_start_sec + 85 / 24.0) * 1000))

    inputs = ["-i", voice_wav_path, "-i", bgm_path]
    for _ in shot_delays_ms:
        inputs.extend(["-i", shot_mp3])
    inputs.extend(["-i", rift_mp3])

    fc_parts = [
        "[0:a]volume=1.05[v]",
        "[1:a]volume=0.14,aloop=loop=-1:size=2e+09[b]",
    ]
    mix_labels = ["[v]", "[b]"]
    for idx_s, d_ms in enumerate(shot_delays_ms):
        in_idx = 2 + idx_s
        lbl = f"[sh{idx_s}]"
        fc_parts.append(f"[{in_idx}:a]volume=0.42,adelay={d_ms}|{d_ms}{lbl}")
        mix_labels.append(lbl)

    rift_in_idx = 2 + len(shot_delays_ms)
    fc_parts.append(f"[{rift_in_idx}:a]volume=0.52,adelay={rift_delay_ms}|{rift_delay_ms}[rf]")
    mix_labels.append("[rf]")

    n_in = len(mix_labels)
    fc_parts.append(f"{''.join(mix_labels)}amix=inputs={n_in}:duration=first:dropout_transition=2,alimiter=limit=0.96[out]")

    subprocess.run(
        [
            ffmpeg_path, "-y",
            *inputs,
            "-filter_complex", ";".join(fc_parts),
            "-map", "[out]",
            "-ac", "2",
            "-ar", "44100",
            "-c:a", "pcm_s16le",
            output_wav_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_wav_path


def render_single_commercial(variant_id, skin_key, mode, scenes_template, out_filename, rec_filename):
    ffmpeg_path = resolve_ffmpeg_path()
    out_dir = os.path.join(REPO_ROOT, "out", "fortnite_commercials")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(REC_DIR, exist_ok=True)

    clean_wav = os.path.join(out_dir, f"voice_{variant_id}.wav")
    print(f"\n=======================================================")
    print(f"Cocinando Comercial: {variant_id} ({skin_key} / {mode})")
    print(f"=======================================================")

    scenes = synthesize_elevenlabs_pro_scenes(
        scenes_template,
        skin_key=skin_key,
        output_wav_path=clean_wav,
        ffmpeg_path=ffmpeg_path,
    )

    fps = 24
    ft_engine = FeatherTalkFortniteCommercialEngine(skin_key, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)
    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} cuadros ({total_frames/fps:.1f}s) en HD 720x1280...")

    renderer = FortniteCommercialRenderer(ft_engine, skin_key=skin_key, mode=mode)
    temp_video = os.path.join(out_dir, f"temp_vis_{variant_id}.mp4")
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

    gameplay_start = next((sc["start"] for sc in scenes if sc["type"] == "gameplay"), 8.0)
    bgm_path = os.path.join(FN_MUSIC_DIR, "track_going_faster.mp3")
    mixed_wav = os.path.join(out_dir, f"mixed_{variant_id}.wav")
    mix_commercial_audio_with_sfx(clean_wav, bgm_path, gameplay_start, mixed_wav, ffmpeg_path=ffmpeg_path)

    final_mp4 = os.path.join(out_dir, out_filename)
    subprocess.run(
        [
            ffmpeg_path, "-y",
            "-i", temp_video,
            "-i", mixed_wav,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            final_mp4,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.path.exists(temp_video):
        os.remove(temp_video)

    rec_copy = os.path.join(REC_DIR, rec_filename)
    shutil.copyfile(final_mp4, rec_copy)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    art_copy = os.path.join(ARTIFACT_DIR, out_filename)
    shutil.copyfile(final_mp4, art_copy)
    promos_dir = os.path.join(FN_ASSETS_DIR, "promos")
    os.makedirs(promos_dir, exist_ok=True)
    shutil.copyfile(final_mp4, os.path.join(promos_dir, out_filename))

    videos_queue_map = {
        "juego_150_hombre": "01_fortnite_juego_150_hombre.mp4",
        "afiliados_20_hombre": "03_fortnite_afiliados_20_hombre.mp4",
        "juego_150_mujer": "04_fortnite_juego_150_mujer.mp4",
        "afiliados_20_mujer": "05_fortnite_afiliados_20_mujer.mp4",
    }
    if variant_id in videos_queue_map:
        videos_dir = os.path.join(REPO_ROOT, "videos")
        os.makedirs(videos_dir, exist_ok=True)
        shutil.copyfile(final_mp4, os.path.join(videos_dir, videos_queue_map[variant_id]))

    sz_mb = os.path.getsize(final_mp4) / (1024.0 * 1024.0)
    print(f"  -> Listo: {final_mp4} ({sz_mb:.2f} MB)")
    print(f"  -> Copiado a: {rec_copy} y {art_copy}")


def main():
    if "--recapture" in sys.argv or not os.path.exists(os.path.join(FN_CAP_DIR, "gameplay", "frame_0100.png")):
        from capture_real_fortnite_mobile import capture_all
        capture_all()

    variants = [
        (
            "juego_150_hombre",
            "jonesy",
            "juego_150",
            SCENES_JUEGO_150_HOMBRE,
            "video_fortnite_juego_150_hombre.mp4",
            "19-promo-juego-150-hombre-jonesy.mp4",
        ),
        (
            "juego_150_mujer",
            "bomber",
            "juego_150",
            SCENES_JUEGO_150_MUJER,
            "video_fortnite_juego_150_mujer.mp4",
            "20-promo-juego-150-mujer-bomber.mp4",
        ),
        (
            "afiliados_20_hombre",
            "jonesy",
            "afiliados_20",
            SCENES_AFILIADOS_20_HOMBRE,
            "video_fortnite_afiliados_20_hombre.mp4",
            "21-promo-afiliados-20-hombre-jonesy.mp4",
        ),
        (
            "afiliados_20_mujer",
            "bomber",
            "afiliados_20",
            SCENES_AFILIADOS_20_MUJER,
            "video_fortnite_afiliados_20_mujer.mp4",
            "22-promo-afiliados-20-mujer-bomber.mp4",
        ),
    ]

    for v in variants:
        render_single_commercial(*v)


if __name__ == "__main__":
    main()
