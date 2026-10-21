# -*- coding: utf-8 -*-
"""
render_dreamcrafters_video.py — Motor Oficial de Video Promocional DreamCrafters (FeatherTalk ONNX + HF Chatterbox)
===================================================================================================================
- Avatar 3D de Mario con Lip-Sync Neuronal Continuo (`FeatherTalk 144x144` + `FeatherHuBERT` en ONNX):
  * Reemplaza el rig estático por el video 3D de Mario entrenado en FeatherTalk (`characters/02_mario/feathertalk_onnx`).
  * Ciclo ping-pong estabilizado (`frames 24..248`), fusión elíptica sin costuras y boca cerrada natural en pausas.
  * Chroma key con despill suave sobre el fondo bokeh de fiesta (`party_bg.jpeg`) y sombra de contacto.
- Clonación de Voz de Alta Fidelidad desde Hugging Face (`ResembleAI/Chatterbox-Multilingual-TTS` / `ResembleAI/chatterbox`)
  usando la referencia limpia de frase completa (`mario_ref_8s.wav`), con caché persistente por SHA-256 en
  `characters/02_mario/out/cloned_voice_cache`.
- Invitación real `/invitacionmario/index.html` y `dreamcrafters.lat` mostradas a PANTALLA COMPLETA (720x1280)
  durante las escenas `gameplay`, `unlocked` y `website`.
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
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
FEATHERTALK_ONNX_DIR = os.path.join(CHAR_02_DIR, "feathertalk_onnx")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
REF_WAV = os.path.join(CHAR_02_DIR, "mario_ref_8s.wav")
REAL_CAP_DIR = os.path.join(CHAR_02_DIR, "out", "real_mobile_capture")
INTRO_DURATION_SEC = 1.30

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)


SCENES_CLEAN = [
    {
        "type": "hook",
        "accent_rgb": (56, 189, 248),
        "top_caption": "¿OTRA IMAGEN FIJA EN WHATSAPP?",
        "bottom_pill": "INVITACIONES QUE SE JUEGAN EN TU CEL",
        "voice_text": "¡Hola amigos! Soy yo, Mario. ¿Todavía mandas invitaciones aburridas de imagen fija por Guatsap? ¡En Drim Crafters convertimos tu invitación en un videojuego real!",
    },
    {
        "type": "gameplay",
        "accent_rgb": (250, 204, 21),
        "top_caption": "TUS INVITADOS JUEGAN PARA ENTRAR",
        "bottom_pill": "ATRAPA 50 PUNTOS SIN INSTALAR APPS",
        "voice_text": "¡Mira qué divertido! Tus invitados abren el enlace en su celular y tienen que atrapar las monedas espaciales para desbloquear todos los detalles de tu fiesta.",
    },
    {
        "type": "unlocked",
        "accent_rgb": (56, 189, 248),
        "top_caption": "CUENTA REGRESIVA + MAPA GPS",
        "bottom_pill": "CONFIRMACIÓN EN 1 TOQUE A WHATSAPP",
        "voice_text": "Al lograr la misión, se abre la invitación con música épica, cuenta regresiva, mapa exacto en Gúgol Maps y botón para confirmar asistencia directo a tu Guatsap.",
    },
    {
        "type": "website",
        "accent_rgb": (74, 222, 128),
        "top_caption": "CREA LA DE MINECRAFT GRATIS",
        "bottom_pill": "PERSONALIZA EN 60 SEG EN DREAMCRAFTERS.LAT",
        "voice_text": "Además, si entras ahora a drim crafters punto lat, puedes escribir el nombre y la edad de tu festejado y crear gratis la invitación interactiva de Maincraft en un minuto.",
    },
    {
        "type": "cta",
        "accent_rgb": (250, 204, 21),
        "top_caption": "¡SORPRENDE A TODO EL SALÓN!",
        "bottom_pill": "VISITA HOY DREAMCRAFTERS.LAT",
        "voice_text": "¡Muchas felicidades! Te esperamos hoy en drim crafters punto lat. ¡Drim Crafters, artificialmente hechos a mano!",
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


def generate_intro_chime_pcm(duration_sec=1.30, sr=24000):
    n_samples = int(duration_sec * sr)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False)
    freqs = [523.25, 659.25, 783.99, 1174.66]
    sig = np.zeros_like(t)
    for idx_f, f in enumerate(freqs):
        onset = 0.08 + idx_f * 0.06
        t_rel = np.maximum(0.0, t - onset)
        env = np.where(t >= onset, np.exp(-t_rel * 4.5) * (1.0 - np.exp(-t_rel * 45.0)), 0.0)
        sig += np.sin(2.0 * np.pi * f * t_rel) * env * 0.14

    sub_env = np.exp(-t * 6.0) * (1.0 - np.exp(-t * 60.0))
    sig += np.sin(2.0 * np.pi * 130.81 * t) * sub_env * 0.18
    sig = np.clip(sig, -0.9, 0.9)
    return (sig * 32767.0).astype(np.int16)


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
    Usa las pistas clonadas de alta fidelidad de Mario (`ResembleAI/Chatterbox-Multilingual-TTS` en Hugging Face)
    guardadas en `characters/02_mario/out/cloned_voice_cache`. Si alguna línea cambia, la clona
    automáticamente desde Hugging Face (`ResembleAI/Chatterbox-Multilingual-TTS`) o el modelo local.
    """
    cache_dir = os.path.join(CHAR_02_DIR, "out", "cloned_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    intro_pcm = generate_intro_chime_pcm(INTRO_DURATION_SEC, sr=sr)
    pause_samples = np.zeros(int(0.24 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)

    all_pcm = [intro_pcm]
    cur_time = round(len(intro_pcm) / float(sr), 3)

    updated_scenes = [
        {
            "type": "logo_intro",
            "accent_rgb": (56, 189, 248),
            "top_caption": "",
            "bottom_pill": "",
            "start": 0.0,
            "end": cur_time,
            "audio_duration": cur_time,
        }
    ]

    hf_token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HF_API_KEY")
        or os.environ.get("HUGGINGFACE_TOKEN")
        or None
    )

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"chatterbox_hf_mario_v2|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"mario_cb_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav):
            print(f"[HuggingFace Chatterbox-Multilingual-TTS] Clonando voz de Mario para Escena {idx+1}...")
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
                            "highpass=f=80,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=100:makeup=2dB,loudnorm=I=-14.0:TP=-1.0:LRA=6",
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
                print(f"  [Aviso HF Space Chatterbox]: {e}")

            if not cloned_ok:
                import torch
                import torchaudio
                import perth

                class _DummyWatermarker:
                    def apply_watermark(self, wav, sample_rate=None):
                        return wav

                perth.PerthImplicitWatermarker = _DummyWatermarker
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS

                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                torch.manual_seed(42)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed(42)
                wav_tensor = model.generate(
                    v_text,
                    language_id="es",
                    audio_prompt_path=ref_wav_path,
                    exaggeration=0.55,
                    temperature=0.7,
                    cfg_weight=0.5,
                )
                raw_src = os.path.join(cache_dir, f"_src_cb_sc_{idx+1}.wav")
                torchaudio.save(raw_src, wav_tensor.cpu(), model.sr)
                subprocess.run(
                    [
                        ffmpeg_path,
                        "-y",
                        "-i",
                        raw_src,
                        "-af",
                        "highpass=f=80,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=100:makeup=2dB,loudnorm=I=-14.0:TP=-1.0:LRA=6",
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
            sc_copy["end"] = round(cur_time + dur + 0.24, 3)
            cur_time += dur + 0.24
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

        # Cargar los 250 fotogramas base de Mario a 25fps
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

        # Limitar la máscara neuronal exclusivamente a la zona de boca/bigote/mentón (MASK_RECT escalado a 144x144: x=15..129, y=54..126)
        # para no re-escalar ni alterar ojos, nariz o gorra del render 3D original.
        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[50:128, 15:129] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (27, 27), 7.0)[..., None]

        # Extraer características HuBERT a 25Hz y energía RMS por frame del audio completo
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

        # Calcular RMS por frame a `fps`
        rms_arr = np.zeros(total_frames, dtype=np.float32)
        win_samples = int(0.05 * sr)
        for i in range(total_frames):
            c_idx = int((i / float(fps)) * sr)
            s_i = max(0, c_idx - win_samples // 2)
            e_i = min(len(wav_f), c_idx + win_samples // 2)
            if e_i > s_i:
                rms_arr[i] = float(np.sqrt(np.mean(wav_f[s_i:e_i] ** 2)))

        # Extraer FeatherHuBERT por bloques de 20s con solapamiento de 1s y padding de 0.5s en los extremos
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
        masked = _mask_mouth(inner.copy(), inner_size=FACE_INNER_SIZE)

        inp_chw = np.concatenate([self.ref_inner, masked], axis=2).transpose(2, 0, 1).astype(np.float32) / 255.0
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


class CleanDreamCraftersRenderer:
    def __init__(self, ft_engine: FeatherTalkMarioEngine):
        self.ft = ft_engine
        self.W = 720
        self.H = 1280

        party_bg_path = os.path.join(CHAR_02_DIR, "party_bg.jpeg")
        self.party_bg = load_pil_rgba(party_bg_path, (self.W, self.H))

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
            f"Frames moviles reales cargados (Pantalla Completa 720x1280): gameplay={len(self.gameplay_frames)}, "
            f"unlocked={len(self.unlocked_frames)}, website={len(self.website_frames)}"
        )

        # Base oscura cósmica estilo Super Mario Galaxy (#040613 -> #0c1c44)
        bg_arr = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        y_grid, x_grid = np.ogrid[: self.H, : self.W]
        dist = np.sqrt(((x_grid - self.W * 0.48) / 390.0) ** 2 + ((y_grid - self.H * 0.44) / 540.0) ** 2)
        glow = np.clip(1.0 - dist, 0.0, 1.0) ** 1.55
        dist2 = np.sqrt(((x_grid - self.W * 0.25) / 310.0) ** 2 + ((y_grid - self.H * 0.28) / 420.0) ** 2)
        nebula = np.clip(1.0 - dist2, 0.0, 1.0) ** 2.0
        bg_arr[:, :, 0] = np.clip(4 + glow * 14 + nebula * 24, 0, 255).astype(np.uint8)
        bg_arr[:, :, 1] = np.clip(6 + glow * 26 + nebula * 12, 0, 255).astype(np.uint8)
        bg_arr[:, :, 2] = np.clip(19 + glow * 58 + nebula * 42, 0, 255).astype(np.uint8)
        self.clean_dark_bg = Image.fromarray(bg_arr).convert("RGBA")

        rng = np.random.RandomState(2026)
        palette_rgb = [
            (255, 255, 255),
            (255, 224, 85),
            (56, 232, 255),
            (255, 61, 127),
        ]
        self.cosmic_dots = []
        for _ in range(70):
            self.cosmic_dots.append(
                {
                    "x0": float(rng.uniform(0, self.W)),
                    "y0": float(rng.uniform(0, self.H * 0.90)),
                    "r": float(rng.uniform(1.0, 2.4)),
                    "speed": float(rng.uniform(0.55, 2.1)),
                    "phase": float(rng.uniform(0, math.pi * 2)),
                    "twinkle": float(rng.uniform(0.08, 0.18)),
                    "color": palette_rgb[int(rng.randint(0, len(palette_rgb)))],
                }
            )

        self.cosmic_sparks = []
        for _ in range(28):
            self.cosmic_sparks.append(
                {
                    "x0": float(rng.uniform(20, self.W - 20)),
                    "y0": float(rng.uniform(35, self.H * 0.86)),
                    "size": float(rng.uniform(5.5, 11.5)),
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

        if self.party_bg:
            cv_party = cv2.cvtColor(np.array(self.party_bg.convert("RGB")), cv2.COLOR_RGB2BGR)
            cv_blur = cv2.GaussianBlur(cv_party, (45, 45), 18)
            cv_dark = (cv_blur.astype(np.float32) * 0.42).astype(np.uint8)
            self.party_bokeh_bg = Image.fromarray(cv2.cvtColor(cv_dark, cv2.COLOR_BGR2RGB)).convert("RGBA")
        else:
            self.party_bokeh_bg = self.clean_dark_bg

        self.f_top_title = get_font(27, bold=True)
        self.f_pill = get_font(20, bold=True)
        self.f_url = get_font(18, mono=True)
        self.f_intro_sub = get_font(21, bold=True, mono=True)

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
        canvas = self.clean_dark_bg.copy()
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
            alpha = 0.28 + 0.72 * (0.5 + 0.5 * s_val)
            cur_size = sp["size"] * (0.72 + 0.34 * s_val)
            self._draw_four_point_spark(od, x, y, cur_size, sp["color"], alpha)

        for slot in range(2):
            period = 42
            local_f = (idx + slot * 21) % period
            cycle_id = (idx + slot * 21) // period
            if local_f < 30:
                prog_c = local_f / 30.0
                life = math.sin(prog_c * math.pi)
                pal = self.comet_palettes[(cycle_id + slot) % len(self.comet_palettes)]

                start_x = self.W * (0.88 if slot == 0 else 0.62) + ((cycle_id * 97) % 140) - 50
                start_y = 65 + ((cycle_id * 73 + slot * 160) % 340)
                angle = math.pi * (0.74 if slot == 0 else 0.77)
                speed_c = 15.5
                dist_c = local_f * speed_c
                cx = start_x + math.cos(angle) * dist_c
                cy = start_y + math.sin(angle) * dist_c
                tail_len = 125.0
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
                    seg_alpha = int(round(230 * life * ((1.0 - u0) ** 1.5)))
                    width_s = max(1, int(round(4.2 * (1.0 - u0 * 0.7))))
                    if seg_alpha > 4:
                        od.line([(p0x, p0y), (p1x, p1y)], fill=pal["tail"] + (seg_alpha,), width=width_s)

                self._draw_four_point_spark(od, cx, cy, 9.5, pal["head"], min(1.0, life * 1.15))

        canvas.alpha_composite(overlay)
        return canvas

    def render_logo_intro_frame(self, sc_prog, idx=0):
        canvas = self.render_cosmic_galaxy_bg(idx)
        if sc_prog > 0.74:
            fade_bg = min(1.0, (sc_prog - 0.74) / 0.26)
            canvas = Image.blend(canvas, self.party_bokeh_bg, fade_bg)

        halo_alpha = int(130 * math.sin(min(1.0, sc_prog * 1.25) * math.pi))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(170 + 70 * math.sin(sc_prog * math.pi))
            cx, cy = self.W // 2, self.H // 2 - 45
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(56, 189, 248, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(250, 204, 21, halo_alpha // 4))
            canvas.alpha_composite(halo)

        if self.d_icon_hd:
            if sc_prog < 0.45:
                u = sc_prog / 0.45
                c1 = 1.70158
                c3 = c1 + 1.0
                scale = 0.25 + 0.75 * (1.0 + c3 * ((u - 1.0) ** 3) + c1 * ((u - 1.0) ** 2))
                cx, cy = self.W // 2, self.H // 2 - 50
            elif sc_prog < 0.76:
                scale = 1.0 + 0.03 * math.sin((sc_prog - 0.45) * 10.0)
                cx, cy = self.W // 2, self.H // 2 - 50
            else:
                u = (sc_prog - 0.76) / 0.24
                ease = u * u * (3.0 - 2.0 * u)
                scale = (1.0 - ease) * 1.0 + ease * 0.165
                cx = int((1.0 - ease) * (self.W // 2) + ease * 59)
                cy = int((1.0 - ease) * (self.H // 2 - 50) + ease * 56)

            target_w = max(48, int(330 * scale))
            target_h = max(50, int(340 * scale))
            d_img = self.d_icon_hd.resize((target_w, target_h), Image.Resampling.LANCZOS)

            if 0.18 <= sc_prog <= 0.74:
                sweep_u = (sc_prog - 0.18) / 0.56
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
                sw_d.polygon(poly, fill=(250, 204, 21, 185))
                masked_sweep = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                masked_sweep.paste(sweep_layer, (0, 0), d_alpha)
                d_img = Image.alpha_composite(d_img, masked_sweep)

            canvas.alpha_composite(d_img, (cx - target_w // 2, cy - target_h // 2))

        if 0.22 < sc_prog < 0.84:
            txt_alpha = 1.0
            if sc_prog < 0.35:
                txt_alpha = (sc_prog - 0.22) / 0.13
            elif sc_prog > 0.72:
                txt_alpha = max(0.0, 1.0 - (sc_prog - 0.72) / 0.12)

            if self.logo_text and txt_alpha > 0.05:
                lw, lh = self.logo_text.size
                th = 54
                tw = int(lw * (th / float(lh)))
                lt_resized = self.logo_text.resize((tw, th), Image.Resampling.LANCZOS)
                r, g, b, a = lt_resized.split()
                a = a.point(lambda p: int(p * txt_alpha))
                lt_faded = Image.merge("RGBA", (r, g, b, a))
                canvas.alpha_composite(lt_faded, ((self.W - tw) // 2, self.H // 2 + 150))

            sub_col = (56, 189, 248, int(245 * txt_alpha))
            txt_overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            tod = ImageDraw.Draw(txt_overlay)
            tod.text(
                (self.W // 2, self.H // 2 + 232),
                "INVITACIONES QUE SE JUEGAN",
                font=self.f_intro_sub,
                fill=sub_col,
                anchor="mm",
            )
            canvas.alpha_composite(txt_overlay)

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def render_logo_outro_frame(self, outro_prog, idx=0):
        canvas = self.render_cosmic_galaxy_bg(idx)
        if outro_prog < 0.18:
            fade_in = outro_prog / 0.18
            canvas = Image.blend(self.party_bokeh_bg, canvas, fade_in)

        halo_alpha = int(145 * min(1.0, outro_prog * 2.2))
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
                sw_d.polygon(poly, fill=(250, 204, 21, 190))
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
                "INVITACIONES QUE SE JUEGAN",
                font=self.f_intro_sub,
                fill=(56, 189, 248, int(245 * txt_alpha)),
                anchor="mm",
            )
            pill_y0, pill_y1 = self.H - 126, self.H - 34
            tod.rounded_rectangle(
                (32, pill_y0, self.W - 32, pill_y1),
                radius=24,
                fill=(15, 19, 26, int(240 * txt_alpha)),
                outline=(250, 204, 21, int(215 * txt_alpha)),
                width=2,
            )
            tod.text(
                (self.W // 2, pill_y0 + 30),
                "VISITA HOY DREAMCRAFTERS.LAT",
                font=self.f_pill,
                fill=(250, 204, 21, int(255 * txt_alpha)),
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

    def render_fullscreen_invitation(self, scene_type, sc_prog):
        """Renderiza las capturas móviles reales a pantalla completa (720x1280)."""
        if scene_type == "gameplay" and self.gameplay_frames:
            f_idx = min(len(self.gameplay_frames) - 1, int(sc_prog * len(self.gameplay_frames)))
            return Image.open(self.gameplay_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "unlocked" and self.unlocked_frames:
            f_idx = min(len(self.unlocked_frames) - 1, int(sc_prog * len(self.unlocked_frames)))
            return Image.open(self.unlocked_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if scene_type == "website" and self.website_frames:
            f_idx = min(len(self.website_frames) - 1, int(sc_prog * len(self.website_frames)))
            return Image.open(self.website_frames[f_idx]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)

        if self.unlocked_frames:
            return Image.open(self.unlocked_frames[-1]).convert("RGBA").resize((self.W, self.H), Image.Resampling.LANCZOS)
        return Image.new("RGBA", (self.W, self.H), (11, 13, 18, 255))

    def _draw_floor_contact_shadow(self, canvas, cx, boot_y, rx, ry, alpha=145):
        shadow = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((cx - rx, boot_y - ry, cx + rx, boot_y + ry), fill=(4, 6, 12, alpha))
        sd.ellipse(
            (cx - int(rx * 0.65), boot_y - int(ry * 0.65), cx + int(rx * 0.65), boot_y + int(ry * 0.65)),
            fill=(2, 4, 8, int(alpha * 0.75)),
        )
        canvas.alpha_composite(shadow)

    def render_frame(self, idx, total_frames, fps, scene_info):
        sc = scene_info["scene"]
        sc_prog = scene_info["progress"]
        sc_type = sc["type"]

        if sc_type == "logo_intro":
            return self.render_logo_intro_frame(sc_prog, idx=idx)

        # En el final (escena CTA), justo cuando Mario dice el ending ("DreamCrafters, artificialmente hechos a mano"),
        # se sigue escuchando su voz pero en pantalla aparece el cierre animado con el ícono D.
        if sc_type == "cta":
            sc_dur = max(0.1, sc["end"] - sc["start"])
            t_in_sc = sc_prog * sc_dur
            ending_logo_start_sec = 4.55
            if t_in_sc >= ending_logo_start_sec:
                outro_prog = min(1.0, (t_in_sc - ending_logo_start_sec) / max(0.1, sc_dur - ending_logo_start_sec))
                return self.render_logo_outro_frame(outro_prog, idx=idx)

        # ESCENAS GAMEPLAY / UNLOCKED / WEBSITE -> PANTALLA COMPLETA (720x1280)
        if sc_type in ("gameplay", "unlocked", "website"):
            canvas = self.render_fullscreen_invitation(sc_type, sc_prog)
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Mario 3D (FeatherTalk ONNX) de Cuerpo Completo centrado en pantalla
        accent = sc["accent_rgb"]
        canvas = self.party_bokeh_bg.copy()

        mario_rgba, _ = self.ft.synthesize_mario_rgba(idx)
        self._draw_floor_contact_shadow(canvas, self.W // 2, 1132, rx=165, ry=22, alpha=155)
        canvas.alpha_composite(mario_rgba, (0, 0))

        grad = Image.new("RGBA", (self.W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(210 * ((gy / 240.0) ** 1.5))
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
            outline=accent + (210,),
            width=2,
        )
        cd.text((self.W // 2, pill_y0 + 30), sc["bottom_pill"], font=self.f_pill, fill=accent, anchor="mm")
        cd.text((self.W // 2, pill_y0 + 64), ">> DREAMCRAFTERS.LAT <<", font=self.f_url, fill=(250, 246, 238), anchor="mm")

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.path.join(REPO_ROOT, "out", "video_final_dreamcrafters.mp4"))
    args = parser.parse_args()

    if not os.path.exists(os.path.join(REAL_CAP_DIR, "d_icon_hd.png")):
        from capture_real_mario_mobile import capture_all
        capture_all()

    ffmpeg_path = resolve_ffmpeg_path()
    bgm_rel = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "mario_cloned_voice.wav")

    print("Ensamblando narracion clonada de Mario (Hugging Face Chatterbox-Multilingual-TTS)...")
    scenes = synthesize_cloned_scenes_local(SCENES_CLEAN, REF_WAV, clean_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    print("Inicializando motor FeatherTalk ONNX 144x144 para Mario 3D...")
    ft_engine = FeatherTalkMarioEngine(FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)

    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} frames ({total_frames/fps:.1f}s) con FeatherTalk + Invitaciones a Pantalla Completa...")

    renderer = CleanDreamCraftersRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_visual_dc.mp4")
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

    mixed_wav = os.path.join(out_dir, "mario_cloned_mixed.wav")
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
            "19",
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
    print(f"Video listo: {args.output} (y actualizado en {published_copy})")


if __name__ == "__main__":
    main()
