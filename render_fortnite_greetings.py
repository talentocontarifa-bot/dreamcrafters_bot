# -*- coding: utf-8 -*-
"""
render_fortnite_greetings.py — Motor Híbrido HD (720x1280) para los 4 personajes de Fortnite:
- Jonesy y Brite Bomber: Lip-Sync Neuronal FeatherTalk ONNX (144x144).
- Peely (Plátano) y Beef Boss (Hamburguesa): Motor de Sprites Reactivos por Fonema/RMS
  + Efectos de Glitch Táctico RGB y Líneas CCTV desfilando en vertical para disimular cambios de sprite.
- Incluye Tarjeta Táctica integrada con Festejado, Fecha/Hora y Lugar (Zona de Drop) + BGM Epic Cyber Hero.
"""
import os
import sys
import time
import wave
import math
import shutil
import subprocess
import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FT_ROOT = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\FeatherTalk"
FT_DATA_DIR = os.path.join(FT_ROOT, "data_utils")
sys.path.insert(0, FT_ROOT)
sys.path.insert(0, FT_DATA_DIR)

from face_utils import (
    FACE_CROP_SIZE,
    FACE_INNER_SIZE,
    FACE_BORDER,
    GEOMETRY_BASE_SIZE,
    MASK_RECT,
    compute_face_bbox,
)
from model import (
    IMAGE_SIZE,
    AUDIO_TOKENS,
    AUDIO_FEATURE_DIM,
    create_model,
    load_checkpoint_state,
    visual_export_model,
)

REC_DIR = r"C:\Users\rufin\OneDrive\Documentos\DreamCrafters\Invitaciones\01-Fortnite\00-recursos"
INV_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\invitacion-fortnite"
ASSETS_DIR = os.path.join(INV_DIR, "assets")
CHARS_ASSET_DIR = os.path.join(ASSETS_DIR, "characters")
ICONS_ASSET_DIR = os.path.join(ASSETS_DIR, "icons")
DC_CHAR_05_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\dreamcrafter\characters\05_fortnite"
SANTA_HUBERT_ONNX = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\FeatherTalk\santa_onnx\feather_hubert.onnx"
SANTA_INIT_CKPT = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\FeatherTalk\santa_checkpoints\last.pth"
ARTIFACT_DIR = r"C:\Users\rufin\.gemini\antigravity\brain\10e4db52-4bc5-4325-8917-6fe3620cc025"


CHARACTER_CONFIGS = {
    "jonesy": {
        "mode": "feathertalk",
        "green_mp4": os.path.join(REC_DIR, "11-video-jonesy-green.mp4"),
        "voice_mp3": os.path.join(CHARS_ASSET_DIR, "voice_jonesy.mp3"),
        "out_mp4": os.path.join(CHARS_ASSET_DIR, "video_jonesy.mp4"),
        "rec_final_mp4": os.path.join(REC_DIR, "15-video-jonesy-final.mp4"),
        "dx": 0,
        "dy": 0,
        "size_override": None,
        "badge_title": "CAPITÁN JONESY · LÍDER DE ESCUADRÓN",
        "cam_id": "CAM-01 // JONESY-COMM",
        "accent_rgb": (255, 230, 0),
        "char_y_offset": -45,
        "cctv_intensity": 0.48,
    },
    "bomber": {
        "mode": "feathertalk",
        "green_mp4": os.path.join(REC_DIR, "12-video-bomber-green.mp4"),
        "voice_mp3": os.path.join(CHARS_ASSET_DIR, "voice_bomber.mp3"),
        "out_mp4": os.path.join(CHARS_ASSET_DIR, "video_bomber.mp4"),
        "rec_final_mp4": os.path.join(REC_DIR, "16-video-bomber-final.mp4"),
        "dx": 0,
        "dy": 0,
        "size_override": None,
        "badge_title": "BRITE BOMBER · GUARDIANA DE LA LLAMA",
        "cam_id": "CAM-02 // BOMBER-COMM",
        "accent_rgb": (217, 70, 239),
        "char_y_offset": -45,
        "cctv_intensity": 0.48,
    },
    "peely": {
        "mode": "sprites",
        "green_mp4": os.path.join(REC_DIR, "13-video-peely-green.mp4"),
        "voice_mp3": os.path.join(CHARS_ASSET_DIR, "voice_peely.mp3"),
        "out_mp4": os.path.join(CHARS_ASSET_DIR, "video_peely.mp4"),
        "rec_final_mp4": os.path.join(REC_DIR, "17-video-peely-final.mp4"),
        "dx": 0,
        "dy": 58,
        "size_override": 150,
        "badge_title": "AGENTE PEELY · POTASIO TÁCTICO",
        "cam_id": "CCTV-03 // BANANA-SAT",
        "accent_rgb": (255, 230, 0),
        "char_y_offset": -35,
        "cctv_intensity": 1.0,
    },
    "burger": {
        "mode": "sprites",
        "green_mp4": os.path.join(REC_DIR, "14-video-burger-green.mp4"),
        "voice_mp3": os.path.join(CHARS_ASSET_DIR, "voice_burger.mp3"),
        "out_mp4": os.path.join(CHARS_ASSET_DIR, "video_burger.mp4"),
        "rec_final_mp4": os.path.join(REC_DIR, "18-video-burger-final.mp4"),
        "dx": -42,
        "dy": -8,
        "size_override": 220,
        "badge_title": "BEEF BOSS · COMANDANTE DURRR BURGER",
        "cam_id": "CCTV-04 // DURRR-SAT",
        "accent_rgb": (0, 229, 255),
        "char_y_offset": -45,
        "cctv_intensity": 1.0,
    },
}


def _crop_face(image: np.ndarray, bbox: tuple[int, int, int, int], crop_size: int = FACE_CROP_SIZE) -> np.ndarray:
    xmin, ymin, xmax, ymax = bbox
    h, w = image.shape[:2]
    xmin = max(0, min(w - 2, xmin))
    ymin = max(0, min(h - 2, ymin))
    xmax = max(xmin + 2, min(w, xmax))
    ymax = max(ymin + 2, min(h, ymax))
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


def extract_hubert_features(hubert_sess, wav_path_16k: str):
    with wave.open(wav_path_16k, "rb") as wf:
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    wav_f = pcm.astype(np.float32) / 32768.0
    sr = 16000
    pad_16k = np.zeros(int(0.5 * sr), dtype=np.float32)
    wav_norm = (wav_f - wav_f.mean()) / np.sqrt(wav_f.var() + 1e-7)
    wav_padded = np.concatenate([pad_16k, wav_norm, pad_16k]).astype(np.float32)

    in_name = hubert_sess.get_inputs()[0].name
    hu_out = hubert_sess.run(None, {in_name: wav_padded[None, :]})[0][0]
    if hu_out.shape[0] % 2 != 0:
        hu_out = hu_out[:-1]
    feats_25 = hu_out.reshape(-1, 2, 1024).astype(np.float32)
    return feats_25, wav_f


class SpriteFortniteEngine:
    """
    Motor de Lip-Sync basado en Sprites + Articulación de Boca/Lengua para personajes no-humanos
    (Peely el Plátano y Beef Boss la Hamburguesa):
    - Clasifica los 250 cuadros del video original en bancos de Sprites por apertura bucal y fonema:
      * Peely:
        - Tier 0 (CLOSED): boca cerrada sonriendo (cuando la voz está en silencio).
        - Tier 1 (TEETH): dientes blancos (consonantes sibilantes/dentales).
        - Tier 2 (ROUND_O): boca en 'O' (vocales suaves O/U).
        - Tier 3 (MID_OPEN): boca semiabierta (vocales medias).
        - Tier 4 (WIDE_OPEN): boca abierta al máximo mostrando lengua (vocales fuertes A/E).
        Además, alinea y funde el sprite de boca sobre el cuerpo activo y dispara un pulso de Glitch
        cada vez que salta de segmento de sprite para disimular cualquier corte.
      * Beef Boss (Hamburguesa):
        - Selecciona entre sus sprites de postura (idle, cabeceo hablando, levantando micrófono azul brillante)
          y articula elásticamente su pan superior + ojos hacia arriba y su lengua gigante + carne hacia abajo
          al ritmo exacto de las sílabas del audio, disparando Glitch en los cambios de pose.
    """

    def __init__(self, skin_key: str, onnx_dir: str, voice_wav_path: str, fps: int = 24):
        self.skin_key = skin_key
        self.onnx_dir = onnx_dir
        self.fps = fps

        video_path = os.path.join(onnx_dir, f"{skin_key}_25fps.mp4")
        self.base_frames = []
        cap = cv2.VideoCapture(video_path)
        while True:
            ret, frm = cap.read()
            if not ret:
                break
            self.base_frames.append(frm)
        cap.release()

        self.rms_arr, self.zcr_arr, self.total_frames = self._analyze_voice_envelope(voice_wav_path, fps=fps)

        if skin_key == "peely":
            self._init_peely_sprites()
        else:
            self._init_burger_sprites()

        self._build_timeline()

    def _analyze_voice_envelope(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".sprite16k.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
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
        zcr_arr = np.zeros(total_frames, dtype=np.float32)
        win_samples = int(0.055 * sr)
        for i in range(total_frames):
            c_idx = int((i / float(fps)) * sr)
            s_i = max(0, c_idx - win_samples // 2)
            e_i = min(len(wav_f), c_idx + win_samples // 2)
            seg = wav_f[s_i:e_i]
            if len(seg) > 4:
                rms_arr[i] = float(np.sqrt(np.mean(seg ** 2)))
                zcr_arr[i] = float(np.mean(np.abs(np.diff(np.sign(seg)))) * 0.5)

        # Normalize RMS to [0..1] based on 95th percentile
        p95 = max(float(np.percentile(rms_arr, 95)), 0.04)
        rms_norm = np.clip(rms_arr / p95, 0.0, 1.25)
        return rms_norm, zcr_arr, total_frames

    def _init_peely_sprites(self):
        # Classify all 250 Peely frames into 5 crisp mouth sprite banks
        self.tiers = {0: [], 1: [], 2: [], 3: [], 4: []}
        for idx, frm in enumerate(self.base_frames):
            m = frm[420:480, 295:390]
            b = m[:, :, 0].astype(np.float32)
            g = m[:, :, 1].astype(np.float32)
            r = m[:, :, 2].astype(np.float32)
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            dark_red = int(((luma < 115) & ((r - g) > -10)).sum())
            white_teeth = int(((luma > 185) & (b > 155) & ((g - b) < 35)).sum())

            if white_teeth >= 180:
                self.tiers[1].append(idx)  # TEETH / SIBILANT
            elif dark_red < 235:
                self.tiers[0].append(idx)  # CLOSED SMILE
            elif dark_red < 620:
                self.tiers[2].append(idx)  # ROUND "O" / SMALL OPEN
            elif dark_red < 1250:
                self.tiers[3].append(idx)  # MID OPEN
            else:
                self.tiers[4].append(idx)  # WIDE OPEN + TONGUE

        # Canonical ultra-clean mouth sprite frames for direct mouth-patch compositing too
        self.canonical_mouth_idx = {
            0: 100,  # Closed smile
            1: 190,  # White teeth smile
            2: 50,   # Round "O" mouth
            3: 80,   # Half-open mouth
            4: 40,   # Wide-open mouth with red tongue
        }
        # Precompute eye center (x, y) for each frame using template matching of Peely's eyes
        eye_tpl = self.base_frames[100][335:415, 260:435]
        self.eye_offsets = []
        for frm in self.base_frames:
            roi = frm[315:435, 240:455]
            res = cv2.matchTemplate(roi, eye_tpl, cv2.TM_CCOEFF_NORMED)
            _, _, _, max_loc = cv2.minMaxLoc(res)
            dx = (240 + max_loc[0]) - 260
            dy = (315 + max_loc[1]) - 335
            self.eye_offsets.append((dx, dy))

        # Soft mouth blend mask for Peely's mouth region (y=414..486, x=282..402 -> 72x120)
        mh, mw = 74, 118
        m_alpha = np.zeros((mh, mw), dtype=np.float32)
        cv2.ellipse(m_alpha, (mw // 2, mh // 2), (mw // 2 - 8, mh // 2 - 8), 0, 0, 360, 1.0, -1)
        # Protect microphone boom on bottom-right of mouth box
        m_alpha[44:, 82:] = 0.0
        self.peely_mouth_alpha = cv2.GaussianBlur(m_alpha, (15, 15), 4.0)[..., None]

    def _init_burger_sprites(self):
        H, W = self.base_frames[0].shape[:2]
        self.grid_x, self.grid_y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        self.w_upper = np.exp(-(((self.grid_x - 365.0) / 140.0) ** 2 + ((self.grid_y - 135.0) / 75.0) ** 2)).astype(np.float32)
        self.w_lower = np.exp(-(((self.grid_x - 375.0) / 120.0) ** 2 + ((self.grid_y - 285.0) / 85.0) ** 2)).astype(np.float32)
        self.w_tongue = np.exp(-(((self.grid_x - 382.0) / 58.0) ** 2 + ((self.grid_y - 295.0) / 80.0) ** 2)).astype(np.float32)
        self.gap_zone = np.exp(-(((self.grid_x - 365.0) / 95.0) ** 2 + ((self.grid_y - 208.0) / 16.0) ** 2)).astype(np.float32)

        # Sprite pose banks from Burger's 250 frames:
        self.burger_clips = {
            0: list(range(56, 66)) + list(range(65, 56, -1)),     # Pose 0: Calm idle
            1: list(range(70, 84)) + list(range(83, 70, -1)),     # Pose 1: Head tilt left talking
            2: list(range(95, 112)) + list(range(111, 95, -1)),   # Pose 2: Head tilt up / wide jaw
            3: list(range(218, 232)) + list(range(231, 218, -1)), # Pose 3: Leaning forward emphatic
            4: list(range(4, 19)) + list(range(18, 4, -1)),       # Pose 4: Raising glowing blue mic!
        }

    def _build_timeline(self):
        """Precomputes per-frame sprite index, mouth state, and glitch intensity."""
        self.frame_plan = []
        cur_state = 0
        hold_count = 0
        glitch_cooldown = 0

        if self.skin_key == "peely":
            # Segment banks for Peely body motion so body flows and jumps on sprite switches
            body_segments = [
                list(range(55, 108)),
                list(range(15, 52)),
                list(range(110, 165)),
                list(range(175, 235)),
            ]
            seg_idx = 0
            seg_cursor = 0

            for i in range(self.total_frames):
                rms = float(self.rms_arr[i])
                zcr = float(self.zcr_arr[i])

                # Determine target mouth sprite state (0=Closed, 1=Teeth, 2=Round O, 3=Mid, 4=Wide)
                if rms < 0.08:
                    target_state = 0
                elif hold_count < 2 and cur_state != 0:
                    # Hold mouth sprite at least 2 frames (1/12s) for crisp cartoon readability
                    target_state = cur_state
                else:
                    if zcr > 0.22 and rms < 0.72:
                        target_state = 1  # Teeth / consonant sprite
                    elif rms < 0.30:
                        target_state = 2  # Round O / small open sprite
                    elif rms < 0.62:
                        target_state = 3  # Mid open sprite
                    else:
                        target_state = 4  # Wide open sprite

                state_changed = target_state != cur_state
                if state_changed:
                    hold_count = 1
                else:
                    hold_count += 1

                # Switch full-body sprite segment on major state transitions to give real sprite-cut feel + Glitch!
                trigger_glitch = 0.0
                if state_changed and ((cur_state == 0 and target_state >= 2) or (target_state == 4 and glitch_cooldown <= 0)):
                    seg_idx = (seg_idx + 1) % len(body_segments)
                    seg_cursor = 0
                    if glitch_cooldown <= 0:
                        trigger_glitch = 1.0
                        glitch_cooldown = 9
                elif i % 26 == 12 and rms > 0.35 and glitch_cooldown <= 0:
                    trigger_glitch = 0.75
                    glitch_cooldown = 8

                if glitch_cooldown > 0:
                    glitch_cooldown -= 1

                cur_state = target_state
                cur_seg = body_segments[seg_idx]
                base_f_idx = cur_seg[seg_cursor % len(cur_seg)]
                seg_cursor += 1
                if seg_cursor >= len(cur_seg):
                    cur_seg.reverse()
                    seg_cursor = 0

                # Also pick a direct frame from the matching tier when available
                tier_list = self.tiers.get(cur_state, [100])
                sprite_f_idx = tier_list[(i // 2) % len(tier_list)]

                self.frame_plan.append({
                    "base_f_idx": base_f_idx,
                    "sprite_f_idx": sprite_f_idx,
                    "mouth_state": cur_state,
                    "rms": rms,
                    "glitch": trigger_glitch,
                })
        else:
            # Burger sprite timeline: jumps between the 5 Burger Sprite Poses (0..4) driven by audio syllables + Glitch
            active_pose = 0
            clip_cursor = 0
            pose_hold = 0
            for i in range(self.total_frames):
                rms = float(self.rms_arr[i])
                zcr = float(self.zcr_arr[i])

                if rms < 0.08:
                    target_state = 0
                    open_amt = 0.0
                elif rms < 0.28:
                    target_state = 1
                    open_amt = 0.45
                elif rms < 0.55:
                    target_state = 2
                    open_amt = 0.85
                elif rms < 0.80:
                    target_state = 3
                    open_amt = 1.15
                else:
                    target_state = 4
                    open_amt = 1.42

                # Quantize open_amt in 2-frame holds so it reads like snappy animated sprites
                if i % 2 == 1 and i > 0 and target_state > 0:
                    open_amt = self.frame_plan[-1]["open_amt"]
                    target_state = self.frame_plan[-1]["mouth_state"]

                # Switch Burger full-body sprite pose every 6-10 frames when talking state changes
                new_pose = active_pose
                pose_hold += 1
                if target_state == 0 and pose_hold >= 5:
                    new_pose = 0
                elif target_state >= 1 and pose_hold >= 7:
                    if target_state == 4:
                        new_pose = 4 if (i // 14) % 2 == 0 else 2
                    elif target_state == 3:
                        new_pose = 2 if (i // 10) % 2 == 0 else 3
                    else:
                        new_pose = 1 if (i // 8) % 2 == 0 else 3

                trigger_glitch = 0.0
                if new_pose != active_pose:
                    active_pose = new_pose
                    clip_cursor = 0
                    pose_hold = 0
                    trigger_glitch = 0.95
                    glitch_cooldown = 7
                elif abs(target_state - cur_state) >= 2 and glitch_cooldown <= 0:
                    trigger_glitch = 0.80
                    glitch_cooldown = 8

                if glitch_cooldown > 0:
                    glitch_cooldown -= 1

                cur_state = target_state
                clip_seq = self.burger_clips[active_pose]
                base_f_idx = clip_seq[clip_cursor % len(clip_seq)]
                clip_cursor += 1

                wag = math.sin(i * 0.75) * (0.95 if zcr > 0.18 else 0.55) * (1.0 if open_amt > 0.2 else 0.0)
                self.frame_plan.append({
                    "base_f_idx": base_f_idx,
                    "mouth_state": cur_state,
                    "open_amt": open_amt,
                    "wag": wag,
                    "rms": rms,
                    "glitch": trigger_glitch,
                })

    def synthesize_rgba(self, frame_idx: int) -> tuple[Image.Image, float, int]:
        plan = self.frame_plan[min(frame_idx, len(self.frame_plan) - 1)]
        glitch_level = float(plan["glitch"])
        # Also keep a 2nd frame decay if previous frame had a strong glitch
        if glitch_level == 0.0 and frame_idx > 0:
            prev_g = float(self.frame_plan[frame_idx - 1]["glitch"])
            if prev_g >= 0.8:
                glitch_level = prev_g * 0.48

        if self.skin_key == "peely":
            base_idx = plan["base_f_idx"]
            m_state = plan["mouth_state"]
            canon_idx = self.canonical_mouth_idx[m_state]

            frame_bgr = self.base_frames[base_idx].copy()
            src_mouth_bgr = self.base_frames[canon_idx]

            # Align canonical mouth sprite onto current base frame using eye offset delta
            dx_base, dy_base = self.eye_offsets[base_idx]
            dx_src, dy_src = self.eye_offsets[canon_idx]

            # Mouth box in canonical frame (100) is y=414..488, x=282..400
            sy1, sy2, sx1, sx2 = 414 + dy_src, 488 + dy_src, 282 + dx_src, 400 + dx_src
            dy1, dy2, dx1, dx2 = 414 + dy_base, 488 + dy_base, 282 + dx_base, 400 + dx_base

            patch_src = src_mouth_bgr[sy1:sy2, sx1:sx2].astype(np.float32)
            patch_dst = frame_bgr[dy1:dy2, dx1:dx2].astype(np.float32)

            # Match local banana yellow brightness smoothly
            blended = (patch_src * self.peely_mouth_alpha + patch_dst * (1.0 - self.peely_mouth_alpha)).astype(np.uint8)
            frame_bgr[dy1:dy2, dx1:dx2] = blended

            return _key_green_screen(frame_bgr), glitch_level, m_state

        else:
            # Burger Sprite Articulation
            base_idx = plan["base_f_idx"]
            open_amt = plan["open_amt"]
            wag = plan["wag"]
            m_state = plan["mouth_state"]
            frame_bgr = self.base_frames[base_idx]

            if open_amt <= 0.02:
                warped = frame_bgr.copy()
            else:
                dy = (
                    (self.w_upper * (open_amt * 19.0))
                    - (self.w_lower * (open_amt * 15.0))
                    - (self.w_tongue * (open_amt * 17.0))
                )
                dx = -(self.w_tongue * (wag * 12.0)) - (self.w_upper * (wag * -4.5))
                map_x = (self.grid_x + dx).astype(np.float32)
                map_y = (self.grid_y + dy).astype(np.float32)
                warped = cv2.remap(frame_bgr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

                wb = warped[:, :, 0].astype(np.float32)
                wg = warped[:, :, 1].astype(np.float32)
                wr = warped[:, :, 2].astype(np.float32)
                w_is_green = (wg - np.maximum(wr, wb)) > 25.0
                w_is_tongue = (wr - wg) > 22.0
                valid_cavity = (~w_is_green) & (~w_is_tongue)
                cavity_factor = np.where(valid_cavity, self.gap_zone * min(1.0, open_amt * 0.85), 0.0)[..., None]
                cavity_col = np.array([16.0, 12.0, 44.0], dtype=np.float32)
                warped = np.clip(warped.astype(np.float32) * (1.0 - cavity_factor) + cavity_col * cavity_factor, 0, 255).astype(np.uint8)

            return _key_green_screen(warped), glitch_level, m_state


def apply_cctv_and_glitch_fx(
    canvas: Image.Image,
    frame_idx: int,
    glitch_level: float,
    accent_rgb: tuple[int, int, int],
    cam_id: str,
    intensity: float = 1.0,
) -> Image.Image:
    """
    Aplica sobre la ventana del personaje (y=82..830):
    1. Líneas CCTV desfilando en vertical (tanto líneas verticales/horizontales de monitor táctico
       como dos barras luminosas de escaneo CCTV que desfilan verticalmente de arriba hacia abajo).
    2. Efectos de Glitch RGB + desplazamiento de franjas horizontales + interferencia digital
       sincronizados con los cambios de Sprite para disimular cualquier salto.
    """
    W, H = canvas.size
    y_top, y_bot = 82, 830
    arr = np.array(canvas, dtype=np.uint8)
    roi = arr[y_top:y_bot, :, :3].astype(np.float32)
    rh, rw = roi.shape[:2]

    # 1. GLITCH DISPLACEMENT & RGB CHROMATIC ABERRATION (cuando hay cambio de sprite o interferencia)
    if glitch_level > 0.05:
        rng = np.random.RandomState(frame_idx * 97 + 13)
        glitched = roi.copy()

        # RGB Chromatic Split horizontal
        shift_rgb = max(2, int(round(glitch_level * 9 * intensity)))
        glitched[:, shift_rgb:, 0] = roi[:, :-shift_rgb, 0]       # Red shifted right
        glitched[:, :-shift_rgb, 2] = roi[:, shift_rgb:, 2]       # Blue shifted left

        # Horizontal slice tears (attenuated and avoiding mouth area when intensity < 0.7)
        n_slices = int(2 + round(glitch_level * 4 * intensity))
        for _ in range(n_slices):
            if intensity < 0.7:
                sy = rng.randint(315, rh - 45) if rng.rand() > 0.25 else rng.randint(8, 68)
                sh = rng.randint(6, 24)
                sx = rng.choice([-1, 1]) * rng.randint(5, int(9 + glitch_level * 12))
            else:
                sy = rng.randint(10, rh - 45)
                sh = rng.randint(8, 38)
                sx = rng.choice([-1, 1]) * rng.randint(8, int(14 + glitch_level * 22))
            band = glitched[sy : sy + sh].copy()
            glitched[sy : sy + sh] = np.roll(band, sx, axis=1)
            # Flash cyan/magenta glitch line on slice border
            col_tear = np.array([0, 229, 255] if rng.rand() > 0.4 else [217, 70, 239], dtype=np.float32)
            glitched[sy : min(rh, sy + 2), :, :] = glitched[sy : min(rh, sy + 2), :, :] * 0.45 + col_tear * 0.55

        roi = glitched

    # 2. LÍNEAS CCTV DESFILANDO EN VERTICAL (Scanlines + Barras de Barrido Vertical + Lluvia de Líneas Verticales)
    yy = np.arange(rh, dtype=np.float32)[:, None]
    xx = np.arange(rw, dtype=np.float32)[None, :]

    # A) Finas líneas horizontales de monitor CCTV que desfilan verticalmente hacia abajo
    scroll_h = np.sin((yy - frame_idx * 3.2) * (math.pi / 2.5))
    scan_h_mask = (scroll_h > 0.35).astype(np.float32) * (0.11 * intensity)

    # B) Líneas verticales tipo CCTV / matriz táctica con onda luminosa desfilando en vertical (de arriba a abajo)
    vert_line_mask = ((np.arange(rw) % 6) == 0)[None, :].astype(np.float32)
    vert_wave = 0.5 + 0.5 * np.sin((yy - frame_idx * 14.0) * 0.045 + xx * 0.015)
    vert_cctv = vert_line_mask * vert_wave * (0.16 * intensity)

    # C) Dos barras de barrido CCTV ("rolling shutter bars") desfilando verticalmente de arriba a abajo
    bar1_y = (frame_idx * 19) % rh
    bar2_y = (frame_idx * 11 + rh // 2) % rh
    dist1 = np.minimum(np.abs(yy - bar1_y), rh - np.abs(yy - bar1_y))
    dist2 = np.minimum(np.abs(yy - bar2_y), rh - np.abs(yy - bar2_y))
    bar_glow = (np.exp(-(dist1 ** 2) / (2.0 * (26.0 ** 2))) * 0.22 + np.exp(-(dist2 ** 2) / (2.0 * (12.0 ** 2))) * 0.15) * intensity

    # D) Ráfagas de líneas verticales digitales cortas ("vertical CCTV data rain/streaks") desfilando hacia abajo
    streak_rng = np.random.RandomState(42)
    streak_cols = streak_rng.randint(24, rw - 24, size=18)
    streak_speeds = streak_rng.uniform(14.0, 26.0, size=18)
    streak_phases = streak_rng.uniform(0.0, rh, size=18)
    streak_len = 85.0
    streak_layer = np.zeros((rh, rw), dtype=np.float32)
    for sc_x, sp, ph in zip(streak_cols, streak_speeds, streak_phases):
        head_y = (frame_idx * sp + ph) % (rh + streak_len) - streak_len * 0.5
        dy_s = head_y - yy[:, 0]
        valid_s = (dy_s >= 0) & (dy_s <= streak_len)
        if np.any(valid_s):
            falloff = (1.0 - dy_s[valid_s] / streak_len) ** 1.5
            streak_layer[valid_s, sc_x : min(rw, sc_x + 2)] = np.maximum(
                streak_layer[valid_s, sc_x : min(rw, sc_x + 2)],
                falloff[:, None] * (0.38 * intensity),
            )

    # Apply dark scanline troughs and glowing cyan/accent CCTV highlights
    roi = roi * (1.0 - scan_h_mask[..., None])
    cctv_col = np.array([0.0, 229.0, 255.0], dtype=np.float32) * 0.65 + np.array(accent_rgb, dtype=np.float32) * 0.35
    total_glow = np.clip(vert_cctv + bar_glow + streak_layer, 0.0, 0.65)[..., None]
    roi = np.clip(roi * (1.0 - total_glow * 0.35) + cctv_col * total_glow, 0, 255)

    arr[y_top:y_bot, :, :3] = roi.astype(np.uint8)
    out_img = Image.fromarray(arr, mode="RGBA")

    # 3. HUD DE MONITOR CCTV (Esquinas de visor + Timecode + Indicador REC/GLITCH)
    hud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hud)
    c_cyan = (0, 229, 255, int(195 * intensity))
    c_acc = accent_rgb + (int(215 * intensity),)

    # Viewfinder corner brackets inside character viewport
    bx0, by0, bx1, by1 = 34, 96, W - 34, 814
    blen = 26
    for cx, cy, sx, sy in [
        (bx0, by0, 1, 1),
        (bx1, by0, -1, 1),
        (bx0, by1, 1, -1),
        (bx1, by1, -1, -1),
    ]:
        hd.line([(cx, cy), (cx + sx * blen, cy)], fill=c_cyan, width=3)
        hd.line([(cx, cy), (cx, cy + sy * blen)], fill=c_cyan, width=3)

    # Small CCTV badge on top-right below header
    f_cctv = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 13)
    tc_sec = frame_idx // 24
    tc_frm = frame_idx % 24
    tc_str = f"REC   {cam_id} // TC 00:{tc_sec:02d}:{tc_frm:02d}"
    hd.rounded_rectangle((W - 375, 92, W - 36, 118), radius=6, fill=(6, 10, 24, int(195 * intensity)), outline=c_cyan, width=1)
    dot_on = (frame_idx // 6) % 2 == 0
    if dot_on:
        hd.ellipse((W - 332, 100, W - 322, 110), fill=(255, 45, 85, 255))
    hd.text((W - 364, 105), tc_str, font=f_cctv, fill=c_acc, anchor="lm")

    if glitch_level > 0.35:
        hd.rounded_rectangle((42, 780, 245, 808), radius=6, fill=(217, 70, 239, 210))
        hd.text((143, 794), "⚡ SYNC // SEÑAL ENCRIPTADA", font=f_cctv, fill=(255, 255, 255, 255), anchor="mm")

    return Image.alpha_composite(out_img, hud)


class FeatherTalkFortniteEngine:
    def __init__(self, onnx_dir: str, voice_wav_path: str, ref_idx: int = 0, fps: int = 24):
        import onnxruntime as ort

        self.onnx_dir = onnx_dir
        self.fps = fps
        skin_key = os.path.basename(onnx_dir).replace("_onnx", "")

        hubert_path = os.path.join(onnx_dir, "feather_hubert.onnx")
        ft_path = os.path.join(onnx_dir, "feathertalk_144.onnx")
        bboxes_path = os.path.join(onnx_dir, "bboxes_240.npy")
        closed_win_path = os.path.join(onnx_dir, "closed_win.npy")
        video_path = os.path.join(onnx_dir, f"{skin_key}_25fps.mp4")
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
        ref_bbox = tuple(self.bboxes[min(ref_idx, len(self.bboxes) - 1)])
        ref_crop = _crop_face(ref_img, ref_bbox, crop_size=FACE_CROP_SIZE)
        self.ref_inner = _extract_inner(ref_crop, inner_size=FACE_INNER_SIZE)

        n_valid = min(len(self.base_frames), len(self.bboxes))
        base_seq = list(range(0, n_valid))
        self.ping_pong = base_seq + base_seq[-2:0:-1]
        self.pp_cursor = 0

        mask_alpha = np.zeros((FACE_INNER_SIZE, FACE_INNER_SIZE), dtype=np.float32)
        mask_alpha[16:134, 14:130] = 1.0
        self.mask_alpha = cv2.GaussianBlur(mask_alpha, (17, 17), 4.0)[..., None]

        self.feats_25, self.rms_24fps, self.total_frames = self._analyze_audio(voice_wav_path, fps=fps)

    def _analyze_audio(self, voice_wav_path: str, fps: int = 24):
        tmp_16k = voice_wav_path + ".tmp16k.wav"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", voice_wav_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                tmp_16k,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            feats_25, wav_f = extract_hubert_features(self.hubert_sess, tmp_16k)
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

        return feats_25, rms_arr, total_frames

    def synthesize_rgba(self, frame_idx: int) -> tuple[Image.Image, float, int]:
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

        # Subtle tactical glitch pulses every ~26 frames (attenuated by cctv_intensity=0.48)
        mod_f = frame_idx % 26
        if mod_f == 12:
            glitch = 0.55
        elif mod_f == 13:
            glitch = 0.30
        else:
            glitch = 0.0
        return _key_green_screen(frame_bgr), glitch, (0 if is_silent else 2)


def render_character_card_video(skin_key: str, cfg: dict, onnx_dir: str, ref_idx: int = 0):
    W, H = 720, 1280
    fps = 24

    voice_wav = os.path.join(onnx_dir, f"voice_{skin_key}.wav")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", cfg["voice_mp3"],
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le",
            voice_wav,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if cfg.get("mode") == "sprites":
        engine = SpriteFortniteEngine(skin_key, onnx_dir, voice_wav, fps=fps)
    else:
        engine = FeatherTalkFortniteEngine(onnx_dir, voice_wav, ref_idx=ref_idx, fps=fps)

    bg_raw = Image.open(os.path.join(ASSETS_DIR, "island_bg.webp")).convert("RGBA")
    bw, bh = bg_raw.size
    scale = max(W / float(bw), H / float(bh))
    bg_scaled = bg_raw.resize((int(bw * scale), int(bh * scale)), Image.Resampling.LANCZOS)
    left = (bg_scaled.width - W) // 2
    top = (bg_scaled.height - H) // 2
    bg_base = bg_scaled.crop((left, top, left + W, top + H))

    vignette = Image.new("RGBA", (W, H), (6, 10, 26, 75))
    bg_base = Image.alpha_composite(bg_base, vignette)

    bus_img = Image.open(os.path.join(ASSETS_DIR, "battle_bus.webp")).convert("RGBA")
    bus_img = bus_img.resize((150, int(150 * bus_img.height / bus_img.width)), Image.Resampling.LANCZOS)

    icon_date = Image.open(os.path.join(ICONS_ASSET_DIR, "09-icon-fecha-reloj.webp")).convert("RGBA").resize((58, 58), Image.Resampling.LANCZOS)
    icon_map = Image.open(os.path.join(ICONS_ASSET_DIR, "08-icon-mapa-drop.webp")).convert("RGBA").resize((58, 58), Image.Resampling.LANCZOS)
    icon_vip = Image.open(os.path.join(ICONS_ASSET_DIR, "10-icon-pase-vip.webp")).convert("RGBA").resize((54, 54), Image.Resampling.LANCZOS)

    logo_text = Image.open(os.path.join(ASSETS_DIR, "logo-text.webp")).convert("RGBA")
    _, _, _, la = logo_text.split()
    logo_white = Image.merge("RGBA", (*Image.new("RGB", logo_text.size, (255, 255, 255)).split(), la))
    logo_white = logo_white.resize((int(logo_white.width * (28.0 / logo_white.height)), 28), Image.Resampling.LANCZOS)

    f_badge = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 17)
    f_hero = ImageFont.truetype(r"C:\Windows\Fonts\impact.ttf", 40)
    f_sub = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 19)
    f_label = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)
    f_val = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 22)
    f_footer = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 16)

    accent = cfg["accent_rgb"]
    temp_mp4 = os.path.join(onnx_dir, f"_tmp_{skin_key}_card.mp4")
    vw = cv2.VideoWriter(temp_mp4, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    print(f"=== [{skin_key.upper()} · modo={cfg.get('mode')}] Renderizando {engine.total_frames} cuadros HD (720x1280) + CCTV/Glitch ===")
    for i in range(engine.total_frames):
        canvas = bg_base.copy()

        bus_y = 95 + int(8 * math.sin(i * 0.12))
        canvas.alpha_composite(bus_img, (34, bus_y))

        char_rgba, glitch_level, _ = engine.synthesize_rgba(i)
        canvas.alpha_composite(char_rgba, (0, cfg["char_y_offset"]))

        # Apply CCTV vertical lines & tactical Glitch FX on the character transmission area
        canvas = apply_cctv_and_glitch_fx(
            canvas,
            frame_idx=i,
            glitch_level=glitch_level,
            accent_rgb=accent,
            cam_id=cfg.get("cam_id", "CCTV-01"),
            intensity=cfg.get("cctv_intensity", 1.0),
        )

        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        od.rounded_rectangle((14, 14, W - 14, H - 14), radius=26, outline=accent + (210,), width=4)

        od.rounded_rectangle((30, 28, W - 30, 82), radius=14, fill=(9, 13, 30, 230), outline=(0, 229, 255, 190), width=2)
        od.ellipse((48, 47, 64, 63), fill=(34, 229, 102, 255))
        od.text((76, 55), cfg["badge_title"], font=f_badge, fill=accent + (255,), anchor="lm")
        ov.alpha_composite(logo_white, (W - 30 - logo_white.width - 16, 41))

        card_box = (24, 830, W - 24, 1250)
        crop_blur = canvas.crop(card_box).filter(ImageFilter.GaussianBlur(radius=14))
        glass = Image.new("RGBA", (card_box[2] - card_box[0], card_box[3] - card_box[1]), (0, 0, 0, 0))
        glass.paste(crop_blur, (0, 0))
        tint = Image.new("RGBA", glass.size, (8, 12, 30, 232))
        glass = Image.alpha_composite(glass, tint)

        mask = Image.new("L", glass.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, glass.width - 1, glass.height - 1), radius=24, fill=255)
        canvas.paste(glass, (card_box[0], card_box[1]), mask)

        od.rounded_rectangle(card_box, radius=24, outline=accent + (245,), width=3)

        hdr_box = (44, 848, W - 44, 924)
        od.rounded_rectangle(hdr_box, radius=14, fill=(20, 29, 68, 245), outline=(255, 230, 0, 220), width=2)
        ov.alpha_composite(icon_vip, (58, 859))
        od.text((126, 874), "¡ESTÁS INVITADO AL DROP ZONE!", font=f_label, fill=(0, 229, 255, 255), anchor="lm")
        od.text((126, 902), "DARÍO · ¡CUMPLE 8 AÑOS!", font=f_hero, fill=(255, 230, 0, 255), anchor="lm")

        r1_box = (44, 938, W - 44, 1028)
        od.rounded_rectangle(r1_box, radius=14, fill=(10, 15, 36, 245), outline=(0, 229, 255, 160), width=2)
        ov.alpha_composite(icon_date, (58, 954))
        od.text((130, 964), "FECHA Y HORA DE DESPLIEGUE", font=f_label, fill=(0, 229, 255, 255), anchor="lm")
        od.text((130, 995), "Sábado, 24 de Mayo 2026 · 4:00 PM", font=f_val, fill=(255, 255, 255, 255), anchor="lm")

        r2_box = (44, 1040, W - 44, 1130)
        od.rounded_rectangle(r2_box, radius=14, fill=(10, 15, 36, 245), outline=(217, 70, 239, 170), width=2)
        ov.alpha_composite(icon_map, (58, 1056))
        od.text((130, 1066), "ZONA DE DROP (UBICACIÓN)", font=f_label, fill=(217, 70, 239, 255), anchor="lm")
        od.text((130, 1097), "Salón Epic Zone, Av. Victory 123", font=f_val, fill=(255, 255, 255, 255), anchor="lm")

        cta_box = (44, 1146, W - 44, 1230)
        od.rounded_rectangle(cta_box, radius=14, fill=(255, 230, 0, 250))
        od.text((W // 2, 1176), "¡CONFIRMA TU ASISTENCIA Y OBTÉN TU PASE VIP!", font=f_sub, fill=(8, 11, 26, 255), anchor="mm")
        od.text((W // 2, 1206), "INVITACIÓN INTERACTIVA · DREAMCRAFTERS.LAT", font=f_footer, fill=(30, 41, 82, 255), anchor="mm")

        canvas = Image.alpha_composite(canvas, ov)
        rgb = np.array(canvas.convert("RGB"))
        vw.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    vw.release()

    bgm_path = os.path.join(ASSETS_DIR, "bgm.mp3")
    mixed_aac = os.path.join(onnx_dir, f"mixed_{skin_key}.m4a")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", voice_wav,
            "-i", bgm_path,
            "-filter_complex",
            "[0:a]volume=1.35[v];[1:a]volume=0.14[bg];[v][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "[a]",
            "-c:a", "aac", "-b:a", "128k",
            mixed_aac,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Encode Full High-Definition 720x1280 (-crf 15, high bitrate, 192k audio)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", temp_mp4,
            "-i", mixed_aac,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "slow",
            "-crf", "15",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            cfg["out_mp4"],
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.path.exists(temp_mp4):
        os.remove(temp_mp4)

    shutil.copy2(cfg["out_mp4"], cfg["rec_final_mp4"])
    if os.path.exists(ARTIFACT_DIR):
        shutil.copy2(cfg["out_mp4"], os.path.join(ARTIFACT_DIR, f"video_{skin_key}.mp4"))
    sz_mb = os.path.getsize(cfg["out_mp4"]) / (1024 * 1024.0)
    print(f"  [OK] Video HD listo: {cfg['out_mp4']} ({sz_mb:.2f} MB)")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["jonesy", "bomber", "peely", "burger"]
    for skin_key in targets:
        cfg = CHARACTER_CONFIGS[skin_key]
        onnx_dir = os.path.join(DC_CHAR_05_DIR, f"{skin_key}_onnx")
        render_character_card_video(skin_key, cfg, onnx_dir, ref_idx=0)


if __name__ == "__main__":
    main()
