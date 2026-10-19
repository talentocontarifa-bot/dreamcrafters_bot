# -*- coding: utf-8 -*-
"""
render_dreamcrafters_video.py — Motor Oficial de Video Promocional DreamCrafters
================================================================================
- Clonación de Voz 100% Local (PyTorch `ChatterboxMultilingualTTS` de `chatterbox-tts`),
  sin llamadas externas a Gradio Spaces.
- Intro rápido (1.3s) con el ícono "D" (`d-icon.svg`) animado + transición al header.
- Invitación real `/invitacionmario/index.html` y `dreamcrafters.lat` renderizadas en
  modo móvil real vía Playwright Chromium.
"""

import os
import sys
import glob
import math
import json
import wave
import hashlib
import argparse
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TOON_HOST_DIR = os.path.join(REPO_ROOT, "toon_host")
if TOON_HOST_DIR not in sys.path:
    sys.path.insert(0, TOON_HOST_DIR)

from toon_packager import ToonPackager

CHAR_02_DIR = os.path.join(REPO_ROOT, "characters", "02_mario")
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
LANDING_DIR = os.path.join(WEB_ASSETS_DIR, "landing")
REF_WAV = os.path.join(CHAR_02_DIR, "mario_ref_8s.wav")
REAL_CAP_DIR = os.path.join(CHAR_02_DIR, "out", "real_mobile_capture")
INTRO_DURATION_SEC = 1.30


SCENES_CLEAN = [
    {
        "type": "hook",
        "accent_rgb": (56, 189, 248),
        "top_caption": "¿OTRA IMAGEN FIJA EN WHATSAPP?",
        "bottom_pill": "INVITACIONES QUE SE JUEGAN EN TU CEL",
        "voice_text": "¡Hola amigos! Soy yo, Mario. ¿Todavía mandas invitaciones aburridas de imagen fija por WhatsApp? En Drim Crafters convertimos tu invitación en un videojuego real.",
    },
    {
        "type": "gameplay",
        "accent_rgb": (250, 204, 21),
        "top_caption": "TUS INVITADOS JUEGAN PARA ENTRAR",
        "bottom_pill": "ATRAPA 50 PUNTOS SIN INSTALAR APPS",
        "voice_text": "Mira qué divertido: tus invitados abren el enlace en su celular y tienen que atrapar las monedas espaciales para desbloquear todos los detalles de tu fiesta.",
    },
    {
        "type": "unlocked",
        "accent_rgb": (56, 189, 248),
        "top_caption": "CUENTA REGRESIVA + MAPA GPS",
        "bottom_pill": "CONFIRMACIÓN EN 1 TOQUE A WHATSAPP",
        "voice_text": "Al lograr la misión se abre la invitación con música épica, cuenta regresiva, mapa exacto en Google Maps y botón para confirmar asistencia directo a tu WhatsApp.",
    },
    {
        "type": "website",
        "accent_rgb": (74, 222, 128),
        "top_caption": "CREA LA DE MINECRAFT GRATIS",
        "bottom_pill": "PERSONALIZA EN 60 SEG EN DREAMCRAFTERS.LAT",
        "voice_text": "Además, si entras ahora a drim crafters punto lat, puedes escribir el nombre y la edad de tu festejado y crear gratis la invitación interactiva de Minecraft en un minuto.",
    },
    {
        "type": "cta",
        "accent_rgb": (250, 204, 21),
        "top_caption": "¡SORPRENDE A TODO EL SALÓN!",
        "bottom_pill": "VISITA HOY DREAMCRAFTERS.LAT",
        "voice_text": "¡Muchas felicidades! Te esperamos hoy en drim crafters punto lat. Drim Crafters, artificialmente hechos a mano.",
    },
]


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


def synthesize_cloned_scenes_local(scenes, ref_wav_path, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Clona la voz de `ref_wav_path` 100% localmente usando PyTorch + `ChatterboxMultilingualTTS`
    (sin depender de Gradio Spaces externos), manteniendo caché por SHA-256 de cada línea.
    """
    cache_dir = os.path.join(CHAR_02_DIR, "out", "cloned_voice_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    intro_pcm = generate_intro_chime_pcm(INTRO_DURATION_SEC, sr=sr)
    pause_samples = np.zeros(int(0.26 * sr), dtype=np.int16)
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

    local_model = None

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"chatterbox_mario_v1|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"mario_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav):
            print(f"[Chatterbox Local] Clonando voz de Mario en CPU/GPU local para Escena {idx+1}...")
            import torch
            import torchaudio as ta
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            if local_model is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                local_model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                local_model.prepare_conditionals(ref_wav_path, exaggeration=0.55)

            torch.manual_seed(42)
            wav_tensor = local_model.generate(
                text=v_text,
                language_id="es",
                audio_prompt_path=None,  # Reutiliza los conditionals ya calculados de mario_ref_8s.wav
                exaggeration=0.55,
                cfg_weight=0.50,
                temperature=0.72,
            )
            raw_tmp = os.path.join(cache_dir, f"_raw_sc_{idx+1}.wav")
            ta.save(raw_tmp, wav_tensor, local_model.sr)

            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    raw_tmp,
                    "-af",
                    "highpass=f=85,lowpass=f=11000,acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=3dB,alimiter=limit=0.95",
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
            sc_copy["end"] = round(cur_time + dur + 0.26, 3)
            cur_time += dur + 0.26
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


class CleanDreamCraftersRenderer:
    def __init__(self, packager):
        self.tp = packager
        self.W = 720
        self.H = 1280

        party_bg_path = os.path.join(CHAR_02_DIR, "party_bg.jpeg")
        self.party_bg = load_pil_rgba(party_bg_path, (self.W, self.H))

        d_icon_path = os.path.join(REAL_CAP_DIR, "d_icon_hd.png")
        self.d_icon_hd = load_pil_rgba(d_icon_path)
        self.d_icon_header = load_pil_rgba(d_icon_path, (54, 56))

        raw_logo = load_pil_rgba(os.path.join(LANDING_DIR, "logo-text.png"))
        if raw_logo:
            r_c, g_c, b_c, a_c = raw_logo.split()
            white_rgb = Image.new("RGB", raw_logo.size, (250, 246, 238))
            self.logo_text = Image.merge("RGBA", (*white_rgb.split(), a_c))
        else:
            self.logo_text = None

        self.gameplay_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "gameplay", "frame_*.png")))
        self.unlocked_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "unlocked", "frame_*.png")))
        self.website_frames = sorted(glob.glob(os.path.join(REAL_CAP_DIR, "website", "frame_*.png")))
        print(
            f"Frames moviles reales cargados: gameplay={len(self.gameplay_frames)}, "
            f"unlocked={len(self.unlocked_frames)}, website={len(self.website_frames)}"
        )

        bg_arr = np.zeros((self.H, self.W, 3), dtype=np.uint8)
        y_grid, x_grid = np.ogrid[: self.H, : self.W]
        dist = np.sqrt(((x_grid - self.W * 0.5) / 380.0) ** 2 + ((y_grid - self.H * 0.46) / 520.0) ** 2)
        glow = np.clip(1.0 - dist, 0.0, 1.0) ** 1.6
        bg_arr[:, :, 0] = (10 + glow * 16).astype(np.uint8)
        bg_arr[:, :, 1] = (14 + glow * 26).astype(np.uint8)
        bg_arr[:, :, 2] = (24 + glow * 50).astype(np.uint8)
        self.clean_dark_bg = Image.fromarray(bg_arr).convert("RGBA")

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

    def render_logo_intro_frame(self, sc_prog):
        canvas = self.clean_dark_bg.copy()
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

    def render_phone_content(self, scene_type, sc_prog):
        pw, ph = 420, 796
        if scene_type == "gameplay" and self.gameplay_frames:
            f_idx = min(len(self.gameplay_frames) - 1, int(sc_prog * len(self.gameplay_frames)))
            return Image.open(self.gameplay_frames[f_idx]).convert("RGBA").resize((pw, ph), Image.Resampling.LANCZOS)

        if scene_type == "unlocked" and self.unlocked_frames:
            f_idx = min(len(self.unlocked_frames) - 1, int(sc_prog * len(self.unlocked_frames)))
            return Image.open(self.unlocked_frames[f_idx]).convert("RGBA").resize((pw, ph), Image.Resampling.LANCZOS)

        if scene_type == "website" and self.website_frames:
            f_idx = min(len(self.website_frames) - 1, int(sc_prog * len(self.website_frames)))
            return Image.open(self.website_frames[f_idx]).convert("RGBA").resize((pw, ph), Image.Resampling.LANCZOS)

        if self.unlocked_frames:
            return Image.open(self.unlocked_frames[-1]).convert("RGBA").resize((pw, ph), Image.Resampling.LANCZOS)
        return Image.new("RGBA", (pw, ph), (11, 13, 18, 255))

    def render_frame(self, idx, total_frames, fps, pos_val, scene_info):
        t_sec = idx / float(fps)
        sc = scene_info["scene"]
        sc_prog = scene_info["progress"]
        sc_type = sc["type"]

        if sc_type == "logo_intro":
            return self.render_logo_intro_frame(sc_prog)

        accent = sc["accent_rgb"]
        s_idx = int(round(np.clip(pos_val, 0, len(self.tp.rgba_ladder) - 1)))
        mario_rgba_cv = self.tp.rgba_ladder[s_idx]
        b, g, r, a = cv2.split(mario_rgba_cv)
        mario_pil = Image.fromarray(cv2.merge([r, g, b, a]))
        breath_y = int(math.sin(t_sec * 2.5) * 4)

        if sc_type in ("hook", "cta"):
            canvas = self.party_bokeh_bg.copy()
            mario_crop = mario_pil.crop((40, 40, 680, 1180))
            mw, mh = 560, 995
            mario_big = mario_crop.resize((mw, mh), Image.Resampling.LANCZOS)

            enter_offset_y = 0
            if sc_type == "hook" and sc_prog < 0.08:
                u = sc_prog / 0.08
                enter_offset_y = int((1.0 - u) * 45)

            canvas.alpha_composite(mario_big, ((self.W - mw) // 2, 175 + breath_y + enter_offset_y))

            grad = Image.new("RGBA", (self.W, 380), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grad)
            for gy in range(380):
                alpha_g = int(235 * ((gy / 380.0) ** 1.4))
                gd.line([(0, gy), (self.W, gy)], fill=(8, 10, 16, alpha_g))
            canvas.alpha_composite(grad, (0, self.H - 380))
        else:
            canvas = self.clean_dark_bg.copy()
            cd = ImageDraw.Draw(canvas)

            phone_w, phone_h = 420, 796
            phone_x = (self.W - phone_w) // 2 - 34
            phone_y = 180

            cd.rounded_rectangle(
                (phone_x - 10, phone_y - 10, phone_x + phone_w + 10, phone_y + phone_h + 10),
                radius=46,
                fill=(18, 22, 30, 255),
                outline=(250, 246, 238, 165),
                width=3,
            )

            phone_scr = self.render_phone_content(sc_type, sc_prog)
            mask = Image.new("L", (phone_w, phone_h), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, phone_w, phone_h), radius=38, fill=255)
            canvas.paste(phone_scr, (phone_x, phone_y), mask)

            cd = ImageDraw.Draw(canvas)
            sp_w = 76
            sp_x = phone_x + (phone_w - sp_w) // 2
            cd.rounded_rectangle((sp_x, phone_y - 7, sp_x + sp_w, phone_y - 3), radius=2, fill=(60, 68, 82, 220))
            hi_w = 130
            hi_x = phone_x + (phone_w - hi_w) // 2
            cd.rounded_rectangle((hi_x, phone_y + phone_h - 14, hi_x + hi_w, phone_y + phone_h - 9), radius=3, fill=(255, 255, 255, 190))

            mario_crop = mario_pil.crop((80, 70, 640, 930))
            mw, mh = 310, 475
            mario_corner = mario_crop.resize((mw, mh), Image.Resampling.LANCZOS)
            canvas.alpha_composite(mario_corner, (self.W - mw + 18, self.H - mh - 98 + breath_y))

        cd = ImageDraw.Draw(canvas)

        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (32, 28))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 34
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (98, 40))

        cd.text((self.W // 2, 134), sc["top_caption"], font=self.f_top_title, fill=(250, 246, 238), anchor="mm")

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

    # Si aún no existen las capturas móviles reales, ejecutarlas automáticamente con Playwright
    if not os.path.exists(os.path.join(REAL_CAP_DIR, "d_icon_hd.png")):
        from capture_real_mario_mobile import capture_all
        capture_all()

    with open(os.path.join(CHAR_02_DIR, "character.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)

    source_vid = os.path.join(CHAR_02_DIR, cfg["assets"]["source_video"])
    bgm_rel = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")
    ladder = cfg["rig"]["frame_ladder"]

    packager = ToonPackager(
        source_video_path=source_vid,
        frame_ladder=ladder,
        bgm_path=bgm_rel if os.path.exists(bgm_rel) else None,
        phonetic_mode=True,
        blend_mode="snap",
    )

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "mario_cloned_voice.wav")

    print("Sintetizando narracion con ChatterboxMultilingualTTS local...")
    scenes = synthesize_cloned_scenes_local(SCENES_CLEAN, REF_WAV, clean_wav, ffmpeg_path=packager.ffmpeg_path)

    fps = 24
    positions, _, _ = packager.compute_smooth_ladder_trajectory(clean_wav, fps=fps)
    intro_frames = int(INTRO_DURATION_SEC * fps)
    for k in range(min(intro_frames, len(positions))):
        positions[k] = 0.0

    total_frames = len(positions)
    print(f"Renderizando {total_frames} frames ({total_frames/fps:.1f}s)...")

    renderer = CleanDreamCraftersRenderer(packager)
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

        bgr = renderer.render_frame(i, total_frames, fps, positions[i], {"scene": active_sc, "progress": prog})
        vw.write(bgr)

    vw.release()

    mixed_wav = os.path.join(out_dir, "mario_cloned_mixed.wav")
    final_audio = packager.mix_voice_with_bgm(clean_wav, mixed_wav, bgm_vol=0.12)

    subprocess.run(
        [
            packager.ffmpeg_path,
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
    print(f"Video listo: {args.output}")


if __name__ == "__main__":
    main()
