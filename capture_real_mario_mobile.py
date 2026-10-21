# -*- coding: utf-8 -*-
"""
capture_real_mario_mobile.py
============================
Levanta un servidor HTTP local sobre `web_assets` y utiliza Playwright Chromium
en modo móvil real (390x693 @ 2x -> 780x1386) a 24 FPS exactos (1.0x real sin aceleración)
controlando `requestAnimationFrame` cuadro por cuadro para capturar:
1) `gameplay`: SOLO los últimos segundos del minijuego en velocidad 1.0x real (iniciando en 030/50 PTS -> 040 -> 050/50 PTS + confeti).
2) `unlocked`: Invitación desbloqueada mostrando el nuevo panel `TRANSMISIÓN DE MARIO` (video personalizado) + Mapa GPS + Pase RSVP.
3) `website`: `http://localhost:3000` (`dreamcrafters.lat`) enfocando la tarjeta de Super Mario Galaxy ($100 MXN con video incluido).
4) Rasterización HD transparente de `d-icon.svg` para el cierre animado.
"""

import os
import socket
import threading
import cv2
import numpy as np
from PIL import Image, ImageDraw
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
OUT_CAP_DIR = os.path.join(REPO_ROOT, "characters", "02_mario", "out", "real_mobile_capture")
SALUDO_MP4 = os.path.join(WEB_ASSETS_DIR, "invitacionmario", "saludo_mario_dario.mp4")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_local_server(directory):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    handler = partial(QuietHandler, directory=directory)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


def capture_all():
    for sub in ("gameplay", "unlocked", "website"):
        sub_dir = os.path.join(OUT_CAP_DIR, sub)
        os.makedirs(sub_dir, exist_ok=True)
        for old_f in os.listdir(sub_dir):
            if old_f.endswith(".png"):
                try:
                    os.remove(os.path.join(sub_dir, old_f))
                except OSError:
                    pass

    # Cargar cuadros del video personalizado de Mario para inyectarlos dentro del reproductor de la escena `unlocked`
    saludo_frames = []
    if os.path.exists(SALUDO_MP4):
        cap = cv2.VideoCapture(SALUDO_MP4)
        while len(saludo_frames) < 300:
            ret, bgr = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            saludo_frames.append(Image.fromarray(rgb).convert("RGBA"))
        cap.release()

    server, port = start_local_server(WEB_ASSETS_DIR)
    url = f"http://127.0.0.1:{port}/invitacionmario/index.html?name=DAR%C3%8DO&ageMessage=%C2%A1CUMPLE%206%20A%C3%91OS!&date=S%C3%81BADO%2024%20DE%20MAYO"
    print(f"Servidor local activo en {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 693},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.dismiss())

        # Controlar requestAnimationFrame para que NO avance mientras page.screenshot() guarda a disco -> velocidad 1.0x exacta
        page.add_init_script(
            """
            (() => {
                try {
                    Object.defineProperty(CanvasRenderingContext2D.prototype, 'filter', {
                        get() { return 'none'; },
                        set(v) {}
                    });
                } catch (e) {}

                const origRandom = Math.random;
                let afterClickCalls = 0;
                window.__gameStarted = false;
                document.addEventListener('click', () => { window.__gameStarted = true; }, true);
                Math.random = function() {
                    if (window.__gameStarted && afterClickCalls < 8) {
                        afterClickCalls++;
                        return 0.88;
                    }
                    return origRandom.apply(this, arguments);
                };

                window.__rafQueue = [];
                window.__virtualTime = 1000.0;
                window.requestAnimationFrame = function(cb) {
                    window.__rafQueue.push(cb);
                    return window.__rafQueue.length;
                };
                window.__stepGameTicks = function(ticks) {
                    for (let t = 0; t < ticks; t++) {
                        window.__virtualTime += 16.6667;
                        const batch = window.__rafQueue.splice(0, window.__rafQueue.length);
                        for (let i = 0; i < batch.length; i++) {
                            try { batch[i](window.__virtualTime); } catch (e) {}
                        }
                    }
                };
            })();
            """
        )

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(800)

        # =====================================================================
        # 1/4 GAMEPLAY: GRABAR SOLO LOS ÚLTIMOS SEGUNDOS DEL MINIJUEGO A 1.0x REAL
        # =====================================================================
        print("1/4 Capturando últimos segundos del minijuego en velocidad 1.0x real (030 -> 050 PTS)...")
        page.evaluate("() => { window.__autoPlayDemo = true; const btn = document.getElementById('start-game-btn'); if (btn) btn.click(); }")
        page.evaluate(
            """() => {
                window.__stepGameTicks(4);
                const el = document.getElementById('current-score');
                if (el) el.innerText = '030';
                const bar = document.getElementById('hud-progress-bar');
                if (bar) bar.style.width = '60%';
            }"""
        )

        total_gameplay_frames = 250
        for f_idx in range(total_gameplay_frames):
            ticks = 2 if (f_idx % 2 == 0) else 3
            if f_idx in (16, 56, 98, 140, 182):
                page.keyboard.press("Space")

            page.evaluate(f"window.__stepGameTicks({ticks})")

            if f_idx < 75:
                pts_now, pct_now = "030", "60%"
            elif f_idx < 145:
                pts_now, pct_now = "040", "80%"
            else:
                pts_now, pct_now = "050", "100%"

            page.evaluate(
                f"""() => {{
                    const el = document.getElementById('current-score');
                    if (el) el.innerText = '{pts_now}';
                    const bar = document.getElementById('hud-progress-bar');
                    if (bar) bar.style.width = '{pct_now}';
                    if ('{pts_now}' === '050' && window.confetti && !window.__celebrated50) {{
                        window.__celebrated50 = true;
                        window.confetti({{ particleCount: 55, spread: 70, origin: {{ y: 0.55 }} }});
                    }}
                }}"""
            )
            out_png = os.path.join(OUT_CAP_DIR, "gameplay", f"frame_{f_idx:04d}.png")
            page.screenshot(path=out_png)

        # =====================================================================
        # 2/4 UNLOCKED: INVITACIÓN DESBLOQUEADA + PANEL TRANSMISIÓN DE MARIO EN VIVO
        # =====================================================================
        print("2/4 Capturando #landing-view con el Video Personalizado de Mario en vivo + Mapa GPS...")
        page.evaluate(
            """() => {
                const gv = document.getElementById('game-view');
                const lv = document.getElementById('landing-view');
                if (gv && lv) {
                    gv.classList.remove('active');
                    gv.classList.add('hidden');
                    lv.classList.remove('hidden');
                    lv.classList.add('active');
                }
                document.getElementById('btn-play-mario-video')?.classList.add('is-playing');
                const lbl = document.getElementById('btn-replay-label');
                if (lbl) lbl.innerText = 'REPRODUCIENDO SALUDO...';
                window.scrollTo(0, 0);
            }"""
        )
        page.wait_for_timeout(300)

        video_panel_y = page.evaluate(
            """() => {
                const el = document.getElementById('mario-video-panel');
                if (!el) return 260;
                const r = el.getBoundingClientRect();
                return Math.max(0, window.scrollY + r.top - 52);
            }"""
        )
        max_scroll = page.evaluate("document.documentElement.scrollHeight - window.innerHeight")

        total_unlocked_frames = 270
        for f_idx in range(total_unlocked_frames):
            # 1) Primeros 1.5s: mostrar título DARÍO ¡CUMPLE 6 AÑOS! y bajar suavemente al panel TRANSMISIÓN DE MARIO
            # 2) De frame 36 a 175 (~6 seg): quedarse fijo en TRANSMISIÓN DE MARIO viendo a Mario hablar y mostrar la dirección
            # 3) De frame 175 a 270 (~4 seg): bajar suavemente por Cuenta Regresiva, Mapa GPS y Pase de Abordaje
            if f_idx < 36:
                u = f_idx / 36.0
                ease = u * u * (3.0 - 2.0 * u)
                sy = int(ease * video_panel_y)
            elif f_idx < 175:
                sy = int(video_panel_y)
            else:
                u = min(1.0, (f_idx - 175) / 85.0)
                ease = u * u * (3.0 - 2.0 * u)
                sy = int(video_panel_y + ease * (max_scroll - video_panel_y))

            page.evaluate(f"window.scrollTo(0, {sy}); window.__stepGameTicks(2);")
            rect_info = page.evaluate(
                """() => {
                    const el = document.querySelector('.mario-video-shell');
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return { x: r.left, y: r.top, w: r.width, h: r.height, vw: window.innerWidth, vh: window.innerHeight };
                }"""
            )
            out_png = os.path.join(OUT_CAP_DIR, "unlocked", f"frame_{f_idx:04d}.png")
            page.screenshot(path=out_png)

            # Incrustar el cuadro real del saludo de Mario dentro de `.mario-video-shell` cuando está visible
            if rect_info and saludo_frames and -rect_info["h"] < rect_info["y"] < rect_info["vh"]:
                base_img = Image.open(out_png).convert("RGBA")
                bw, bh = base_img.size
                sx = bw / float(rect_info["vw"])
                sy_scale = bh / float(rect_info["vh"])
                vx0 = int(round(rect_info["x"] * sx)) + 3
                vy0 = int(round(rect_info["y"] * sy_scale)) + 3
                vw_box = max(10, int(round(rect_info["w"] * sx)) - 6)
                vh_box = max(10, int(round(rect_info["h"] * sy_scale)) - 6)

                # Mostrar mitad saludo de cumpleaños y mitad tarjeta de dirección en pantalla
                s_idx = (f_idx * 3) % len(saludo_frames)
                s_frame = saludo_frames[s_idx].resize((vw_box, vh_box), Image.Resampling.LANCZOS)
                v_mask = Image.new("L", (vw_box, vh_box), 0)
                ImageDraw.Draw(v_mask).rounded_rectangle((0, 0, vw_box - 1, vh_box - 1), radius=24, fill=255)
                base_img.paste(s_frame, (vx0, vy0), v_mask)
                base_img.save(out_png)

        # =====================================================================
        # 3/4 WEBSITE: CAPTURAR SITIO ACTUALIZADO EN LOCALHOST:3000 ($100 MXN + VIDEO)
        # =====================================================================
        print("3/4 Capturando dreamcrafters.lat (localhost:3000) enfocando Super Mario Galaxy $100 MXN...")
        try:
            page.goto("http://localhost:3000", wait_until="networkidle", timeout=20000)
        except Exception:
            page.goto("https://dreamcrafters.lat", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(800)

        mario_target_y = page.evaluate(
            """() => {
                const marioPane = document.querySelector('.dc-pane-mario');
                if (marioPane) {
                    const rect = marioPane.getBoundingClientRect();
                    return Math.max(0, window.scrollY + rect.top - 95);
                }
                return 1350;
            }"""
        )
        total_web_frames = 250
        for i in range(total_web_frames):
            if i < 48:
                sy = 0
            else:
                u = min(1.0, max(0.0, (i - 48) / 95.0))
                ease = u * u * (3.0 - 2.0 * u)
                sy = int(ease * mario_target_y)
            page.evaluate(f"window.scrollTo(0, {sy})")
            page.screenshot(path=os.path.join(OUT_CAP_DIR, "website", f"frame_{i:04d}.png"))

        svg_path = os.path.join(WEB_ASSETS_DIR, "landing", "d-icon.svg")
        with open(svg_path, "r", encoding="utf-8") as sf:
            svg_raw = sf.read()
        svg_page = browser.new_page(viewport={"width": 600, "height": 620}, device_scale_factor=2)
        svg_html = f"""<!DOCTYPE html>
        <html><head><style>
        body {{ margin:0; padding:0; background:transparent; display:flex; align-items:center; justify-content:center; width:600px; height:620px; }}
        svg {{ width:520px; height:533px; fill:#FAF6EE; filter: drop-shadow(0 0 18px rgba(56,189,248,0.55)); }}
        </style></head><body>{svg_raw}</body></html>"""
        svg_page.set_content(svg_html)
        svg_page.wait_for_timeout(200)
        svg_page.screenshot(path=os.path.join(OUT_CAP_DIR, "d_icon_hd.png"), omit_background=True)
        svg_page.close()

        browser.close()
    server.shutdown()
    print("Captura movil 1.0x real completada con exito.")


if __name__ == "__main__":
    capture_all()
