# -*- coding: utf-8 -*-
"""
mario_modular_rig.py — Librería Oficial del Rig Modular 2K Simétrico de Mario (Toon Maker v2)
=============================================================================================
Empaqueta el personaje de Mario de Cuerpo Completo en 2 capas modulares:
  1. `HEAD_LIPSYNC` (9 cabezas flotantes 2K con sub-pixel optical lock):
     - 00: MBP (boca cerrada, ojos abiertos)
     - 01: BLINK (boca cerrada, ojos cerrados)
     - 02: STI (dientes / sibilantes S, T, I)
     - 03: E (vocal pequeña E)
     - 04: AE (vocal media conversacional A/E)
     - 05: AA (vocal abierta amplia AH)
     - 06: OH (vocal redonda O)
     - 07: UW (labios fruncidos U/W)
     - 08: BLINK_TALK (parpadeo hablando con boca abierta)
  2. `BODY_POSES` (Exclusivamente las 5 poses de cuerpo 100% frontales y simétricas):
     - 00: HERO_NEUTRAL (postura heroica frontal neutra)
     - 04: DOUBLE_THUMBS_UP (ambos pulgares arriba simétricos)
     - 06: HANDS_ON_HIPS (ambas manos en la cintura)
     - 07: OPEN_PALMS_EXPLAIN (ambas palmas abiertas explicando al frente)
     - 08: EXCITED_FISTS_PUMPED (ambos puños celebrando simétricos)

Se omiten por diseño las poses asimétricas de una sola mano alzada o giro 3/4 (01, 02, 03, 05)
para garantizar que el eje central vertical (emblema M -> nariz -> mentón -> costura central
del overol -> centro entre botas) permanezca 100% colineal en x = 380 (sobre lienzo 760x920).
"""

import os
import json
import math
import wave
import cv2
import numpy as np
from PIL import Image


SYMMETRIC_POSE_IDS = (0, 4, 6, 7, 8)

POSE_ALIASES = {
    "neutral": 0,
    "hero_neutral": 0,
    "thumbs": 4,
    "double_thumbs_up": 4,
    "happy": 4,
    "hips": 6,
    "hands_on_hips": 6,
    "confident": 6,
    "palms": 7,
    "open_palms": 7,
    "explain": 7,
    "fists": 8,
    "excited_fists": 8,
    "celebrate": 8,
}

VISEME_NAMES = [
    "00:MBP",
    "01:BLINK",
    "02:STI",
    "03:E",
    "04:AE",
    "05:AA",
    "06:OH",
    "07:UW",
    "08:BLINK_TALK",
]


def _load_cv_rgba_unicode(path):
    """Carga un PNG RGBA de forma segura en Windows/Linux soportando rutas con acentos o espacios."""
    pil_img = Image.open(path).convert("RGBA")
    r, g, b, a = pil_img.split()
    return cv2.merge([np.array(b), np.array(g), np.array(r), np.array(a)])


def _composite_rgba_onto_rgba(dst, src, x_off, y_off):
    """Composición alfa exacta de dos matrices BGRA uint8."""
    out = dst.copy()
    H_d, W_d = out.shape[:2]
    sh, sw = src.shape[:2]
    x0 = max(0, x_off)
    y0 = max(0, y_off)
    x1 = min(W_d, x_off + sw)
    y1 = min(H_d, y_off + sh)
    if x0 >= x1 or y0 >= y1:
        return out
    sx0 = x0 - x_off
    sy0 = y0 - y_off
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    src_crop = src[sy0:sy1, sx0:sx1].astype(np.float32)
    dst_crop = out[y0:y1, x0:x1].astype(np.float32)
    sa = src_crop[:, :, 3:4] / 255.0
    da = dst_crop[:, :, 3:4] / 255.0
    out_a = sa + da * (1.0 - sa)
    safe_a = np.where(out_a > 1e-5, out_a, 1.0)
    out_rgb = (src_crop[:, :, :3] * sa + dst_crop[:, :, :3] * da * (1.0 - sa)) / safe_a
    out[y0:y1, x0:x1, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    out[y0:y1, x0:x1, 3:4] = np.clip(out_a * 255.0, 0, 255).astype(np.uint8)
    return out


class MarioModularRig:
    """
    Librería reutilizable del Rig Modular 2K Simétrico de Mario.
    Ensambla bajo demanda (con caché en RAM) cualquiera de las 45 combinaciones simétricas
    (5 cuerpos frontales × 9 visemas 2K) sobre un lienzo canónico de 760×920.
    """

    CANVAS_W = 760
    CANVAS_H = 920
    CENTER_X = 380
    BOOT_SOLE_Y = 876

    def __init__(self, rig_dir):
        self.rig_dir = os.path.abspath(rig_dir)
        rig_json_path = os.path.join(self.rig_dir, "rig_config.json")
        if not os.path.exists(rig_json_path):
            raise FileNotFoundError(f"No se encontró rig_config.json en: {rig_json_path}")

        with open(rig_json_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)

        self.head_scale = float(self.cfg["head_on_body_scale"])
        self.chin_overlap = int(self.cfg["chin_overlap_px"])
        self.ref_chin_y = float(self.cfg["ref_chin_y_unscaled"]) * self.head_scale
        self.ref_head_cx = float(self.cfg["ref_head_cx_unscaled"]) * self.head_scale

        heads_dir = os.path.join(self.rig_dir, "HEAD_LIPSYNC")
        self.heads_scaled = {}
        for v_idx in range(9):
            h_path = os.path.join(heads_dir, f"{v_idx:02d}.png")
            h_img = _load_cv_rgba_unicode(h_path)
            sh = int(round(h_img.shape[0] * self.head_scale))
            sw = int(round(h_img.shape[1] * self.head_scale))
            self.heads_scaled[v_idx] = cv2.resize(h_img, (sw, sh), interpolation=cv2.INTER_LANCZOS4)

        bodies_dir = os.path.join(self.rig_dir, "BODY_POSES")
        self.bodies = {}
        self.body_meta = {}
        for b_info in self.cfg["bodies"]:
            b_idx = int(b_info["index"])
            if b_idx not in SYMMETRIC_POSE_IDS:
                continue
            b_path = os.path.join(bodies_dir, f"{b_idx:02d}.png")
            if os.path.exists(b_path):
                self.bodies[b_idx] = _load_cv_rgba_unicode(b_path)
                self.body_meta[b_idx] = b_info

        if not self.bodies:
            raise RuntimeError(f"No se encontraron cuerpos simétricos en {bodies_dir}")

        self._cache_pil = {}

    def resolve_pose_id(self, pose):
        """Garantiza que cualquier pose solicitada resuelva a una de las 5 poses frontales simétricas."""
        if isinstance(pose, str):
            p_id = POSE_ALIASES.get(pose.lower().strip(), 0)
        else:
            p_id = int(pose)
        if p_id in self.bodies:
            return p_id
        # Mapeo seguro de poses asimétricas a su equivalente simétrico frontal
        fallback_map = {1: 8, 2: 7, 3: 4, 5: 6}
        mapped = fallback_map.get(p_id, 0)
        return mapped if mapped in self.bodies else list(self.bodies.keys())[0]

    def get_puppet_pil(self, pose=0, viseme_idx=0, nod_px=0):
        """
        Devuelve un `PIL.Image` RGBA (760x920) con el cuerpo simétrico `pose` y la cabeza `viseme_idx`
        perfectamente centrados sobre el eje vertical x = 380.
        """
        p_id = self.resolve_pose_id(pose)
        v_id = int(np.clip(viseme_idx, 0, 8))
        nod_i = int(np.clip(round(nod_px), 0, 2))

        cache_key = (p_id, v_id, nod_i)
        if cache_key in self._cache_pil:
            return self._cache_pil[cache_key]

        body_bgra = self.bodies[p_id]
        head_bgra = self.heads_scaled[v_id]
        meta = self.body_meta[p_id]

        collar_y = float(meta["collar_y"])
        neck_cx = float(meta["neck_cx"])

        hx_off = int(round(neck_cx - self.ref_head_cx))
        hy_off = int(round(collar_y + self.chin_overlap - self.ref_chin_y)) + nod_i

        puppet_bgra = _composite_rgba_onto_rgba(body_bgra, head_bgra, hx_off, hy_off)
        b, g, r, a = cv2.split(puppet_bgra)
        pil_img = Image.fromarray(cv2.merge([r, g, b, a]))
        self._cache_pil[cache_key] = pil_img
        return pil_img

    @staticmethod
    def select_symmetric_pose(scene_type, sc_prog):
        """
        Coreografía oficial para los Reels de DreamCrafters usando únicamente las 5 poses
        frontales simétricas (`00`, `04`, `06`, `07`, `08`).
        """
        if scene_type == "hook":
            if sc_prog < 0.25:
                return 8  # EXCITED_FISTS_PUMPED (Saludo enérgico "¡Hola amigos! Soy yo, Mario")
            elif sc_prog < 0.52:
                return 6  # HANDS_ON_HIPS ("¿Todavía mandas invitaciones aburridas...?")
            elif sc_prog < 0.78:
                return 7  # OPEN_PALMS_EXPLAIN ("En DreamCrafters convertimos tu invitación...")
            else:
                return 4  # DOUBLE_THUMBS_UP ("...en un videojuego real!")

        elif scene_type == "gameplay":
            if sc_prog < 0.36:
                return 7  # OPEN_PALMS_EXPLAIN ("Mira qué divertido: tus invitados abren el enlace...")
            elif sc_prog < 0.70:
                return 8  # EXCITED_FISTS_PUMPED ("...y tienen que atrapar las monedas espaciales...")
            else:
                return 4  # DOUBLE_THUMBS_UP ("...para desbloquear todos los detalles de tu fiesta.")

        elif scene_type == "unlocked":
            if sc_prog < 0.35:
                return 0  # HERO_NEUTRAL ("Al lograr la misión se abre la invitación...")
            elif sc_prog < 0.70:
                return 7  # OPEN_PALMS_EXPLAIN ("...cuenta regresiva, mapa exacto en Google Maps...")
            else:
                return 6  # HANDS_ON_HIPS ("...y botón para confirmar asistencia directo a tu WhatsApp.")

        elif scene_type == "website":
            if sc_prog < 0.52:
                return 7  # OPEN_PALMS_EXPLAIN ("Además, si entras ahora a dreamcrafters.lat...")
            else:
                return 4  # DOUBLE_THUMBS_UP ("...puedes crear gratis la invitación de Minecraft en 1 minuto.")

        else:  # cta
            if sc_prog < 0.56:
                return 8  # EXCITED_FISTS_PUMPED ("¡Muchas felicidades! Te esperamos hoy...")
            else:
                return 0  # HERO_NEUTRAL ("DreamCrafters, artificialmente hechos a mano.")

    @staticmethod
    def analyze_voice_visemes(wav_path, fps=24, intro_duration_sec=1.30):
        """
        Analiza el archivo WAV de voz clonada y genera la trayectoria cuadro por cuadro
        de los 9 visemas (`00:MBP` a `08:BLINK_TALK`) + energía RMS normalizada.
        """
        with wave.open(wav_path, "rb") as wf:
            sr = wf.getframerate()
            n_ch = wf.getnchannels()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if n_ch > 1:
            samples = samples.reshape(-1, n_ch).mean(axis=1)
        samples /= 32768.0

        dur = len(samples) / float(sr)
        total_video_frames = int(math.ceil(dur * fps))
        hop = int(sr / fps)

        rms_arr = np.zeros(total_video_frames, dtype=np.float32)
        centroid_arr = np.zeros(total_video_frames, dtype=np.float32)
        is_valley = np.zeros(total_video_frames, dtype=bool)

        for i in range(total_video_frames):
            s0 = i * hop
            s1 = min(len(samples), s0 + hop)
            chunk = samples[s0:s1]
            if len(chunk) < 32:
                continue
            rms = math.sqrt(float(np.mean(chunk * chunk)) + 1e-12)
            rms_arr[i] = rms

            win = chunk * np.hanning(len(chunk))
            spec = np.abs(np.fft.rfft(win))
            freqs = np.fft.rfftfreq(len(chunk), d=1.0 / sr)
            spec_sum = float(np.sum(spec)) + 1e-9
            centroid_arr[i] = float(np.sum(freqs * spec) / spec_sum)

        p95 = float(np.percentile(rms_arr[rms_arr > 0.005], 95)) if np.any(rms_arr > 0.005) else 1.0
        rms_norm = np.clip(rms_arr / max(p95, 1e-4), 0.0, 1.0)

        last_val = -10
        for i in range(1, total_video_frames - 1):
            if rms_norm[i] > 0.08:
                dip = (rms_norm[i] < rms_norm[i - 1] * 0.84 and rms_norm[i] <= rms_norm[i + 1]) or (rms_norm[i] < 0.17)
                if dip and (i - last_val) >= 4:
                    is_valley[i] = True
                    last_val = i

        intro_frames = int(round(intro_duration_sec * fps))
        visemes = np.zeros(total_video_frames, dtype=np.int32)
        is_speaking = np.zeros(total_video_frames, dtype=bool)

        blink_frames = set()
        for b_start in range(38, total_video_frames, 58):
            for f in range(b_start, min(total_video_frames, b_start + 3)):
                blink_frames.add(f)

        last_v = 0
        hold_count = 0
        open_streak = 0

        for i in range(total_video_frames):
            is_blink = i in blink_frames
            if i < intro_frames:
                visemes[i] = 1 if is_blink else 0
                continue

            e = float(rms_norm[i])
            c = float(centroid_arr[i])

            if e < 0.09 or (is_valley[i] and open_streak >= 3 and e < 0.55):
                v = 1 if is_blink else 0
                last_v = v
                hold_count = 0
                open_streak = 0
                is_speaking[i] = False
            else:
                is_speaking[i] = True
                open_streak += 1
                if is_blink:
                    v = 8  # BLINK_TALK
                elif e > 0.65:
                    v = 5 if c > 1250 else 6  # AA vs OH
                elif e > 0.36:
                    if c > 1950:
                        v = 2  # STI
                    elif c < 1050:
                        v = 6  # OH
                    else:
                        v = 4  # AE
                else:
                    if c > 2100:
                        v = 2  # STI
                    elif c < 980:
                        v = 7  # UW
                    else:
                        v = 3  # E

                if last_v in (2, 3, 4, 5, 6, 7) and v != 8 and hold_count < 1 and abs(v - last_v) <= 2 and e < 0.72:
                    v = last_v
                    hold_count += 1
                else:
                    last_v = v
                    hold_count = 0

            visemes[i] = v

        return {
            "rms_norm": rms_norm,
            "visemes": visemes,
            "is_speaking": is_speaking,
            "duration_sec": dur,
            "total_frames": total_video_frames,
        }
