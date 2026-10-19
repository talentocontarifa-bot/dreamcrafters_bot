# -*- coding: utf-8 -*-
"""
capture_real_mario_mobile.py
============================
Levanta un servidor HTTP local sobre `web_assets` y utiliza Playwright Chromium
en modo móvil real (390x740 @ 2x) para capturar los cuadros reales de:
1) `/invitacionmario/index.html` en fase de videojuego (`#game-view`)
2) `/invitacionmario/index.html` en fase de invitación desbloqueada (`#landing-view` con scroll)
3) `https://dreamcrafters.lat` en vista móvil real
4) Rasterización HD transparente de `d-icon.svg` para el Intro animado
"""

import os
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_ASSETS_DIR = os.path.join(REPO_ROOT, "web_assets")
OUT_CAP_DIR = os.path.join(REPO_ROOT, "characters", "02_mario", "out", "real_mobile_capture")


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
    os.makedirs(os.path.join(OUT_CAP_DIR, "gameplay"), exist_ok=True)
    os.makedirs(os.path.join(OUT_CAP_DIR, "unlocked"), exist_ok=True)
    os.makedirs(os.path.join(OUT_CAP_DIR, "website"), exist_ok=True)

    server, port = start_local_server(WEB_ASSETS_DIR)
    url = f"http://127.0.0.1:{port}/invitacionmario/index.html"
    print(f"Servidor local activo en {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 740},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.dismiss())

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
                    if (window.__gameStarted && afterClickCalls < 6) {
                        afterClickCalls++;
                        return 0.88;
                    }
                    return origRandom.apply(this, arguments);
                };
            })();
            """
        )

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)

        print("1/4 Capturando pantalla inicial #game-view (INICIAR MISION)...")
        for f_idx in range(34):
            page.wait_for_timeout(40)
            page.screenshot(path=os.path.join(OUT_CAP_DIR, "gameplay", f"frame_{f_idx:04d}.png"))

        print("2/4 Capturando minijuego real en #game-canvas (Starlight Stage + Cometas + Chispas)...")
        try:
            page.evaluate("() => { const btn = document.getElementById('start-game-btn'); if (btn) btn.click(); }")
        except Exception:
            page.mouse.click(195, 480)
        page.wait_for_timeout(120)

        for f_idx in range(34, 192):
            if f_idx % 22 == 0 and f_idx > 48:
                page.keyboard.press("Space")
            prog_pts = min(50, int(((f_idx - 34) / 145.0) * 52))
            prog_pct = min(100, int((prog_pts / 50.0) * 100))
            try:
                page.evaluate(
                    f"""() => {{
                        const el = document.getElementById('current-score');
                        if (el) el.innerText = String({prog_pts}).padStart(3, '0');
                        const bar = document.getElementById('hud-progress-bar');
                        if (bar) bar.style.width = '{prog_pct}%';
                    }}"""
                )
            except Exception:
                pass
            page.wait_for_timeout(40)
            page.screenshot(path=os.path.join(OUT_CAP_DIR, "gameplay", f"frame_{f_idx:04d}.png"))

        print("3/4 Capturando #landing-view desbloqueada con scroll real...")
        try:
            page.evaluate(
                """() => {
                    const skipBtn = document.getElementById('skip-btn');
                    if (skipBtn) skipBtn.click();
                    const gv = document.getElementById('game-view');
                    const lv = document.getElementById('landing-view');
                    if (gv && lv) {
                        gv.classList.remove('active');
                        gv.classList.add('hidden');
                        lv.classList.remove('hidden');
                        lv.classList.add('active');
                    }
                    window.scrollTo(0, 0);
                }"""
            )
        except Exception:
            pass

        page.wait_for_timeout(600)
        max_scroll = page.evaluate(
            """() => {
                const lv = document.getElementById('landing-view');
                const h1 = document.documentElement.scrollHeight - window.innerHeight;
                const h2 = lv ? (lv.scrollHeight - lv.clientHeight) : 0;
                return Math.max(h1, h2, 1600);
            }"""
        )

        total_unlocked_frames = 216
        for f_idx in range(total_unlocked_frames):
            if f_idx < 32:
                scroll_y = 0
            else:
                t_norm = min(1.0, (f_idx - 32) / float(total_unlocked_frames - 48))
                ease = t_norm * t_norm * (3.0 - 2.0 * t_norm)
                scroll_y = int(ease * max_scroll)

            page.evaluate(
                f"""() => {{
                    window.scrollTo(0, {scroll_y});
                    const lv = document.getElementById('landing-view');
                    if (lv) lv.scrollTop = {scroll_y};
                }}"""
            )
            page.wait_for_timeout(30)
            page.screenshot(path=os.path.join(OUT_CAP_DIR, "unlocked", f"frame_{f_idx:04d}.png"))

        print("4/4 Capturando https://dreamcrafters.lat actualizado en modo movil y d-icon.svg...")
        try:
            page.goto("https://dreamcrafters.lat", wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(1500)
            max_s = page.evaluate("() => Math.min(2400, document.documentElement.scrollHeight - window.innerHeight)")
            for i in range(96):
                u = min(1.0, max(0.0, (i - 12) / 76.0))
                ease = u * u * (3.0 - 2.0 * u)
                sy = int(ease * max_s)
                page.evaluate(f"window.scrollTo(0, {sy})")
                page.wait_for_timeout(30)
                page.screenshot(path=os.path.join(OUT_CAP_DIR, "website", f"frame_{i:04d}.png"))
        except Exception as e:
            print(f"Aviso capturando dreamcrafters.lat: {e}")

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
    print("Captura movil real completada con exito.")


if __name__ == "__main__":
    capture_all()
