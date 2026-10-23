# -*- coding: utf-8 -*-
"""
render_bttf_commercials.py
==========================
Genera los 2 Videos Promocionales Oficiales de Volver al Futuro (720x1280 @ 24 FPS, velocidad 1.0x real):
1) `juego_150_marty` (`video_bttf_promo_invitacion_150.mp4`):
   Comercial Invitación de Volver al Futuro 88 MPH ($150 MXN Combo 2 en 1) con Marty McFly (Voz Clonada ElevenLabs v4 + FeatherTalk ONNX sin línea blanca).
2) `afiliados_20_marty` (`video_bttf_afiliados_20.mp4`):
   Comercial Programa de Afiliados / Socios 20% Vía SPEI con Marty McFly invitando a ganar dinero recomendando las invitaciones interactivas (`dreamcrafters.lat/socios`).
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
from PIL import Image, ImageDraw, ImageFilter

from render_dreamcrafters_video import (
    REPO_ROOT,
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

INV_DIR = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\invitacion-volver-al-futuro"
BTTF_ASSETS_DIR = os.path.join(INV_DIR, "assets")
BTTF_AUDIO_DIR = os.path.join(BTTF_ASSETS_DIR, "audio")
BTTF_SFX_DIR = os.path.join(BTTF_AUDIO_DIR, "sfx")
DC_CHAR_06_DIR = os.path.join(REPO_ROOT, "characters", "06_marty")
BTTF_CAP_DIR = os.path.join(DC_CHAR_06_DIR, "real_mobile_capture")
ARTIFACT_DIR = r"C:\Users\rufin\.gemini\antigravity\brain\10e4db52-4bc5-4325-8917-6fe3620cc025"

ELEVENLABS_API_KEY = os.environ.get(
    "ELEVENLABS_API_KEY",
    "sk_1a6f82b58f6110efdb8b0cce0b470505b9630bbdf8b69795",
)
MARTY_VOICE_ID = "t1lByQjoc2iRlnuSXgYB"

FACE_CROP_SIZE = 152
FACE_INNER_SIZE = 144
FACE_BORDER = 4

# ==============================================================================
# GUIONES DE LOS 2 COMERCIALES OFICIALES DE VOLVER AL FUTURO (MARTY MCFLY)
# ==============================================================================

SCENES_JUEGO_150_MARTY = [
    {
        "type": "hook",
        "accent_rgb": (255, 190, 0),
        "promo_badge": "PAQUETE $150: JUEGO + VIDEO",
        "bottom_pill": "¡MARTY MCFLY SALUDA A TU PEQUE EN VIDEO!",
        "voice_text": "[excited] ¡¡Santos protones, viajeros del tiempo!! ¡Soy Marty McFly! [enthusiastic] ¿¡Sabías que por solo ciento cincuenta pesos tu peque puede tener una invitación de Volver al Futuro donde conduces el DeLorean a ochenta y ocho millas por hora y además un video mío felicitándolo!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "CABINA DELOREAN 360°",
        "bottom_pill": "ACELERA A 88 MPH Y VIAJA EN EL TIEMPO",
        "voice_text": "[excited] ¡¡Mira qué locura!! Tus invitados abren el enlace en su celular, entran a la cabina trescientos sesenta grados del DeLorean, ¡tocan la pantalla para acelerar hasta ochenta y ocho millas por hora y saltan a través del tiempo con uno punto veintiún gigawatts!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (255, 90, 0),
        "promo_badge": "SALUDO HD + PASE VIP",
        "bottom_pill": "CIRCUITOS DEL TIEMPO + PLACA VIP DESCARGABLE",
        "voice_text": "[enthusiastic] ¡Al aterrizar en la fiesta ven mi cuadro de saludo en video de alta definición, los Circuitos del Tiempo, el radar con Google Maps y Waze, y descargan su Placa California V I P con confirmación a tu WhatsApp!",
    },
    {
        "type": "website",
        "accent_rgb": (255, 190, 0),
        "promo_badge": "COMBO 2 EN 1: SOLO $150 MXN",
        "bottom_pill": "CÓMPRALA POR $150 EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡No dejes la fiesta en el pasado con imágenes estáticas! Entra ahora mismo a dreamcrafters punto lat y llévate el combo completo de Volver al Futuro con cabina interactiva y video saludo por solo ciento cincuenta pesos.",
    },
    {
        "type": "cta",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "SOLO $150 MXN · ENTREGA INMEDIATA",
        "bottom_pill": "ACTIVA TU SALTO EN DREAMCRAFTERS.LAT",
        "voice_text": "[excited] ¡¡Sorprende a todos en el grupo de WhatsApp!! Pídela hoy mismo en dreamcrafters punto lat. ¡¡Nos vemos en el futuro!!",
    },
]

SCENES_AFILIADOS_20_MARTY = [
    {
        "type": "hook",
        "accent_rgb": (255, 190, 0),
        "promo_badge": "GANA 20% EN EFECTIVO",
        "bottom_pill": "¡TE PAGAMOS A TI EN VEZ DE A LAS REDES!",
        "voice_text": "[excited] ¡¡Oye, viajero del tiempo!! ¡Soy Marty McFly! [enthusiastic] Escucha esto: ¿¡y si en lugar de pagarle publicidad a las redes sociales, te pagamos ese dinero directamente a tu cuenta bancaria!?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "INVITACIONES QUE SE JUEGAN",
        "bottom_pill": "LA MANDAS AL GRUPO Y TODAS QUIEREN UNA",
        "voice_text": "[excited] ¡En DreamCrafters creamos invitaciones que son videojuegos reales en el celular, como conducir el DeLorean a ochenta y ocho millas por hora! Cuando una mamá la manda al grupo de WhatsApp, ¡todas las demás quieren una igual para su fiesta!",
    },
    {
        "type": "unlocked",
        "accent_rgb": (56, 255, 98),
        "promo_badge": "20% DIRECTO A TU CLABE",
        "bottom_pill": "COMISIÓN DIRECTA VÍA SPEI SIN PREGUNTAS",
        "voice_text": "[enthusiastic] ¡Por cada invitación que se compre desde tu enlace personal, te depositamos el veinte por ciento de comisión directa vía transferencia SPEI a tu cuenta, sin puntos, sin preguntas y sin letras chiquitas!",
    },
    {
        "type": "website",
        "accent_rgb": (255, 190, 0),
        "promo_badge": "ALTA GRATIS EN 30 SEGUNDOS",
        "bottom_pill": "DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡Solo entra a dreamcrafters punto lat diagonal socios, registra tu nombre y tu cuenta CLABE, y genera tu link único de afiliado completamente gratis en treinta segundos!",
    },
    {
        "type": "cta",
        "accent_rgb": (0, 229, 255),
        "promo_badge": "PROGRAMA DE SOCIOS 20%",
        "bottom_pill": "ACTIVA TU LINK EN DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "[excited] ¡¡Si estás en grupos de mamás del cole o trabajas en fiestas infantiles, entra ya a dreamcrafters punto lat diagonal socios y haz que tu bolsillo viaje al futuro!!",
    },
]


def synthesize_elevenlabs_marty_scenes(scenes, output_wav_path, ffmpeg_path="ffmpeg"):
    """Sintetiza cada escena con ElevenLabs `eleven_v4` usando el clon oficial de Marty McFly (`t1lByQjoc2iRlnuSXgYB`)."""
    cache_dir = os.path.join(DC_CHAR_06_DIR, "elevenlabs_v4_comm_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.18 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.45 * sr), dtype=np.int16)
    eq_filter = "highpass=f=80,equalizer=f=3200:width_type=o:width=1.4:g=2.5,loudnorm=I=-13.5:TP=-1.0:LRA=7"

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"el_v4_marty|{MARTY_VOICE_ID}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"bttf_v4_marty_sc_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav) or os.path.getsize(cached_wav) < 1000:
            print(f"  [ElevenLabs v4 Marty] Generando Escena {idx+1}: {v_text[:68]}...")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{MARTY_VOICE_ID}?output_format=mp3_44100_128"
            payload = {
                "text": v_text,
                "model_id": "eleven_v4",
                "voice_settings": {
                    "stability": 0.26,
                    "similarity_boost": 0.92,
                    "style": 0.72,
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
            print(f"  [ElevenLabs Cache Marty] Reusando Escena {idx+1}")

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


class FeatherTalkMartyCommercialEngine:
    """Motor FeatherTalk ONNX (`FeatherTalkMartyEngine`) con máscara elíptica exclusiva de boca (cero cuello roto, cero bocas encimadas)."""

    def __init__(self, voice_wav_path: str, fps: int = 24, ffmpeg_path: str = "ffmpeg"):
        from render_marty_marionette_videos import FeatherTalkMartyEngine

        self.onnx_dir = os.path.join(DC_CHAR_06_DIR, "marty_onnx")
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path
        self.ft_engine = FeatherTalkMartyEngine(self.onnx_dir, voice_wav_path, fps=fps)
        self.rms_24fps = self.ft_engine.rms_24fps
        self.total_frames = self.ft_engine.total_frames

    def synthesize_char_rgba(self, frame_idx: int) -> tuple[Image.Image, float]:
        _, marty_rgba, _ = self.ft_engine.synthesize_frame(frame_idx, force_silent=False)
        return marty_rgba, 0.0


class BttfCommercialRenderer:
    def __init__(self, ft_engine: FeatherTalkMartyCommercialEngine, mode: str = "juego_150"):
        self.ft = ft_engine
        self.mode = mode  # "juego_150" or "afiliados_20"
        self.W = 720
        self.H = 1280

        # Fondo Hill Valley + Huellas de Fuego de Volver al Futuro
        bg_path = os.path.join(BTTF_ASSETS_DIR, "bttf_page_bg_flames.webp")
        raw_bg = load_pil_rgba(bg_path)
        if raw_bg:
            iw, ih = raw_bg.size
            scale_i = max(self.W / float(iw), self.H / float(ih))
            nw, nh = int(iw * scale_i), int(ih * scale_i)
            i_res = raw_bg.resize((nw, nh), Image.Resampling.LANCZOS)
            lx = (nw - self.W) // 2
            ly = (nh - self.H) // 2
            i_crop = i_res.crop((lx, ly, lx + self.W, ly + self.H)).filter(ImageFilter.GaussianBlur(radius=1.8))
            dark_veil = Image.new("RGBA", (self.W, self.H), (6, 8, 20, 118))
            self.stage_bg = Image.alpha_composite(i_crop, dark_veil)
        else:
            self.stage_bg = Image.new("RGBA", (self.W, self.H), (6, 8, 20, 255))

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

        self.gameplay_frames = sorted(glob.glob(os.path.join(BTTF_CAP_DIR, "gameplay", "frame_*.png")))
        self.unlocked_frames = sorted(glob.glob(os.path.join(BTTF_CAP_DIR, "unlocked", "frame_*.png")))

        rng = np.random.RandomState(1985)
        palette_rgb = [(255, 190, 0), (255, 90, 0), (0, 229, 255), (255, 255, 255)]
        self.fire_sparks = []
        for _ in range(65):
            self.fire_sparks.append(
                {
                    "x0": float(rng.uniform(0, self.W)),
                    "y0": float(rng.uniform(0, self.H * 0.90)),
                    "r": float(rng.uniform(1.4, 3.2)),
                    "vy": float(rng.uniform(1.5, 3.8)),
                    "vx": float(rng.uniform(-0.8, 0.8)),
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

    def render_bttf_stage_bg(self, idx):
        canvas = self.stage_bg.copy()
        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        for pt in self.fire_sparks:
            x = (pt["x0"] + idx * pt["vx"] + math.sin(idx * 0.09 + pt["phase"]) * 9.0) % self.W
            y = (pt["y0"] - idx * pt["vy"]) % (self.H * 0.90)
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(idx * 0.16 + pt["phase"]))
            alpha = int(round(235 * tw))
            r = pt["r"]
            od.ellipse((x - r, y - r, x + r, y + r), fill=pt["color"] + (alpha,))

        floor_y = 1095
        od.line([(0, floor_y), (self.W, floor_y)], fill=(255, 190, 0, 215), width=4)
        od.line([(0, floor_y + 4), (self.W, floor_y + 4)], fill=(0, 229, 255, 165), width=2)
        canvas.alpha_composite(ov)
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
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (8, 11, 24, int(235 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (255, 190, 0, int(248 * alpha_u)) if is_complete else (0, 229, 255, int(235 * alpha_u))
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
        text_col = (255, 190, 0, int(255 * alpha_u)) if is_complete else (255, 255, 255, int(255 * alpha_u))
        od.text(
            (bar_x0 + 28, (bar_y0 + bar_y1) // 2),
            display_url,
            font=self.f_pill if is_aff else self.f_nav_url,
            fill=text_col,
            anchor="lm",
        )

        if is_complete and not is_aff:
            go_x0, go_y0, go_x1, go_y1 = bar_x1 - 92, bar_y0 + 18, bar_x1 - 18, bar_y1 - 18
            od.rounded_rectangle((go_x0, go_y0, go_x1, go_y1), radius=14, fill=(255, 190, 0, int(250 * alpha_u)))
            od.text(((go_x0 + go_x1) // 2, (go_y0 + go_y1) // 2), "88 →", font=self.f_nav_label, fill=(10, 14, 26, int(255 * alpha_u)), anchor="mm")

        line1 = "// GANA 20% DE COMISIÓN DIRECTA VÍA SPEI //" if is_aff else "// VOLVER AL FUTURO 88 MPH · COMBO $150 MXN //"
        line2 = "REGISTRA TU CLABE Y COMPARTE EN WHATSAPP" if is_aff else "DELOREAN 360° + SALUDO DE MARTY + PLACA VIP"
        od.text((self.W // 2, by1 - 68), line1, font=self.f_nav_hint, fill=(255, 190, 0, int(250 * alpha_u)), anchor="mm")
        od.text((self.W // 2, by1 - 32), line2, font=self.f_url, fill=(0, 229, 255, int(245 * alpha_u)), anchor="mm")

        out.alpha_composite(ov)
        return out

    def render_logo_outro_frame(self, outro_prog, idx=0):
        canvas = self.render_bttf_stage_bg(idx)
        dark_overlay = Image.new("RGBA", (self.W, self.H), (6, 8, 20, int(214 * min(1.0, outro_prog * 1.8))))
        canvas = Image.alpha_composite(canvas, dark_overlay)

        halo_alpha = int(165 * min(1.0, outro_prog * 2.2))
        if halo_alpha > 5:
            halo = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            hd = ImageDraw.Draw(halo)
            r_halo = int(185 + 45 * math.sin(outro_prog * math.pi * 2.0))
            cx, cy = self.W // 2, self.H // 2 - 55
            hd.ellipse((cx - r_halo, cy - r_halo, cx + r_halo, cy + r_halo), fill=(0, 229, 255, halo_alpha // 3))
            hd.ellipse((cx - r_halo // 2, cy - r_halo // 2, cx + r_halo // 2, cy + r_halo // 2), fill=(255, 190, 0, halo_alpha // 4))
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
            sub_txt = "PROGRAMA DE SOCIOS · GANA 20% VÍA SPEI" if is_aff else "VOLVER AL FUTURO 88 MPH · COMBO $150 MXN"
            tod.text(
                (self.W // 2, self.H // 2 + 236),
                sub_txt,
                font=self.f_intro_sub,
                fill=(255, 190, 0, int(250 * txt_alpha)),
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
            tod.text((self.W // 2, pill_y0 + 64), pill_bot, font=self.f_url, fill=(255, 190, 0, int(255 * txt_alpha)), anchor="mm")
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
            # Usar únicamente los cuadros finales estacionarios (280..final) en ping-pong suave para que no haya brinco de scroll
            tail_start = min(len(self.unlocked_frames) - 1, 282)
            tail_seq = list(range(tail_start, len(self.unlocked_frames)))
            if len(tail_seq) > 2:
                tail_pp = tail_seq + tail_seq[-2:0:-1]
                f_idx = tail_pp[local_frame_idx % len(tail_pp)]
            else:
                f_idx = len(self.unlocked_frames) - 1
            canvas = Image.open(self.unlocked_frames[f_idx]).convert("RGBA")
            canvas = self._overlay_typing_browser_box(canvas, t_in_sc, sc_dur)
            rgb = np.array(canvas.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # ESCENAS HOOK / CTA -> Marty McFly con Lip-Sync FeatherTalk + HUD 1.21 GW
        accent = sc["accent_rgb"]
        canvas = self.render_bttf_stage_bg(idx)

        char_rgba, glitch_lvl = self.ft.synthesize_char_rgba(idx)
        canvas.alpha_composite(char_rgba, (0, 20))

        canvas = apply_cctv_and_glitch_fx(
            canvas,
            frame_idx=idx,
            glitch_level=glitch_lvl,
            accent_rgb=accent,
            cam_id="OUTATIME // MARTY-1985",
            intensity=0.42,
        )

        grad = Image.new("RGBA", (self.W, 240), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for gy in range(240):
            alpha_g = int(224 * ((gy / 240.0) ** 1.5))
            gd.line([(0, gy), (self.W, gy)], fill=(6, 9, 20, alpha_g))
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
            outline=(255, 190, 0, 240),
            width=2,
        )
        cd.text(
            ((badge_x0 + badge_x1) // 2, (badge_y0 + badge_y1) // 2),
            sc.get("promo_badge", "PROMO $150 MXN"),
            font=self.f_badge,
            fill=(255, 190, 0),
            anchor="mm",
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


def mix_bttf_commercial_audio_with_sfx(voice_wav_path, bgm_path, gameplay_start_sec, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Mezcla la narración de Marty McFly con el tema oficial de Volver al Futuro (`bttf_theme.mp3`)
    y los efectos reales del DeLorean (`sfx_accelerate_88_timetravel.mp3` + `sfx_flux_sparks.mp3` + `sfx_sonic_boom.mp3`).
    """
    accel_mp3 = os.path.join(BTTF_SFX_DIR, "sfx_accelerate_88_timetravel.mp3")
    sparks_mp3 = os.path.join(BTTF_SFX_DIR, "sfx_flux_sparks.mp3")
    boom_mp3 = os.path.join(BTTF_SFX_DIR, "sfx_sonic_boom.mp3")

    accel_delay_ms = int(round((gameplay_start_sec + 16 / 24.0) * 1000))
    sparks_delay_ms = int(round((gameplay_start_sec + 46 / 24.0) * 1000))
    boom_delay_ms = int(round((gameplay_start_sec + 84 / 24.0) * 1000))

    inputs = [
        "-i", voice_wav_path,
        "-i", bgm_path,
        "-i", accel_mp3,
        "-i", sparks_mp3,
        "-i", boom_mp3,
    ]

    fc_parts = [
        "[0:a]volume=1.08[v]",
        "[1:a]volume=0.16,aloop=loop=-1:size=2e+09[b]",
        f"[2:a]volume=0.36,adelay={accel_delay_ms}|{accel_delay_ms}[ac]",
        f"[3:a]volume=0.38,adelay={sparks_delay_ms}|{sparks_delay_ms}[sp]",
        f"[4:a]volume=0.48,adelay={boom_delay_ms}|{boom_delay_ms}[bm]",
        "[v][b][ac][sp][bm]amix=inputs=5:duration=first:dropout_transition=2,alimiter=limit=0.96[out]",
    ]

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


def render_single_bttf_commercial(variant_id, mode, scenes_template, out_filename):
    ffmpeg_path = resolve_ffmpeg_path()
    out_dir = os.path.join(REPO_ROOT, "out", "bttf_commercials")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    clean_wav = os.path.join(out_dir, f"voice_{variant_id}.wav")
    print(f"\n=======================================================")
    print(f"Cocinando Comercial Volver al Futuro: {variant_id} ({mode})")
    print(f"=======================================================")

    scenes = synthesize_elevenlabs_marty_scenes(
        scenes_template,
        output_wav_path=clean_wav,
        ffmpeg_path=ffmpeg_path,
    )

    fps = 24
    ft_engine = FeatherTalkMartyCommercialEngine(clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)
    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} cuadros ({total_frames/fps:.1f}s) en HD 720x1280...")

    renderer = BttfCommercialRenderer(ft_engine, mode=mode)
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
    bgm_path = os.path.join(BTTF_AUDIO_DIR, "bttf_theme.mp3")
    mixed_wav = os.path.join(out_dir, f"mixed_{variant_id}.wav")
    mix_bttf_commercial_audio_with_sfx(clean_wav, bgm_path, gameplay_start, mixed_wav, ffmpeg_path=ffmpeg_path)

    final_mp4 = os.path.join(out_dir, out_filename)
    subprocess.run(
        [
            ffmpeg_path, "-y",
            "-i", temp_video,
            "-i", mixed_wav,
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
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

    art_copy = os.path.join(ARTIFACT_DIR, out_filename)
    shutil.copyfile(final_mp4, art_copy)
    promos_dir = os.path.join(BTTF_ASSETS_DIR, "promos")
    os.makedirs(promos_dir, exist_ok=True)
    shutil.copyfile(final_mp4, os.path.join(promos_dir, out_filename))

    videos_queue_dir = os.path.join(REPO_ROOT, "videos")
    os.makedirs(videos_queue_dir, exist_ok=True)
    queue_name = "07_volver_al_futuro_afiliados_20.mp4" if mode == "afiliados_20" else "06_volver_al_futuro_juego_150.mp4"
    shutil.copyfile(final_mp4, os.path.join(videos_queue_dir, queue_name))

    web_promos_dir = os.path.join(INV_DIR, "promos")
    os.makedirs(web_promos_dir, exist_ok=True)
    hd_name = "promo_afiliados_hd.mp4" if mode == "afiliados_20" else "promo_invitacion_hd.mp4"
    lite_name = "promo_afiliados_lite.mp4" if mode == "afiliados_20" else "promo_invitacion_lite.mp4"
    shutil.copyfile(final_mp4, os.path.join(web_promos_dir, hd_name))
    subprocess.run(
        [
            ffmpeg_path, "-y",
            "-i", final_mp4,
            "-c:v", "libx264", "-preset", "fast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            os.path.join(web_promos_dir, lite_name),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    sz_mb = os.path.getsize(final_mp4) / (1024.0 * 1024.0)
    print(f"  -> Listo: {final_mp4} ({sz_mb:.2f} MB)")
    print(f"  -> Sincronizado en videos/{queue_name} y promos/{hd_name} + {lite_name}")
    print(f"  -> Copiado a Artifact: {art_copy}")


def main():
    if "--recapture" in sys.argv or not os.path.exists(os.path.join(BTTF_CAP_DIR, "gameplay", "frame_0100.png")):
        from capture_real_bttf_mobile import capture_all
        capture_all()

    variants = [
        (
            "juego_150_marty",
            "juego_150",
            SCENES_JUEGO_150_MARTY,
            "video_bttf_promo_invitacion_150.mp4",
        ),
        (
            "afiliados_20_marty",
            "afiliados_20",
            SCENES_AFILIADOS_20_MARTY,
            "video_bttf_afiliados_20.mp4",
        ),
    ]

    for v in variants:
        render_single_bttf_commercial(*v)


if __name__ == "__main__":
    main()
