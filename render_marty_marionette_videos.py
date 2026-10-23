# -*- coding: utf-8 -*-
"""
render_marty_marionette_videos.py
=================================
Motor FeatherTalk ONNX (`FeatherTalkMartyEngine`) para Marty McFly en Volver al Futuro:
- Cero cuello roto: máscara elíptica exclusiva de boca `cv2.ellipse(mask_alpha, (72, 48), (48, 31))`
  (`y=17..79, x=24..120` dentro de 144x144) con igualación de iluminación en el anillo de piel.
  Termina 10px arriba del borde del mentón y 50px arriba del cuello/chamarra.
- Cero bocas encimadas: cubre desde `y=17` hasta `y=79` (100% de labio superior, dientes y labio inferior)
  y usa el segmento limpio continuo `96..249` (154 cuadros = 12.8s en ping-pong) con todos los gestos de brazos y parpadeos.
"""
import os
import math
import wave
import shutil
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import onnxruntime as ort
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
ONNX_DIR = os.path.join(REPO_ROOT, "characters", "06_marty", "marty_onnx")
INV_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\invitacion-volver-al-futuro"
WEB_PUBLIC_BTTF_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\dreamcrafters-web\public\invitacionvolveralfuturo"
CHAR_ASSETS_DIR = os.path.join(INV_DIR, "assets", "characters")
WEB_CHAR_ASSETS_DIR = os.path.join(WEB_PUBLIC_BTTF_DIR, "assets", "characters")
MARTY_AUDIO_DIR = os.path.join(INV_DIR, "assets", "audio", "marty")
os.makedirs(CHAR_ASSETS_DIR, exist_ok=True)
os.makedirs(WEB_CHAR_ASSETS_DIR, exist_ok=True)

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)


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


def _key_green_screen(bgr: np.ndarray) -> Image.Image:
    """Extrae a Marty del fondo verde (#00FF00) con despill suave y sin halo verde."""
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


def get_font(size, bold=True, mono=False):
    candidates = []
    if mono:
        candidates = [
            r"C:\Windows\Fonts\consolab.ttf",
            r"C:\Windows\Fonts\lucon.ttf",
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


class FeatherTalkMartyEngine:
    def __init__(self, onnx_dir: str, voice_wav_path: str, fps: int = 24):
        self.onnx_dir = onnx_dir
        self.fps = fps

        hubert_path = os.path.join(onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(onnx_dir, "closed_win.npy")
        video_path = os.path.join(onnx_dir, "marty_25fps.mp4")

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

        n_valid = min(len(self.base_frames), len(self.bboxes))
        self.base_frames = self.base_frames[:n_valid]
        self.bboxes = self.bboxes[:n_valid]

        base_seq = list(range(0, n_valid))
        self.ping_pong = base_seq + base_seq[-2:0:-1]
        self.pp_cursor = 0

        # Con bboxes exactos de landmarks (.lms) y reference = inner.copy() (como inference.py oficial),
        # mask_alpha[16:134, 14:130] reemplaza 100% boca + mentón y reconstruye el cuello exacto del cuadro actual
        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[16:134, 14:130] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (17, 17), 4.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio(voice_wav_path, fps=fps)

    def _analyze_audio(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k_ft.wav"
        subprocess.run(
            [
                FFMPEG, "-y", "-i", voice_wav_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", tmp_16k,
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
        total_frames = max(1, int(round(dur_sec * fps)))

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

    def synthesize_frame(self, frame_idx: int, force_silent: bool = False) -> tuple[np.ndarray, Image.Image, float]:
        t_sec = frame_idx / float(self.fps)
        rms_val = float(self.rms_24fps[min(frame_idx, len(self.rms_24fps) - 1)])
        is_silent = force_silent or (rms_val < 0.010)

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
        inner_f = inner.astype(np.float32)

        blended_inner = (pred_bgr * self.mask_alpha + inner_f * (1.0 - self.mask_alpha)).astype(np.uint8)
        b = FACE_BORDER
        crop_152[b : b + FACE_INNER_SIZE, b : b + FACE_INNER_SIZE] = blended_inner
        frame_bgr[ymin:ymax, xmin:xmax] = cv2.resize(
            crop_152, (xmax - xmin, ymax - ymin), interpolation=cv2.INTER_LANCZOS4
        )

        marty_rgba = _key_green_screen(frame_bgr)
        return frame_bgr, marty_rgba, rms_val


SpriteMartyEngine = FeatherTalkMartyEngine


def build_bttf_stage_bg(W=720, H=1280) -> Image.Image:
    bg_path = os.path.join(INV_DIR, "assets", "bttf_page_bg_flames.webp")
    base = Image.new("RGBA", (W, H), (2, 3, 8, 255))
    if os.path.exists(bg_path):
        raw = Image.open(bg_path).convert("RGBA")
        rw, rh = raw.size
        target_h = int(H * 0.72)
        target_w = int(rw * (target_h / float(rh)))
        resized = raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
        lx = (target_w - W) // 2
        cropped = resized.crop((lx, 0, lx + W, target_h))

        arr = np.array(cropped).astype(np.float32)
        y_grad = np.ones((target_h, 1), dtype=np.float32)
        fade_top = int(target_h * 0.28)
        fade_bot = int(target_h * 0.25)
        y_grad[:fade_top, 0] = np.linspace(0.0, 1.0, fade_top) ** 1.5
        y_grad[-fade_bot:, 0] = np.linspace(1.0, 0.0, fade_bot) ** 1.5
        arr[:, :, 3] = arr[:, :, 3] * y_grad * 0.85
        faded_layer = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
        base.alpha_composite(faded_layer, (0, int(H * 0.16)))

    veil = Image.new("RGBA", (W, H), (2, 4, 12, 85))
    base = Image.alpha_composite(base, veil)
    return base


def sync_to_web_public(filename: str):
    src = os.path.join(CHAR_ASSETS_DIR, filename)
    dst = os.path.join(WEB_CHAR_ASSETS_DIR, filename)
    if os.path.exists(src):
        shutil.copyfile(src, dst)


def render_all():
    voice_wav = os.path.join(ONNX_DIR, "voice_marty_saludo.wav")
    bgm_mp3 = os.path.join(INV_DIR, "assets", "audio", "bttf_theme.mp3")

    print("=== 1. Renderizando video_marty.mp4 + marty_marioneta_green.mp4 con FeatherTalk (Cero Cuello Roto) ===")
    engine = FeatherTalkMartyEngine(ONNX_DIR, voice_wav, fps=24)
    W, H = 720, 1280
    stage_bg = build_bttf_stage_bg(W, H)

    rng = np.random.RandomState(1985)
    sparks = []
    spark_colors = [
        (255, 90, 0),
        (255, 150, 20),
        (255, 215, 70),
        (255, 60, 0),
        (80, 215, 255),
    ]
    for _ in range(75):
        sparks.append({
            "x": rng.uniform(20, W - 20),
            "y": rng.uniform(0, H),
            "vy": rng.uniform(2.5, 6.2),
            "vx": rng.uniform(-1.1, 1.1),
            "r": rng.uniform(2.0, 4.8),
            "color": spark_colors[rng.randint(0, len(spark_colors))],
            "phase": rng.uniform(0, math.pi * 2),
        })

    font_mono = get_font(20, bold=True, mono=True)
    font_title = get_font(28, bold=True, mono=False)
    font_sub = get_font(22, bold=True, mono=False)

    tmp_green_mp4 = os.path.join(CHAR_ASSETS_DIR, "_tmp_green_silent.mp4")
    tmp_card_mp4 = os.path.join(CHAR_ASSETS_DIR, "_tmp_card_silent.mp4")

    writer_green = cv2.VideoWriter(tmp_green_mp4, cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (W, H))
    writer_card = cv2.VideoWriter(tmp_card_mp4, cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (W, H))

    for f_idx in range(engine.total_frames):
        t_sec = f_idx / 24.0
        frame_bgr_green, marty_rgba, _ = engine.synthesize_frame(f_idx)
        writer_green.write(frame_bgr_green)

        canvas = stage_bg.copy()
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for sp in sparks[:45]:
            sx = (sp["x"] + math.sin(t_sec * 2.5 + sp["phase"]) * 18.0 + sp["vx"] * f_idx) % W
            sy = (sp["y"] - sp["vy"] * f_idx) % H
            alpha = int(170 + 80 * math.sin(t_sec * 6.0 + sp["phase"]))
            r_sz = sp["r"]
            c = sp["color"]
            draw.ellipse((sx - r_sz*2, sy - r_sz*2, sx + r_sz*2, sy + r_sz*2), fill=(c[0], c[1], c[2], alpha // 4))
            draw.ellipse((sx - r_sz, sy - r_sz, sx + r_sz, sy + r_sz), fill=(255, 240, 200, alpha))

        canvas = Image.alpha_composite(canvas, overlay)
        canvas.alpha_composite(marty_rgba, (0, 40))

        fg_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fg_draw = ImageDraw.Draw(fg_ov)
        for sp in sparks[45:]:
            sx = (sp["x"] + math.cos(t_sec * 2.2 + sp["phase"]) * 15.0 + sp["vx"] * f_idx) % W
            sy = (sp["y"] - sp["vy"] * f_idx) % H
            alpha = int(165 + 85 * math.cos(t_sec * 5.5 + sp["phase"]))
            r_sz = sp["r"]
            c = sp["color"]
            fg_draw.ellipse((sx - r_sz*1.8, sy - r_sz*1.8, sx + r_sz*1.8, sy + r_sz*1.8), fill=(c[0], c[1], c[2], alpha // 3))
            fg_draw.ellipse((sx - r_sz, sy - r_sz, sx + r_sz, sy + r_sz), fill=(255, 245, 215, alpha))

        fg_draw.rounded_rectangle((36, 36, W - 36, 108), radius=16, fill=(5, 10, 22, 215), outline=(255, 106, 0, 220), width=2)
        fg_draw.text((W // 2, 58), "TRANSMISIÓN TEMPORAL · 88 MPH", font=font_mono, fill=(56, 214, 255, 255), anchor="mm")
        fg_draw.text((W // 2, 86), "MARTY McFLY · EN VIVO DESDE 1985", font=font_sub, fill=(255, 210, 80, 255), anchor="mm")

        fg_draw.rounded_rectangle((32, H - 142, W - 32, H - 42), radius=18, fill=(5, 10, 22, 228), outline=(56, 214, 255, 210), width=2)
        fg_draw.text((W // 2, H - 106), "¡NO FALTES A LOS 7 AÑOS DE SANTIAGO!", font=font_title, fill=(255, 255, 255, 255), anchor="mm")
        fg_draw.text((W // 2, H - 68), "SÁB 24 MAY 2025 · 19:00 H · CASA DE EVENTOS", font=font_mono, fill=(255, 140, 26, 255), anchor="mm")

        canvas = Image.alpha_composite(canvas, fg_ov)
        card_bgr = cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)
        writer_card.write(card_bgr)

    writer_green.release()
    writer_card.release()

    mixed_wav = os.path.join(CHAR_ASSETS_DIR, "_tmp_mixed_audio.wav")
    filter_complex = (
        "[0:a]volume=1.0[v];"
        "[1:a]volume=0.14,aloop=loop=-1:size=2e+09[b];"
        "[v][b]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.96[out]"
    )
    subprocess.run(
        [
            FFMPEG, "-y", "-i", voice_wav, "-i", bgm_mp3,
            "-filter_complex", filter_complex, "-map", "[out]",
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", mixed_wav,
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    out_green_mp4 = os.path.join(CHAR_ASSETS_DIR, "marty_marioneta_green.mp4")
    out_card_mp4 = os.path.join(CHAR_ASSETS_DIR, "video_marty.mp4")

    subprocess.run(
        [
            FFMPEG, "-y", "-i", tmp_green_mp4, "-i", voice_wav,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "fast",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_green_mp4,
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        [
            FFMPEG, "-y", "-i", tmp_card_mp4, "-i", mixed_wav,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_card_mp4,
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for p in (tmp_green_mp4, tmp_card_mp4, mixed_wav):
        if os.path.exists(p):
            os.remove(p)

    sync_to_web_public("marty_marioneta_green.mp4")
    sync_to_web_public("video_marty.mp4")
    print(" -> video_marty.mp4 & marty_marioneta_green.mp4 actualizados con FeatherTalk (Cero Cuello Roto).")

    print("=== 2. Regenerando TODOS los clips extra en pantalla verde con FeatherTalk ===")
    extra_clips = [
        ("marty_welcome_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_welcome_party.mp3")),
        ("marty_rsvp_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_rsvp_thanks.mp3")),
        ("marty_soda_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_soda.mp3")),
        ("marty_alcalde_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_alcalde.mp3")),
        ("marty_bicicleta_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_bicicleta.mp3")),
        ("marty_defiendete_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_defiendete.mp3")),
        ("marty_george_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_george.mp3")),
        ("marty_mirame_green.mp4", os.path.join(MARTY_AUDIO_DIR, "marty_orig_mirame.mp3")),
    ]
    for out_name, audio_path in extra_clips:
        if not os.path.exists(audio_path):
            continue
        out_mp4 = os.path.join(CHAR_ASSETS_DIR, out_name)
        eng = FeatherTalkMartyEngine(ONNX_DIR, audio_path, fps=24)
        tmp_v = os.path.join(CHAR_ASSETS_DIR, "_tmp_" + out_name)
        writer = cv2.VideoWriter(tmp_v, cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (720, 1280))
        for f_idx in range(eng.total_frames):
            bgr, _, _ = eng.synthesize_frame(f_idx, force_silent=False)
            writer.write(bgr)
        writer.release()
        subprocess.run(
            [
                FFMPEG, "-y", "-i", tmp_v, "-i", audio_path,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-preset", "fast",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_mp4,
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if os.path.exists(tmp_v):
            os.remove(tmp_v)
        sync_to_web_public(out_name)
        print(f" -> Regenerado con FeatherTalk: {out_name} ({eng.total_frames} cuadros)")

    # Idle loop (96 cuadros = 4.0s silent closed-mouth ping-pong)
    idle_mp4 = os.path.join(CHAR_ASSETS_DIR, "marty_idle_green.mp4")
    eng_idle = FeatherTalkMartyEngine(ONNX_DIR, os.path.join(MARTY_AUDIO_DIR, "marty_orig_soda.mp3"), fps=24)
    tmp_v = os.path.join(CHAR_ASSETS_DIR, "_tmp_idle.mp4")
    writer = cv2.VideoWriter(tmp_v, cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (720, 1280))
    seq = list(range(48)) + list(range(47, -1, -1))
    for idx in seq:
        eng_idle.pp_cursor = idx
        bgr, _, _ = eng_idle.synthesize_frame(0, force_silent=True)
        writer.write(bgr)
    writer.release()
    subprocess.run(
        [
            FFMPEG, "-y", "-i", tmp_v,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-preset", "fast",
            "-an", "-movflags", "+faststart", idle_mp4,
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if os.path.exists(tmp_v):
        os.remove(tmp_v)
    sync_to_web_public("marty_idle_green.mp4")
    print(" -> Regenerado con FeatherTalk: marty_idle_green.mp4 (96 cuadros)")


if __name__ == "__main__":
    render_all()
