# -*- coding: utf-8 -*-
"""
render_mario_birthday_greeting.py — Generador de Video Personalizado de Mario Felicitando al Cumpleañero
========================================================================================================
Arquitectura de 4 Bloques (2 Dinámicos + 2 Fijos Cacheables) para no saturar el Runner:
  - Bloque 1 [DINÁMICO]: Saludo al cumpleañero por su nombre y cuántos años cumple.
  - Bloque 2 [FIJO CACHEADO]: Invitación entusiasta a todos sus amigos.
  - Bloque 3 [DINÁMICO]: Día y hora de la fiesta con voz.
  - Bloque 4 [FIJO CACHEADO EN VOZ + DIRECCIÓN DINÁMICA EN PANTALLA]:
      Mario dice: "¡La fiesta es en la dirección que ves aquí en pantalla! ¡Confirma tu asistencia y allá nos vemos!"
      mientras aparece la Tarjeta Holográfica con el Salón, Dirección, Fecha y Nombre del festejado.
"""

import os
import sys
import math
import time
import wave
import shutil
import hashlib
import argparse
import subprocess
import requests
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from render_dreamcrafters_video import (
    REPO_ROOT,
    CHAR_02_DIR,
    FEATHERTALK_ONNX_DIR,
    WEB_ASSETS_DIR,
    REF_WAV,
    resolve_ffmpeg_path,
    synthesize_cloned_scenes_local,
    mix_voice_with_bgm,
    _trim_silence_pcm,
    FeatherTalkMarioEngine,
    MarioGalaxyCommercialRenderer,
    get_font,
)


def synthesize_elevenlabs_mario_scenes(scenes, api_key, voice_id, output_wav_path, ffmpeg_path="ffmpeg"):
    """
    Sintetiza los bloques con la voz clonada de Mario en ElevenLabs (`eleven_multilingual_v2`).
    SOLO se invoca cuando el usuario autoriza explícitamente usar la llave restringida.
    Los bloques fijos (Bloque 2 y Bloque 4) quedan guardados en caché para no gastar créditos de más.
    """
    cache_dir = os.path.join(CHAR_02_DIR, "out", "elevenlabs_mario_cache")
    os.makedirs(cache_dir, exist_ok=True)

    sr = 24000
    pause_samples = np.zeros(int(0.18 * sr), dtype=np.int16)
    tail_samples = np.zeros(int(0.35 * sr), dtype=np.int16)
    eq_filter = "highpass=f=80,equalizer=f=3400:width_type=o:width=1.4:g=2.8,loudnorm=I=-13.0:TP=-0.8:LRA=7"

    all_pcm = []
    cur_time = 0.0
    updated_scenes = []

    for idx, sc in enumerate(scenes):
        v_text = sc["voice_text"].strip()
        h_key = hashlib.sha256(f"el_mario_v4|{voice_id}|{v_text}".encode("utf-8")).hexdigest()[:16]
        cached_wav = os.path.join(cache_dir, f"el_mario_v4_blk_{idx+1}_{h_key}.wav")

        if not os.path.exists(cached_wav) or os.path.getsize(cached_wav) < 1000:
            print(f"  [ElevenLabs v4 Mario Clone] Generando Bloque {idx+1}: {v_text}")
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
                raise RuntimeError(f"Error ElevenLabs ({resp.status_code}): {resp.text}")

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
            print(f"  [ElevenLabs Mario Cache] Reusando Bloque {idx+1} desde caché local (0 chars gastados)")

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


def build_birthday_scenes(name_display, name_voice, age_num, age_voice, date_voice, date_display, time_display, venue_name, venue_address):
    return [
        {
            "type": "bday_greet",
            "is_fixed": False,
            "accent_rgb": (250, 204, 21),
            "top_badge": f"¡FELIZ CUMPLE #{age_num}!",
            "voice_text": f"¡Wahoo! ¡Hola {name_voice}! ¡Soy yo, Mario! ¡Muchas felicidades campeón, ya cumples {age_voice}!",
            "card_kicker": "FELICITACIÓN ESPECIAL DE SUPER MARIO",
            "card_title": f"¡FELICIDADES {name_display.upper()}!",
            "card_sub": f"¡CUMPLE {age_num} AÑOS!",
            "card_detail": "MISION DE CUMPLEANOS ACTIVADA",
        },
        {
            "type": "bday_friends",
            "is_fixed": True,
            "accent_rgb": (56, 189, 248),
            "top_badge": "INVITACIÓN OFICIAL",
            "voice_text": "¡Oigan amigos! Prepárense para saltar por la galaxia, porque están todos invitados a su gran fiesta de Super Mario Galaxy.",
            "card_kicker": "LLAMADO A TODA LA TRIPULACIÓN",
            "card_title": "¡AMIGOS, ESTÁN INVITADOS!",
            "card_sub": "AVENTURA DE SUPER MARIO GALAXY",
            "card_detail": "JUEGOS · PASTEL · SORPRESAS ESPACIALES",
        },
        {
            "type": "bday_date",
            "is_fixed": False,
            "accent_rgb": (250, 204, 21),
            "top_badge": "FECHA CONFIRMADA",
            "voice_text": f"¡Anoten bien la fecha! La fiesta será el día {date_voice}.",
            "card_kicker": "FECHA Y HORA DE DESPEGUE",
            "card_title": date_display.upper(),
            "card_sub": f"HORA DE CITA: {time_display.upper()}",
            "card_detail": "¡PUNTUALES PARA INICIAR LA MISIÓN!",
        },
        {
            "type": "bday_address",
            "is_fixed": True,
            "accent_rgb": (56, 189, 248),
            "top_badge": "UBICACIÓN EN PANTALLA",
            "voice_text": "¡La fiesta es en la dirección que ves aquí en pantalla! ¡Confirma tu asistencia en la invitación y allá nos vemos! ¡Let's-a go!",
            "venue_name": venue_name,
            "venue_address": venue_address,
            "date_display": date_display.upper(),
            "time_display": time_display.upper(),
            "celebrant_label": f"¡TE ESPERA {name_display.upper()} ({age_num} AÑOS)!",
        },
    ]


class MarioBirthdayGreetingRenderer(MarioGalaxyCommercialRenderer):
    def __init__(self, ft_engine):
        super().__init__(ft_engine)
        self.f_kicker = get_font(17, bold=True, mono=True)
        self.f_big_title = get_font(34, bold=True)
        self.f_med_title = get_font(26, bold=True)
        self.f_sub = get_font(22, bold=True)
        self.f_addr_title = get_font(28, bold=True)
        self.f_addr_line = get_font(21, bold=True)
        self.f_addr_meta = get_font(18, bold=True, mono=True)

    def _draw_frosted_panel(self, canvas, box, radius, tint_rgba, border_rgba, border_w=3):
        bx0, by0, bx1, by1 = box
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=16))
        glass = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass.paste(crop_region, (0, 0))
        tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), tint_rgba)
        glass = Image.alpha_composite(glass, tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=radius, fill=255)

        out = canvas.copy()
        out.paste(glass, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rounded_rectangle(box, radius=radius, outline=border_rgba, width=border_w)
        out.alpha_composite(ov)
        return out

    def _wrap_text(self, text, font, max_w, draw_obj):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            bbox = draw_obj.textbbox((0, 0), test, font=font)
            if (bbox[2] - bbox[0]) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def render_birthday_frame(self, idx, fps, active_sc, t_in_sc):
        accent = active_sc["accent_rgb"]
        sc_type = active_sc["type"]

        # 1. Escenario galáctico animado de Super Mario Galaxy
        canvas = self.render_cosmic_galaxy_bg(idx)

        # 2. Mario 3D con lip-sync FeatherTalk ONNX
        mario_rgba, _ = self.ft.synthesize_mario_rgba(idx)

        # En el bloque 4 (dirección en pantalla), subimos ligeramente a Mario para que la tarjeta de dirección luzca enorme y clara abajo
        if sc_type == "bday_address":
            self._draw_floor_contact_shadow(canvas, self.W // 2, 1020, rx=160, ry=20, alpha=145)
            canvas.alpha_composite(mario_rgba, (0, -95))
        else:
            self._draw_floor_contact_shadow(canvas, self.W // 2, 1110, rx=175, ry=24, alpha=165)
            canvas.alpha_composite(mario_rgba, (0, -18))

        # 3. Header superior (DreamCrafters + Insignia de estado)
        cd = ImageDraw.Draw(canvas)
        if self.d_icon_header:
            canvas.alpha_composite(self.d_icon_header, (28, 26))
        if self.logo_text:
            lw, lh = self.logo_text.size
            th = 32
            tw = int(lw * (th / float(lh)))
            canvas.alpha_composite(self.logo_text.resize((tw, th), Image.Resampling.LANCZOS), (92, 38))

        badge_x0, badge_y0, badge_x1, badge_y1 = self.W - 310, 26, self.W - 24, 82
        cd.rounded_rectangle(
            (badge_x0, badge_y0, badge_x1, badge_y1),
            radius=18,
            fill=(10, 15, 28, 238),
            outline=accent + (240,),
            width=2,
        )
        if self.mario_star:
            star_sm = self.mario_star.resize((36, 36), Image.Resampling.LANCZOS)
            canvas.alpha_composite(star_sm, (badge_x0 + 12, badge_y0 + 10))
        cd.text(
            (badge_x0 + 58, (badge_y0 + badge_y1) // 2),
            active_sc.get("top_badge", "MENSAJE DE MARIO"),
            font=self.f_badge,
            fill=accent,
            anchor="lm",
        )

        # Animación suave de entrada de la tarjeta inferior en cada bloque
        enter_u = min(1.0, max(0.0, t_in_sc / 0.28))
        slide_y = int(round((1.0 - enter_u) * 28))

        if sc_type != "bday_address":
            # Tarjeta inferior para Bloques 1, 2 y 3 (Saludo, Amigos, Fecha/Hora)
            bx0, by0, bx1, by1 = 28, 975 + slide_y, self.W - 28, 1236 + slide_y
            canvas = self._draw_frosted_panel(
                canvas,
                (bx0, by0, bx1, by1),
                radius=28,
                tint_rgba=(8, 13, 28, 226),
                border_rgba=accent + (245,),
                border_w=3,
            )
            od = ImageDraw.Draw(canvas)

            # Kicker pill
            od.rounded_rectangle(
                (bx0 + 24, by0 + 18, bx1 - 24, by0 + 54),
                radius=12,
                fill=(16, 26, 52, 230),
                outline=accent + (140,),
                width=1,
            )
            od.text(
                (self.W // 2, by0 + 36),
                active_sc["card_kicker"],
                font=self.f_kicker,
                fill=(185, 225, 255),
                anchor="mm",
            )

            title_font = self.f_big_title if len(active_sc["card_title"]) <= 22 else self.f_med_title
            od.text(
                (self.W // 2, by0 + 102),
                active_sc["card_title"],
                font=title_font,
                fill=(255, 255, 255),
                anchor="mm",
            )
            od.text(
                (self.W // 2, by0 + 154),
                active_sc["card_sub"],
                font=self.f_sub,
                fill=(250, 204, 21),
                anchor="mm",
            )
            od.text(
                (self.W // 2, by0 + 206),
                active_sc["card_detail"],
                font=self.f_kicker,
                fill=(56, 232, 255),
                anchor="mm",
            )
        else:
            # Bloque 4: TARJETA PROTAGONISTA DE DIRECCIÓN EN PANTALLA ("en la dirección que ves en pantalla")
            bx0, by0, bx1, by1 = 24, 835 + slide_y, self.W - 24, 1244 + slide_y
            pulse_border = int(215 + 40 * math.sin(idx * 0.25))
            canvas = self._draw_frosted_panel(
                canvas,
                (bx0, by0, bx1, by1),
                radius=30,
                tint_rgba=(7, 12, 26, 238),
                border_rgba=(250, 204, 21, pulse_border),
                border_w=4,
            )
            od = ImageDraw.Draw(canvas)

            # Encabezado dorado "DIRECCIÓN DE LA FIESTA"
            od.rounded_rectangle(
                (bx0 + 22, by0 + 18, bx1 - 22, by0 + 64),
                radius=14,
                fill=(250, 204, 21, 248),
            )
            od.text(
                (self.W // 2, by0 + 41),
                "COORDENADAS DE LA FIESTA (DIRECCIÓN)",
                font=self.f_kicker,
                fill=(10, 14, 24),
                anchor="mm",
            )

            # Nombre del Salón en grande
            od.text(
                (self.W // 2, by0 + 108),
                active_sc["venue_name"].upper(),
                font=self.f_addr_title,
                fill=(255, 255, 255),
                anchor="mm",
            )

            # Caja interna con la calle y colonia exactas
            addr_box = (bx0 + 22, by0 + 144, bx1 - 22, by0 + 258)
            od.rounded_rectangle(
                addr_box,
                radius=18,
                fill=(14, 22, 44, 245),
                outline=(56, 189, 248, 220),
                width=2,
            )
            lines = self._wrap_text(active_sc["venue_address"], self.f_addr_line, (bx1 - bx0 - 76), od)
            if len(lines) == 1:
                od.text((self.W // 2, (addr_box[1] + addr_box[3]) // 2), lines[0], font=self.f_addr_line, fill=(56, 232, 255), anchor="mm")
            else:
                od.text((self.W // 2, addr_box[1] + 38), lines[0], font=self.f_addr_line, fill=(56, 232, 255), anchor="mm")
                od.text((self.W // 2, addr_box[1] + 76), " ".join(lines[1:]), font=self.f_addr_line, fill=(235, 245, 255), anchor="mm")

            # Fecha y Hora resumidas abajo
            od.text(
                (self.W // 2, by0 + 296),
                f"{active_sc['date_display']}  ·  {active_sc['time_display']}",
                font=self.f_addr_meta,
                fill=(250, 204, 21),
                anchor="mm",
            )

            # Pie con el nombre del festejado
            od.rounded_rectangle(
                (bx0 + 40, by0 + 334, bx1 - 40, by0 + 384),
                radius=14,
                fill=(22, 163, 74, 235),
            )
            od.text(
                (self.W // 2, by0 + 359),
                active_sc["celebrant_label"],
                font=self.f_kicker,
                fill=(255, 255, 255),
                anchor="mm",
            )

        rgb = np.array(canvas.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def main():
    parser = argparse.ArgumentParser(description="Renderiza el video personalizado de Mario felicitando al cumpleañero.")
    parser.add_argument("--name", default="Darío", help="Nombre del cumpleañero para mostrar")
    parser.add_argument("--name-voice", default="Darío", help="Pronunciación fonética del nombre para TTS")
    parser.add_argument("--age", type=int, default=6, help="Edad que cumple")
    parser.add_argument("--age-voice", default="seis años", help="Edad en texto para TTS")
    parser.add_argument("--date-voice", default="sábado veinticuatro de mayo a las cuatro de la tarde", help="Fecha y hora habladas por Mario")
    parser.add_argument("--date-display", default="SÁBADO 24 DE MAYO 2026", help="Fecha en pantalla")
    parser.add_argument("--time-display", default="4:00 PM (16:00 HRS)", help="Hora en pantalla")
    parser.add_argument("--venue-name", default='Salón "Estrella"', help="Nombre del salón o lugar")
    parser.add_argument("--venue-address", default="Av. Galaxia Sur 123, Col. Observatorio, Guadalajara", help="Dirección completa en pantalla")
    parser.add_argument(
        "--output",
        default=r"C:\Users\rufin\.gemini\antigravity\playground\dreamcrafters\public\invitacionmario\saludo_mario_dario.mp4",
    )
    parser.add_argument("--elevenlabs-key", default="", help="Llave ElevenLabs autorizada por el usuario")
    parser.add_argument("--elevenlabs-voice-id", default="UjVFP9j28dAsNPGkXXOT", help="Voice ID de Mario clonado en ElevenLabs")
    args = parser.parse_args()

    t0 = time.time()
    ffmpeg_path = resolve_ffmpeg_path()
    bgm_rel = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")

    out_dir = os.path.join(REPO_ROOT, "out", "birthday_greetings")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    raw_scenes = build_birthday_scenes(
        name_display=args.name,
        name_voice=args.name_voice,
        age_num=args.age,
        age_voice=args.age_voice,
        date_voice=args.date_voice,
        date_display=args.date_display,
        time_display=args.time_display,
        venue_name=args.venue_name,
        venue_address=args.venue_address,
    )

    clean_wav = os.path.join(out_dir, f"voice_bday_{args.name.lower()}.wav")
    print(f"[1/3] Sintetizando bloques de voz (2 dinámicos + 2 fijos en caché) para {args.name} ({args.age} años)...")
    if args.elevenlabs_key:
        scenes = synthesize_elevenlabs_mario_scenes(
            raw_scenes,
            api_key=args.elevenlabs_key,
            voice_id=args.elevenlabs_voice_id,
            output_wav_path=clean_wav,
            ffmpeg_path=ffmpeg_path,
        )
    else:
        scenes = synthesize_cloned_scenes_local(raw_scenes, REF_WAV, clean_wav, ffmpeg_path=ffmpeg_path)

    fps = 24
    print("[2/3] Ejecutando FeatherTalk ONNX 144x144 (Lip-Sync de Mario 3D)...")
    ft_engine = FeatherTalkMarioEngine(FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path)
    total_frames = ft_engine.total_frames

    print(f"[3/3] Componiendo {total_frames} cuadros ({total_frames / fps:.1f}s) con Tarjeta de Dirección Galáctica...")
    renderer = MarioBirthdayGreetingRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_bday_visual.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(temp_video, fourcc, fps, (720, 1280))

    for i in range(total_frames):
        t_sec = i / float(fps)
        active_sc = scenes[-1]
        for sc in scenes:
            if sc["start"] <= t_sec <= sc["end"]:
                active_sc = sc
                break
        t_in_sc = max(0.0, t_sec - active_sc["start"])
        bgr = renderer.render_birthday_frame(i, fps, active_sc, t_in_sc)
        vw.write(bgr)

    vw.release()

    mixed_wav = os.path.join(out_dir, f"mixed_bday_{args.name.lower()}.wav")
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

    # También copiar a invitacion-mario en astral-curie por si se sirve desde Vite
    vite_public_copy = r"c:\Users\rufin\.gemini\antigravity\playground\astral-curie\invitacion-mario\public\invitacionmario\saludo_mario_dario.mp4"
    if os.path.exists(os.path.dirname(vite_public_copy)):
        shutil.copyfile(args.output, vite_public_copy)

    elapsed = time.time() - t0
    print(f"[OK] Video de felicitacion personalizado listo en {elapsed:.1f}s -> {args.output}")


if __name__ == "__main__":
    main()
