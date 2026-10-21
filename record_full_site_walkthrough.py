# -*- coding: utf-8 -*-
"""
record_full_site_walkthrough.py — Grabación completa del recorrido por el sitio + integración del Video de Mario
=================================================================================================================
Genera un video MP4 vertical (720x1280 @ 24 FPS) con audio real que muestra de principio a fin:
  1. Sitio principal (`dreamcrafters.lat`) -> Tarjeta Super Mario Galaxy ($100 MXN) con video incluido.
  2. Configuración post-pago (`/gracias-mario`) -> Llenado de datos de Darío + pantalla de entrega con descarga MP4.
  3. Invitación recibida (`/invitacionmario/index.html`) -> Minijuego espacial hasta 50/50 PTS con confeti.
  4. Desbloqueo de la invitación -> Panel `TRANSMISIÓN DE MARIO` -> Clic en Play y reproducción en vivo (con voz y lip-sync)
     de los 4 bloques del saludo personalizado dentro de la página de la invitación.
  5. Recorrido final por la invitación desbloqueada (Cuenta regresiva, Mapa GPS, Yoshi y Pase de Abordaje WhatsApp).
"""

import os
import io
import math
import time
import shutil
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
SALUDO_MP4 = r"C:\Users\rufin\.gemini\antigravity\playground\dreamcrafters\public\invitacionmario\saludo_mario_dario.mp4"
OUT_MP4 = r"C:\Users\rufin\.gemini\antigravity\brain\44c7b598-662f-4ee8-9ce6-c2392451d5e9\recorrido_completo_sitio_y_video.mp4"

FPS = 24
W, H = 720, 1280


def get_font(size, bold=True):
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


FONT_STEP = get_font(20, bold=True)
FONT_SUB = get_font(16, bold=True)


def add_step_banner_and_tap(pil_img, step_title, step_sub, tap_xy=None, tap_prog=0.0):
    canvas = pil_img.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    # Banner flotante superior indicador del paso del recorrido
    bx0, by0, bx1, by1 = 22, 16, W - 22, 92
    od.rounded_rectangle(
        (bx0, by0, bx1, by1),
        radius=18,
        fill=(6, 11, 24, 232),
        outline=(56, 232, 255, 225),
        width=2,
    )
    od.text((W // 2, by0 + 26), step_title, font=FONT_STEP, fill=(250, 204, 21, 255), anchor="mm")
    od.text((W // 2, by0 + 55), step_sub, font=FONT_SUB, fill=(225, 240, 255, 245), anchor="mm")

    if tap_xy and 0.0 < tap_prog < 1.0:
        tx, ty = tap_xy
        r1 = int(18 + 38 * tap_prog)
        a1 = int(240 * (1.0 - tap_prog))
        od.ellipse((tx - r1, ty - r1, tx + r1, ty + r1), outline=(250, 204, 21, a1), width=4)
        od.ellipse((tx - 12, ty - 12, tx + 12, ty + 12), fill=(250, 204, 21, int(210 * (1.0 - tap_prog * 0.5))))

    canvas.alpha_composite(ov)
    return cv2.cvtColor(np.array(canvas.convert("RGB")), cv2.COLOR_RGB2BGR)


def snap_pil(page):
    raw = page.screenshot(type="jpeg", quality=92)
    return Image.open(io.BytesIO(raw)).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)


def main():
    os.makedirs(os.path.dirname(OUT_MP4), exist_ok=True)
    temp_vis = os.path.join(REPO_ROOT, "out", "temp_walkthrough_vis.mp4")
    os.makedirs(os.path.dirname(temp_vis), exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(temp_vis, fourcc, FPS, (W, H))

    # Leer todos los frames de saludo_mario_dario.mp4 para inyectarlos cuadro a cuadro en el reproductor de la página
    saludo_cap = cv2.VideoCapture(SALUDO_MP4)
    saludo_frames_pil = []
    while True:
        ret, frame_bgr = saludo_cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        saludo_frames_pil.append(Image.fromarray(rgb).convert("RGBA"))
    saludo_cap.release()
    print(f"Frames de saludo_mario_dario.mp4 cargados: {len(saludo_frames_pil)} ({len(saludo_frames_pil)/FPS:.1f}s)")

    video_start_frame = 0
    video_end_frame = 0
    total_written = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 693},
            device_scale_factor=2,
        )
        page = context.new_page()

        # =====================================================================
        # PASO 1: LANDING PAGE (`dreamcrafters.lat`) -> TARJETA MARIO GALAXY $100
        # =====================================================================
        print("[1/5] Grabando Paso 1: Landing Page dreamcrafters.lat...")
        page.goto("http://localhost:3000", wait_until="networkidle")
        page.wait_for_timeout(400)

        mario_card_y = page.evaluate(
            """() => {
                const el = document.querySelector('.dc-pane-mario');
                if (!el) return 900;
                const r = el.getBoundingClientRect();
                return Math.max(0, window.scrollY + r.top - 110);
            }"""
        )

        # 5.0 segundos (120 frames): vista del Hero -> scroll suave hacia la tarjeta de Mario $100 -> tap en Comprar
        n_step1 = 120
        for i in range(n_step1):
            u = i / float(n_step1 - 1)
            if u < 0.20:
                sy = 0
            elif u < 0.62:
                su = (u - 0.20) / 0.42
                ease = 1.0 - pow(1.0 - su, 3)
                sy = int(mario_card_y * ease)
            else:
                sy = int(mario_card_y)
            page.evaluate(f"window.scrollTo(0, {sy})")
            img = snap_pil(page)
            tap_xy = (230, 980) if u > 0.80 else None
            tap_p = (u - 0.80) / 0.20 if u > 0.80 else 0.0
            bgr = add_step_banner_and_tap(
                img,
                "PASO 1 · CATÁLOGO EN DREAMCRAFTERS.LAT",
                "Paquete Super Mario Galaxy ($100 MXN) con Video Incluido",
                tap_xy=tap_xy,
                tap_prog=tap_p,
            )
            vw.write(bgr)
            total_written += 1

        # =====================================================================
        # PASO 2: CONFIGURACIÓN POST-PAGO (`/gracias-mario`) + ENTREGA DE VIDEO
        # =====================================================================
        print("[2/5] Grabando Paso 2: Configuración y entrega en /gracias-mario...")
        page.route(
            "**/api/verify-payment*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"authorized":true,"paymentId":"cs_live_demo_2026","customerPhone":"3312345678"}',
            ),
        )
        page.goto("http://localhost:3000/gracias-mario?session_id=cs_live_demo_2026", wait_until="networkidle")
        page.wait_for_timeout(500)

        # Llenar los campos progresivamente durante 3 segundos (72 frames)
        fields_seq = [
            (10, "#mario-names", "DARÍO"),
            (22, "#mario-date", "2026-05-24"),
            (32, "#mario-time", "16:00"),
            (42, "#mario-address", 'Salón "Estrella", Av. Galaxia Sur 123, Guadalajara'),
            (54, "#mario-wa", "3312345678"),
        ]
        for i in range(72):
            for trig_f, sel, val in fields_seq:
                if i == trig_f:
                    try:
                        page.fill(sel, val)
                    except Exception:
                        pass
            if i == 46:
                page.evaluate("window.scrollTo(0, 260)")
            img = snap_pil(page)
            tap_xy = (W // 2, 1110) if i >= 58 else None
            tap_p = (i - 58) / 14.0 if i >= 58 else 0.0
            bgr = add_step_banner_and_tap(
                img,
                "PASO 2 · PERSONALIZACIÓN AL INSTANTE",
                "El cliente ingresa Nombre, Edad, Fecha y Dirección del Salón",
                tap_xy=tap_xy,
                tap_prog=tap_p,
            )
            vw.write(bgr)
            total_written += 1

        # Mostrar la vista de confirmación en /gracias-mario con el link + tarjeta del Video de Mario (.MP4)
        page.evaluate(
            """() => {
                // Simular estado activado sin abrir ventana externa de WhatsApp
                window.open = () => null;
            }"""
        )
        try:
            page.click('button[type="submit"]')
            page.wait_for_timeout(700)
        except Exception:
            pass
        page.evaluate("window.scrollTo(0, 0)")

        for i in range(72):
            img = snap_pil(page)
            tap_xy = (220, 560) if i >= 54 else None
            tap_p = (i - 54) / 18.0 if i >= 54 else 0.0
            bgr = add_step_banner_and_tap(
                img,
                "PASO 2 · ENTREGA INMEDIATA DEL PAQUETE",
                "Link de Invitación + Descarga directa del Video de Mario (.MP4)",
                tap_xy=tap_xy,
                tap_prog=tap_p,
            )
            vw.write(bgr)
            total_written += 1

        # =====================================================================
        # PASO 3: EL INVITADO ABRE LA INVITACIÓN Y JUEGA EL MINIJUEGO ESPACIAL
        # =====================================================================
        print("[3/5] Grabando Paso 3: Minijuego en la invitación móvil...")
        page.goto("http://localhost:3000/invitacionmario/index.html", wait_until="networkidle")
        page.wait_for_timeout(400)

        # Pantalla de inicio de misión (28 frames ~1.2s)
        for i in range(28):
            img = snap_pil(page)
            tap_xy = (W // 2, 835) if i >= 16 else None
            tap_p = (i - 16) / 12.0 if i >= 16 else 0.0
            bgr = add_step_banner_and_tap(
                img,
                "PASO 3 · EL INVITADO ABRE SU LINK EN CELULAR",
                "Inicia la misión espacial para desbloquear la fiesta",
                tap_xy=tap_xy,
                tap_prog=tap_p,
            )
            vw.write(bgr)
            total_written += 1

        # Iniciar minijuego y capturar 5 segundos de acción hasta ganar 50 PTS
        page.click("#start-game-btn")
        for i in range(110):
            if i in (10, 28, 46, 66, 84):
                page.keyboard.press("Space")
            if i == 22:
                page.evaluate("if (window.updateScoreUI) window.updateScoreUI(20); document.getElementById('current-score').innerText='020'; document.getElementById('hud-progress-bar').style.width='40%';")
            if i == 52:
                page.evaluate("if (window.updateScoreUI) window.updateScoreUI(40); document.getElementById('current-score').innerText='040'; document.getElementById('hud-progress-bar').style.width='80%';")
            if i == 78:
                page.evaluate("document.getElementById('skip-btn')?.click();")
            page.wait_for_timeout(35)
            img = snap_pil(page)
            bgr = add_step_banner_and_tap(
                img,
                "PASO 3 · MINIJUEGO INTERACTIVO EN CELULAR",
                "Tus invitados atrapan 50 PTS y desbloquean la invitación",
            )
            vw.write(bgr)
            total_written += 1

        # =====================================================================
        # PASO 4: SE DESBLOQUEA LA INVITACIÓN Y SE REPRODUCE EL VIDEO DE MARIO
        # =====================================================================
        print("[4/5] Grabando Paso 4: Panel TRANSMISIÓN DE MARIO reproduciéndose con audio en vivo...")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)

        # Posicionar exactamente en el panel #mario-video-panel
        video_panel_y = page.evaluate(
            """() => {
                const el = document.getElementById('mario-video-panel');
                if (!el) return 300;
                const r = el.getBoundingClientRect();
                return Math.max(0, window.scrollY + r.top - 58);
            }"""
        )

        # Scroll suave del Hero hacia el panel TRANSMISIÓN DE MARIO y clic en el botón Play amarillo (42 frames)
        for i in range(42):
            u = i / 41.0
            sy = int(video_panel_y * (1.0 - pow(1.0 - min(1.0, u / 0.65), 3)))
            page.evaluate(f"window.scrollTo(0, {sy})")
            img = snap_pil(page)
            tap_xy = (W // 2, 650) if u >= 0.72 else None
            tap_p = (u - 0.72) / 0.28 if u >= 0.72 else 0.0
            bgr = add_step_banner_and_tap(
                img,
                "PASO 4 · TRANSMISIÓN DE MARIO EN LA INVITACIÓN",
                "El invitado toca Play para escuchar el saludo personalizado",
                tap_xy=tap_xy,
                tap_prog=tap_p,
            )
            vw.write(bgr)
            total_written += 1

        # Ocultar el overlay de Play y obtener las coordenadas exactas del contenedor `.mario-video-shell` en pantalla
        page.evaluate(
            """() => {
                document.getElementById('btn-play-mario-video')?.classList.add('is-playing');
                const lbl = document.getElementById('btn-replay-label');
                if (lbl) lbl.innerText = 'PAUSAR SALUDO';
            }"""
        )
        page.wait_for_timeout(100)
        rect_info = page.evaluate(
            """() => {
                const el = document.querySelector('.mario-video-shell');
                const r = el.getBoundingClientRect();
                return { x: r.left, y: r.top, w: r.width, h: r.height, vw: window.innerWidth, vh: window.innerHeight };
            }"""
        )
        base_page_img = snap_pil(page)

        # Escalar coordenadas del viewport (390x693) al canvas (720x1280)
        sx = W / float(rect_info["vw"])
        sy = H / float(rect_info["vh"])
        vx0 = int(round(rect_info["x"] * sx)) + 3
        vy0 = int(round(rect_info["y"] * sy)) + 3
        vw_box = int(round(rect_info["w"] * sx)) - 6
        vh_box = int(round(rect_info["h"] * sy)) - 6

        # Mask redondeada para el reproductor incrustado
        v_mask = Image.new("L", (vw_box, vh_box), 0)
        ImageDraw.Draw(v_mask).rounded_rectangle((0, 0, vw_box - 1, vh_box - 1), radius=24, fill=255)

        video_start_frame = total_written
        for sf_idx, s_pil in enumerate(saludo_frames_pil):
            frame_canvas = base_page_img.copy()
            resized_saludo = s_pil.resize((vw_box, vh_box), Image.Resampling.LANCZOS)
            frame_canvas.paste(resized_saludo, (vx0, vy0), v_mask)

            sec_in_v = sf_idx / float(FPS)
            if sec_in_v < 6.8:
                sub_txt = "Bloque 1 (Dinámico): Saluda a Darío por su nombre y sus 6 años"
            elif sec_in_v < 14.3:
                sub_txt = "Bloque 2 (Fijo en Caché): Mario invita a todos sus amigos"
            elif sec_in_v < 20.5:
                sub_txt = "Bloque 3 (Dinámico con voz): Dice el día y la hora de la fiesta"
            else:
                sub_txt = 'Bloque 4: "¡En la dirección que ves aquí en pantalla!"'

            bgr = add_step_banner_and_tap(
                frame_canvas,
                "PASO 4 · REPRODUCCIÓN EN VIVO CON VOZ DE MARIO",
                sub_txt,
            )
            vw.write(bgr)
            total_written += 1
        video_end_frame = total_written

        # =====================================================================
        # PASO 5: RECORRIDO POR EL RESTO DE LA INVITACIÓN + PASE WHATSAPP
        # =====================================================================
        print("[5/5] Grabando Paso 5: Cuenta regresiva, Mapa GPS y Pase de Abordaje...")
        max_scroll = page.evaluate("document.body.scrollHeight - window.innerHeight")
        for i in range(96):
            u = i / 95.0
            cur_y = int(video_panel_y + (max_scroll - video_panel_y) * min(1.0, u / 0.72))
            page.evaluate(f"window.scrollTo(0, {cur_y})")
            if i == 68:
                page.fill("#guestNameInput", "Familia Pérez")
            if i == 76:
                page.evaluate("document.getElementById('pass-modal')?.classList.remove('hidden')")
            img = snap_pil(page)
            bgr = add_step_banner_and_tap(
                img,
                "PASO 5 · CUENTA REGRESIVA, MAPA GPS Y PASE RSVP",
                "Confirmación en 1 toque directo al WhatsApp del organizador",
            )
            vw.write(bgr)
            total_written += 1

        browser.close()

    vw.release()

    # =========================================================================
    # MEZCLA DE AUDIO: Tema de Super Mario Galaxy de fondo + Audio del Saludo de Mario
    # exactamente sincronizado cuando el invitado le da Play en el Paso 4
    # =========================================================================
    ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
    bgm_path = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "mario_galaxy_theme.mp3")
    delay_ms = int(round((video_start_frame / float(FPS)) * 1000))
    v_start_s = video_start_frame / float(FPS)
    v_end_s = video_end_frame / float(FPS)
    total_dur_s = total_written / float(FPS)

    # Bajamos el volumen del BGM mientras habla Mario en el Paso 4 y lo subimos antes/después
    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_dur_s:.2f},"
        f"volume='if(between(t,{v_start_s:.2f},{v_end_s:.2f}),0.03,0.22)':eval=frame[bgm];"
        f"[2:a]adelay={delay_ms}|{delay_ms},volume=1.15[saludo];"
        f"[bgm][saludo]amix=inputs=2:duration=first:dropout_transition=1,alimiter=limit=0.96[aout]"
    )

    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            temp_vis,
            "-i",
            bgm_path,
            "-i",
            SALUDO_MP4,
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            OUT_MP4,
        ],
        check=True,
    )
    if os.path.exists(temp_vis):
        os.remove(temp_vis)
    print(f"[OK] Recorrido completo guardado en: {OUT_MP4} ({total_dur_s:.1f}s)")


if __name__ == "__main__":
    main()
