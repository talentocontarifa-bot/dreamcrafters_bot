# -*- coding: utf-8 -*-
"""
render_mario_referidos_video.py — Comercial Oficial de Mario 3D (FeatherTalk ONNX)
para el Programa de Socios / Referidos del 20% ("¿Y si en vez de pagar publicidad, te pagamos a ti?")
====================================================================================================
Reutiliza el motor 3D de Mario (`FeatherTalkMarioEngine` + `MarioGalaxyCommercialRenderer`)
con barra de navegador tipeando `dreamcrafters.lat/socios` y cierre animado.
"""

import os
import argparse
import shutil
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from render_dreamcrafters_video import (
    REPO_ROOT,
    CHAR_02_DIR,
    FEATHERTALK_ONNX_DIR,
    WEB_ASSETS_DIR,
    REF_WAV,
    REAL_CAP_DIR,
    FeatherTalkMarioEngine,
    MarioGalaxyCommercialRenderer,
    resolve_ffmpeg_path,
    mix_voice_with_bgm,
    synthesize_cloned_scenes_local,
    synthesize_elevenlabs_v4_scenes,
)

SCENES_MARIO_REFERIDOS = [
    {
        "type": "hook",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "GANA 20% EN EFECTIVO",
        "bottom_pill": "¡TE PAGAMOS A TI EN VEZ DE A LAS REDES!",
        "voice_text": "¡Hola amigos! Soy yo, Mario. Oigan, ¿y si en vez de pagarle publicidad a las redes sociales, te pagamos ese dinero directamente a ti?",
    },
    {
        "type": "gameplay",
        "accent_rgb": (56, 189, 248),
        "promo_badge": "INVITACIONES QUE SE JUEGAN",
        "bottom_pill": "LA MANDAS AL GRUPO Y TODAS QUIEREN UNA",
        "voice_text": "En DreamCrafters hacemos invitaciones que son videojuegos reales en el celular. Cuando una mamá la manda al grupo de WhatsApp del salón, todas las demás quieren una igual para su fiesta.",
    },
    {
        "type": "unlocked",
        "accent_rgb": (74, 222, 128),
        "promo_badge": "20% DIRECTO A TU CLABE",
        "bottom_pill": "COMISIÓN DIRECTA SIN PREGUNTAS",
        "voice_text": "Por cada invitación que se compre desde tu enlace personal, te depositamos el veinte por ciento de comisión directa a tu cuenta bancaria, sin preguntas y sin letras chiquitas.",
    },
    {
        "type": "website",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "ALTA GRATIS EN 30 SEGUNDOS",
        "bottom_pill": "DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "Solo entra a dreamcrafters punto lat diagonal socios, registra tu nombre y la cuenta donde quieres recibir tus pagos, y genera tu link único en treinta segundos.",
    },
    {
        "type": "cta",
        "accent_rgb": (250, 204, 21),
        "promo_badge": "PROGRAMA DE SOCIOS 20%",
        "bottom_pill": "ACTIVA TU LINK EN DREAMCRAFTERS.LAT/SOCIOS",
        "voice_text": "¡Si estás en los grupos de mamás del cole o trabajas en fiestas infantiles, entra ya a dreamcrafters punto lat diagonal socios y gana con cada fiesta! ¡Allá nos vemos!",
    },
]


class MarioReferidosCommercialRenderer(MarioGalaxyCommercialRenderer):
    """
    Extiende el renderizador galáctico de Mario para mostrar la URL `dreamcrafters.lat/socios`
    y los textos del Programa de Referidos del 20% en las tarjetas de navegador y cierre.
    """

    def _overlay_typing_browser_box(self, canvas: Image.Image, t_in_sc: float, sc_dur: float) -> Image.Image:
        show_until = min(4.2, sc_dur * 0.65)
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

        target_text = "dreamcrafters.lat/socios"
        type_prog = min(1.0, max(0.0, (t_in_sc - 0.18) / 1.95))
        n_chars = int(round(type_prog * len(target_text)))
        typed_str = target_text[:n_chars]
        is_complete = n_chars >= len(target_text)

        bx0, by0, bx1, by1 = 24, 455, self.W - 24, 775
        crop_region = canvas.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(radius=18))

        glass_card = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
        glass_card.paste(crop_region, (0, 0))
        dark_tint = Image.new("RGBA", (bx1 - bx0, by1 - by0), (8, 14, 28, int(228 * alpha_u)))
        glass_card = Image.alpha_composite(glass_card, dark_tint)

        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, bx1 - bx0 - 1, by1 - by0 - 1), radius=32, fill=int(255 * alpha_u))

        out = canvas.copy()
        out.paste(glass_card, (bx0, by0), mask)

        ov = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        border_col = (74, 222, 128, int(245 * alpha_u)) if is_complete else (250, 204, 21, int(235 * alpha_u))
        od.rounded_rectangle((bx0, by0, bx1, by1), radius=32, outline=border_col, width=3)

        od.text(
            (self.W // 2, by0 + 42),
            "GENERA TU LINK EN 30 SEGUNDOS:",
            font=self.f_nav_label,
            fill=(190, 215, 240, int(245 * alpha_u)),
            anchor="mm",
        )

        bar_x0, bar_y0, bar_x1, bar_y1 = bx0 + 22, by0 + 78, bx1 - 22, by0 + 178
        od.rounded_rectangle(
            (bar_x0, bar_y0, bar_x1, bar_y1),
            radius=22,
            fill=(5, 9, 18, int(248 * alpha_u)),
            outline=border_col,
            width=2,
        )

        cursor_on = (not is_complete) or (int(t_in_sc * 6) % 2 == 0)
        display_url = typed_str + ("|" if cursor_on and not is_complete else "")
        text_col = (74, 222, 128, int(255 * alpha_u)) if is_complete else (250, 246, 238, int(255 * alpha_u))
        od.text(
            (bar_x0 + 28, (bar_y0 + bar_y1) // 2),
            display_url,
            font=self.f_pill,
            fill=text_col,
            anchor="lm",
        )

        od.text(
            (self.W // 2, by1 - 62),
            "★ GANA 20% DE COMISIÓN DIRECTA VÍA SPEI ★",
            font=self.f_nav_hint,
            fill=(250, 204, 21, int(250 * alpha_u)),
            anchor="mm",
        )
        od.text(
            (self.W // 2, by1 - 28),
            "SIN PREGUNTAS · REGISTRA TU CLABE Y COMPARTE",
            font=self.f_url,
            fill=(74, 222, 128, int(245 * alpha_u)),
            anchor="mm",
        )

        out.alpha_composite(ov)
        return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=os.path.join(REPO_ROOT, "out", "video_mario_referidos_20.mp4"),
    )
    parser.add_argument(
        "--elevenlabs-key",
        default=os.environ.get(
            "ELEVENLABS_API_KEY_RESTRICTED_CLONING",
            "sk_1a6f82b58f6110efdb8b0cce0b470505b9630bbdf8b69795",
        ),
        help="Llave ElevenLabs con voz clonada de Mario por defecto",
    )
    parser.add_argument(
        "--elevenlabs-voice-id",
        default="UjVFP9j28dAsNPGkXXOT",
        help="Voice ID de Mario clonado en ElevenLabs",
    )
    parser.add_argument(
        "--enqueue",
        action="store_true",
        help="Copia el video terminado a dreamcrafter/videos/03_mario_referidos_20.mp4",
    )
    args = parser.parse_args()

    if not os.path.exists(os.path.join(REAL_CAP_DIR, "d_icon_hd.png")):
        from capture_real_mario_mobile import capture_all
        capture_all()

    ffmpeg_path = resolve_ffmpeg_path()
    bgm_rel = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    clean_wav = os.path.join(out_dir, "mario_referidos_20_voice.wav")

    print("Sintetizando voz de Mario para Comercial del Programa de Referidos (20%)...")
    if args.elevenlabs_key:
        scenes = synthesize_elevenlabs_v4_scenes(
            SCENES_MARIO_REFERIDOS,
            api_key=args.elevenlabs_key,
            voice_id=args.elevenlabs_voice_id,
            output_wav_path=clean_wav,
            ffmpeg_path=ffmpeg_path,
        )
    else:
        scenes = synthesize_cloned_scenes_local(
            SCENES_MARIO_REFERIDOS,
            REF_WAV,
            clean_wav,
            ffmpeg_path=ffmpeg_path,
        )

    fps = 24
    ft_engine = FeatherTalkMarioEngine(
        FEATHERTALK_ONNX_DIR, clean_wav, fps=fps, ffmpeg_path=ffmpeg_path
    )
    total_frames = ft_engine.total_frames
    print(f"Renderizando {total_frames} frames ({total_frames/fps:.1f}s) del comercial de Referidos 20%...")

    renderer = MarioReferidosCommercialRenderer(ft_engine)
    temp_video = os.path.join(out_dir, "temp_visual_mario_referidos.mp4")
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

        bgr = renderer.render_frame(
            i, total_frames, fps, {"scene": active_sc, "progress": prog}
        )
        vw.write(bgr)

    vw.release()

    mixed_wav = os.path.join(out_dir, "mario_referidos_20_mixed.wav")
    final_audio = mix_voice_with_bgm(
        clean_wav, bgm_rel, mixed_wav, bgm_vol=0.12, ffmpeg_path=ffmpeg_path
    )

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

    if args.enqueue:
        videos_dir = os.path.join(REPO_ROOT, "videos")
        os.makedirs(videos_dir, exist_ok=True)
        dest = os.path.join(videos_dir, "03_mario_referidos_20.mp4")
        shutil.copyfile(args.output, dest)
        print(f"Copiado a bandeja de publicación: {dest}")

    print(f"Comercial de Referidos 20% con Mario listo en: {args.output}")


if __name__ == "__main__":
    main()
