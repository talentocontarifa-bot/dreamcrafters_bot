# -*- coding: utf-8 -*-
"""
render_santa_demo.py — Demo Navideño Santa Claus 3D (FeatherTalk ONNX + ElevenLabs v4)
"""
import os
import sys
import json
import wave
import math
import shutil
import hashlib
import subprocess
import urllib.request
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
CHAR_04_DIR = os.path.join(REPO_ROOT, "characters", "04_santa")
CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
FEATHERTALK_ONNX_DIR = os.path.join(CHAR_04_DIR, "feathertalk_onnx")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
CHRISTMAS_BG_PATH = os.path.join(CHAR_04_DIR, "christmas_bg.jpg")

ELEVENLABS_KEYS = [
    os.environ.get("ELEVENLABS_API_KEY", ""),
    "sk_23049c20908c037dcaacd577ec4524ad4ef9674756d8f67c",
    "sk_7a19a6c786e6ce5b518337ad562c31bb673e61403c048c3b",
    "sk_9518cdd9e61bdf93f3e9d2ad8f129c455c108cf487881505",
]
# Brian - Deep, Resonant and Comforting
ELEVENLABS_VOICE_ID = os.environ.get("SANTA_VOICE_ID", "nPczCjzI2devNBz1zQrb")
ELEVENLABS_MODEL_ID = "eleven_v4"

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4
GEOMETRY_BASE_SIZE = 160
MASK_RECT = (5, 5, 150, 145)

SANTA_PROMO_TEXT = (
    "¡Jo, jo, jo! ¡Feliz Navidad, amigos! Este año en Drim Crafters estamos preparando algo mágico "
    "para tus posadas, fiestas navideñas y regalos especiales. ¡Invitaciones y experiencias interactivas "
    "hechas para sorprender a todos desde su celular! Muy pronto en drim crafters punto lat."
)


def resolve_ffmpeg_path():
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


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
                if rem > 350:
                    print(f"[ElevenLabs] Usando key {k[:12]}... (saldo disponible: {rem} chars)")
                    return k
        except Exception:
            pass
    raise RuntimeError("No se encontró ninguna key de ElevenLabs con saldo suficiente.")


def synthesize_santa_voice(text, output_wav_path, ffmpeg_path="ffmpeg"):
    cache_dir = os.path.join(CHAR_04_DIR, "out", "elevenlabs_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)
    sr = 24000
    h_key = hashlib.sha256(f"santa_v4|{ELEVENLABS_VOICE_ID}|{text}".encode("utf-8")).hexdigest()[:16]
    cached_wav = os.path.join(cache_dir, f"santa_{h_key}.wav")

    if not os.path.exists(cached_wav):
        api_key = _pick_working_elevenlabs_key()
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128"
        payload = json.dumps(
            {
                "text": text,
                "model_id": ELEVENLABS_MODEL_ID,
                "voice_settings": {
                    "stability": 0.40,
                    "similarity_boost": 0.85,
                    "style": 0.55,
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
        raw_mp3 = os.path.join(cache_dir, "_tmp_santa.mp3")
        with urllib.request.urlopen(req, timeout=35) as resp:
            with open(raw_mp3, "wb") as f_mp3:
                f_mp3.write(resp.read())

        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                raw_mp3,
                "-af",
                "highpass=f=65,equalizer=f=180:width_type=o:width=1.2:g=2.2,equalizer=f=3600:width_type=o:width=1.4:g=3.5,loudnorm=I=-12.5:TP=-0.8:LRA=8",
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

    shutil.copyfile(cached_wav, output_wav_path)
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
        # Use exact bbox of frame 72 (the ref_0 frame)
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
        hu_out = self.hubert_sess.run(None, {in_name: wav_padded[None, :]})[0][0]
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


def main():
    # Ensure exact unsmoothed bboxes so inner replacement has zero pixel shift
    ft_root = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\FeatherTalk"
    sys.path.insert(0, ft_root)
    from face_utils import read_landmarks, compute_face_bbox
    lms_dir = os.path.join(ft_root, "santa_dataset", "landmarks")
    exact_bboxes = np.array(
        [compute_face_bbox(read_landmarks(os.path.join(lms_dir, f"{i}.lms"))) for i in range(250)],
        dtype=np.int32,
    )
    np.save(os.path.join(FEATHERTALK_ONNX_DIR, "bboxes_240.npy"), exact_bboxes)

    ffmpeg_path = resolve_ffmpeg_path()
    out_dir = os.path.join(REPO_ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    voice_wav = os.path.join(out_dir, "santa_promo_voice.wav")
    synthesize_santa_voice(SANTA_PROMO_TEXT, voice_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    engine = FeatherTalkSantaEngine(FEATHERTALK_ONNX_DIR, voice_wav, fps=fps, ffmpeg_path=ffmpeg_path)
    W, H = 720, 1280
    bg = Image.open(CHRISTMAS_BG_PATH).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)

    d_icon_path = os.path.join(CHAR_02_DIR, "out", "real_mobile_capture", "d_icon_hd.png")
    d_icon_header = Image.open(d_icon_path).convert("RGBA").resize((54, 56), Image.Resampling.LANCZOS) if os.path.exists(d_icon_path) else None

    raw_logo_path = os.path.join(LANDING_DIR, "logo-text.png")
    logo_text = None
    if os.path.exists(raw_logo_path):
        raw_logo = Image.open(raw_logo_path).convert("RGBA")
        _, _, _, a_c = raw_logo.split()
        white_rgb = Image.new("RGB", raw_logo.size, (250, 246, 238))
        logo_text = Image.merge("RGBA", (*white_rgb.split(), a_c))

    f_pill = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 20)
    f_url = ImageFont.truetype(os.path.join(CHAR_02_DIR, "assets", "ShareTechMono-Regular.ttf"), 18)

    temp_v = os.path.join(out_dir, "temp_santa_visual.mp4")
    vw = cv2.VideoWriter(temp_v, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    for i in range(engine.total_frames):
        canvas = bg.copy()
        santa_rgba, _ = engine.synthesize_santa_rgba(i)

        # Soft blurred contact shadow on the snow under Santa's boots
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((W // 2 - 220, 1138 - 28, W // 2 + 220, 1138 + 28), fill=(14, 22, 42, 135))
        from PIL import ImageFilter
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
        canvas.alpha_composite(shadow)

        canvas.alpha_composite(santa_rgba, (0, 0))

        # Bottom gradient + festive pill
        grad = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(215 * ((gy / 240.0) ** 1.5))
            gd.line([(0, gy), (W, gy)], fill=(12, 10, 18, alpha_g))
        canvas.alpha_composite(grad, (0, H - 240))

        if d_icon_header:
            canvas.alpha_composite(d_icon_header, (32, 28))
        if logo_text:
            lw, lh = logo_text.size
            th = 34
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(logo_text.resize((tw, th), Image.Resampling.LANCZOS), (98, 40))

        cd = ImageDraw.Draw(canvas)
        pill_y0, pill_y1 = H - 126, H - 34
        accent = (250, 204, 21)
        cd.rounded_rectangle(
            (32, pill_y0, W - 32, pill_y1),
            radius=24,
            fill=(24, 14, 18, 240),
            outline=accent + (225,),
            width=2,
        )
        cd.text((W // 2, pill_y0 + 30), "¡ESPECIAL DE NAVIDAD EN CAMINO!", font=f_pill, fill=accent, anchor="mm")
        cd.text((W // 2, pill_y0 + 64), ">> DREAMCRAFTERS.LAT <<", font=f_url, fill=(250, 246, 238), anchor="mm")

        rgb = np.array(canvas.convert("RGB"))
        vw.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    vw.release()

    final_mp4 = os.path.join(out_dir, "demo_santa_navidad_dreamcrafters.mp4")
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            temp_v,
            "-i",
            voice_wav,
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
            final_mp4,
        ],
        check=True,
    )
    if os.path.exists(temp_v):
        os.remove(temp_v)
    print("Demo Santa listo en:", final_mp4)


if __name__ == "__main__":
    main()
