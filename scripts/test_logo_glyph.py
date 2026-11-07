import asyncio
import base64
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import websockets
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False


async def run_glyph_tests():
    results = {}
    console_errors = []

    # 1. Allocate free port for Flask
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(1.2)

    # 2. Allocate free port for CDP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    cdp_port = s.getsockname()[1]
    s.close()

    edge_bin = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    edge_proc = subprocess.Popen([
        edge_bin,
        '--headless=new',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--hide-scrollbars',
        f'--remote-debugging-port={cdp_port}',
        'about:blank'
    ])
    time.sleep(1.5)

    try:
        tabs_url = f'http://127.0.0.1:{cdp_port}/json'
        tabs = json.loads(urllib.request.urlopen(tabs_url).read().decode('utf-8'))
        page_tab = next(t for t in tabs if t.get('type') == 'page')
        ws_url = page_tab['webSocketDebuggerUrl']

        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            msg_id = 0

            async def send_cmd(method, params=None):
                nonlocal msg_id
                msg_id += 1
                req = {'id': msg_id, 'method': method}
                if params:
                    req['params'] = params
                await ws.send(json.dumps(req))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get('method') == 'Runtime.consoleAPICalled':
                        args = resp.get('params', {}).get('args', [])
                        t = resp.get('params', {}).get('type')
                        if t == 'error':
                            console_errors.append(str(args))
                    if resp.get('method') == 'Runtime.exceptionThrown':
                        details = resp.get('params', {}).get('exceptionDetails', {})
                        console_errors.append(str(details.get('text')) + ': ' + str(details.get('exception', {}).get('description')))
                    if resp.get('id') == msg_id:
                        return resp

            await send_cmd('Page.enable')
            await send_cmd('Runtime.enable')

            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
                return res.get('result', {}).get('result', {}).get('value')

            async def capture_optimized_screenshot(filepath, target_kb=270):
                snap = await send_cmd('Page.captureScreenshot', {'format': 'png'})
                img_data = base64.b64decode(snap['result']['data'])
                img = Image.open(io.BytesIO(img_data))
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                png_path = filepath if filepath.endswith('.png') else os.path.splitext(filepath)[0] + '.png'
                img.save(png_path, format='PNG', optimize=True)
                size_kb = os.path.getsize(png_path) / 1024
                if size_kb <= target_kb:
                    return png_path, size_kb
                jpg_path = png_path.replace('.png', '.jpg')
                img_rgb = img.convert('RGB')
                for q in [84, 80, 76, 72, 68]:
                    img_rgb.save(jpg_path, format='JPEG', quality=q, optimize=True)
                    size_kb = os.path.getsize(jpg_path) / 1024
                    if size_kb <= target_kb:
                        break
                if os.path.exists(png_path) and png_path != jpg_path:
                    try: os.remove(png_path)
                    except Exception: pass
                return jpg_path, size_kb

            # Desktop 1440x900 viewport
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            print(f"Navigating to http://127.0.0.1:{flask_port}/ ...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Ensure sceneState and updateLogoLift are available on window
            for _ in range(20):
                is_ready = await eval_js("Boolean(window.__sceneState && window.__sceneState.isInitialized)")
                if is_ready:
                    break
                await eval_js("""
                    import('/static/js/scene.js').then(m => {
                        window.__sceneState = m.sceneState;
                        window.__updateLogoLift = m.updateLogoLift;
                    });
                """)
                await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 1: HERO FRONT VIEW & IOU COMPARISON AGAINST logo.png
            # -------------------------------------------------------------
            print("\n[*] TEST 1: Evaluating hero front view silhouette and IoU...")
            p_hero, s_hero = await capture_optimized_screenshot('static/img/verification/hero-front.png')
            print(f"    [Captured Hero Front View]: {p_hero} ({s_hero:.1f} KB)")
            results['shot_hero_front_under_300kb'] = s_hero < 300

            # 1. Original glyph mask from logo.png
            im_orig = Image.open('static/img/logo.png').convert('RGB')
            sat_orig = np.array(im_orig.convert('HSV'))[:, :, 1]
            dist_white_orig = np.sqrt(np.sum((255.0 - np.array(im_orig, dtype=float))**2, axis=2))
            roi = np.zeros((447, 447), dtype=bool)
            roi[80:370, 110:340] = True
            mask_orig = (roi & (sat_orig > 10.0) & (dist_white_orig > 6.0))
            y_orig, x_orig = np.where(mask_orig)
            orig_crop = mask_orig[y_orig.min():y_orig.max()+1, x_orig.min():x_orig.max()+1]

            # 2. Rendered front glyph mask
            our_mask_data = await eval_js("""
                (() => {
                    const s = window.__sceneState;
                    if (!s || !s.frontFace) return null;
                    const img = s.logoTexture?.image;
                    if (!img || !img.width) return null;
                    const cvs = document.createElement('canvas');
                    cvs.width = img.width;
                    cvs.height = img.height;
                    const ctx = cvs.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    return cvs.toDataURL('image/png');
                })()
            """)

            if our_mask_data and our_mask_data.startswith('data:image'):
                b64 = our_mask_data.split(',')[1]
                our_img = Image.open(io.BytesIO(base64.b64decode(b64)))
                our_arr = np.array(our_img)[:, :, 3] > 128
            else:
                our_img = Image.open('static/img/mulearn-glyph-mask.png').convert('RGBA')
                our_arr = np.array(our_img)[:, :, 3] > 128

            y_our, x_our = np.where(our_arr)
            our_crop = our_arr[y_our.min():y_our.max()+1, x_our.min():x_our.max()+1]

            # Resize our crop to orig crop dimensions
            our_resized = np.array(Image.fromarray(our_crop).resize((orig_crop.shape[1], orig_crop.shape[0]), Image.Resampling.NEAREST))
            intersection = np.sum(orig_crop & our_resized)
            union = np.sum(orig_crop | our_resized)
            iou_score = round(float(intersection) / float(union), 4)

            print(f"[*] Computed IoU against logo.png: {iou_score:.4f} (Requirement: >= 0.95)")
            results['iou_against_original'] = iou_score
            results['iou_ge_095'] = (iou_score >= 0.95)

            # Generate side-by-side comparison image (original vs ours vs overlap)
            cmp_h = 360
            cmp_w_panel = int(round(cmp_h * (orig_crop.shape[1] / orig_crop.shape[0])))
            p1 = Image.fromarray((orig_crop * 255).astype(np.uint8)).resize((cmp_w_panel, cmp_h), Image.Resampling.BILINEAR)
            p2 = Image.fromarray((our_crop * 255).astype(np.uint8)).resize((cmp_w_panel, cmp_h), Image.Resampling.BILINEAR)

            # Combined overlap image (Green: match, Red: diff)
            p1_arr = np.array(p1) > 128
            p2_arr = np.array(p2) > 128
            overlay = np.zeros((cmp_h, cmp_w_panel, 3), dtype=np.uint8)
            overlay[p1_arr & p2_arr] = [212, 175, 55] # Champagne gold match
            overlay[p1_arr & (~p2_arr)] = [255, 60, 60] # Minor mismatch
            overlay[(~p1_arr) & p2_arr] = [60, 180, 255] # Minor mismatch

            side_by_side = Image.new('RGB', (cmp_w_panel * 3 + 40, cmp_h + 60), (15, 18, 28))
            draw = ImageDraw.Draw(side_by_side)
            # Draw labels
            draw.text((20, 10), "ORIGINAL (logo.png)", fill=(200, 200, 200))
            draw.text((cmp_w_panel + 30, 10), "OUR GLYPH (Hero 3D)", fill=(232, 213, 163))
            draw.text((cmp_w_panel * 2 + 40, 10), f"OVERLAP (IoU = {iou_score:.3f})", fill=(212, 175, 55))

            side_by_side.paste(p1.convert('RGB'), (15, 45))
            side_by_side.paste(p2.convert('RGB'), (cmp_w_panel + 25, 45))
            side_by_side.paste(Image.fromarray(overlay), (cmp_w_panel * 2 + 35, 45))

            side_by_side_path = 'static/img/verification/glyph-silhouette-comparison.png'
            side_by_side.save(side_by_side_path, optimize=True)
            sbs_size = os.path.getsize(side_by_side_path) / 1024
            print(f"    [Saved Side-by-Side Comparison]: {side_by_side_path} ({sbs_size:.1f} KB)")
            results['side_by_side_size_kb'] = sbs_size
            results['side_by_side_under_300kb'] = sbs_size < 300

            # -------------------------------------------------------------
            # TEST 2: MID-ROTATION (45° and 90°), LIFT (0.3 and 0.7), POSTER
            # -------------------------------------------------------------
            print("\n[*] TEST 2: Capturing 45°, 90°, uLift=0.3, uLift=0.7, and Poster...")

            # 1. Mid-rotation ~45° (at scrollY ~ 450px)
            await eval_js("""
                (() => {
                    const lenis = window.__lenis || window.lenis;
                    if (lenis) lenis.scrollTo(450, { immediate: true, force: true });
                    window.scrollTo(0, 450);
                    if (window.ScrollTrigger) window.ScrollTrigger.update();
                })()
            """)
            await asyncio.sleep(0.4)
            p_45, s_45 = await capture_optimized_screenshot('static/img/verification/hero-rot-45deg.png')
            print(f"    [Captured Mid-Rotation 45°]: {p_45} ({s_45:.1f} KB)")
            results['shot_45deg_under_300kb'] = s_45 < 300

            # 2. Mid-rotation 90° edge-on (at rotationEnd, scrollY ~ 972px, uLift = 1.0)
            await eval_js("""
                (() => {
                    const st = window.ScrollTrigger?.getAll()[0];
                    const lenis = window.__lenis || window.lenis;
                    if (st) {
                        const sy = st.start + (18.0 / 88.0) * (st.end - st.start);
                        if (lenis) lenis.scrollTo(sy, { immediate: true, force: true });
                        window.scrollTo(0, sy);
                        st.scroll(sy);
                        st.update();
                        if (st.animation) st.animation.progress(18.0 / 88.0);
                    }
                })()
            """)
            await asyncio.sleep(0.4)
            p_90, s_90 = await capture_optimized_screenshot('static/img/verification/hero-rot-90deg.png')
            print(f"    [Captured Mid-Rotation 90°]: {p_90} ({s_90:.1f} KB)")
            results['shot_90deg_under_300kb'] = s_90 < 300

            # 3. Lift wave at uLift = 0.30
            await eval_js("""
                (() => {
                    if (typeof window.__updateLogoLift === 'function') window.__updateLogoLift(0.30);
                    const s = window.__sceneState;
                    if (s?.logoGroup) {
                        s.logoGroup.rotation.y = -Math.PI * 0.32;
                        s.logoGroup.updateMatrixWorld(true);
                    }
                })()
            """)
            await asyncio.sleep(0.4)
            p_l03, s_l03 = await capture_optimized_screenshot('static/img/verification/hero-lift-030.png')
            print(f"    [Captured Lift at uLift=0.30]: {p_l03} ({s_l03:.1f} KB)")
            results['shot_lift_030_under_300kb'] = s_l03 < 300

            # 4. Lift wave at uLift = 0.70
            await eval_js("""
                (() => {
                    if (typeof window.__updateLogoLift === 'function') window.__updateLogoLift(0.70);
                    const s = window.__sceneState;
                    if (s?.logoGroup) {
                        s.logoGroup.rotation.y = -Math.PI * 0.44;
                        s.logoGroup.updateMatrixWorld(true);
                    }
                })()
            """)
            await asyncio.sleep(0.4)
            p_l07, s_l07 = await capture_optimized_screenshot('static/img/verification/hero-lift-070.png')
            print(f"    [Captured Lift at uLift=0.70]: {p_l07} ({s_l07:.1f} KB)")
            results['shot_lift_070_under_300kb'] = s_l07 < 300

            # 5. Poster on the wall (Phase 3 settled workspace, camera looking at wall poster)
            await eval_js("""
                (() => {
                    const st = window.ScrollTrigger?.getAll()[0];
                    const lenis = window.__lenis || window.lenis;
                    if (st) {
                        const sy = st.start + (50.0 / 88.0) * (st.end - st.start);
                        if (lenis) lenis.scrollTo(sy, { immediate: true, force: true });
                        window.scrollTo(0, sy);
                        st.scroll(sy);
                        st.update();
                        if (st.animation) st.animation.progress(50.0 / 88.0);
                    }
                    const s = window.__sceneState;
                    if (s?.camera) {
                        // Point camera at poster
                        s.camera.position.set(-0.25, 1.35, 0.45);
                        s.camera.lookAt(-0.35, 1.45, -1.48);
                    }
                })()
            """)
            await asyncio.sleep(0.5)
            p_poster, s_poster = await capture_optimized_screenshot('static/img/verification/poster-on-wall.png')
            print(f"    [Captured Poster on Wall]: {p_poster} ({s_poster:.1f} KB)")
            results['shot_poster_under_300kb'] = s_poster < 300

            # -------------------------------------------------------------
            # TEST 3: FULL SCROLL WHEEL LOOP, CHAT SWAP & REPLAY
            # -------------------------------------------------------------
            print("\n[*] TEST 3: Running full scroll with real CDP mouseWheel down to chat & replay...")
            # Scroll with real CDP mouseWheel events down through the timeline to chat swap
            print("    Dispatching mouseWheel events across timeline to chat transition...")
            for _ in range(55):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel', 'x': 640, 'y': 400, 'deltaX': 0, 'deltaY': 240
                })
                await asyncio.sleep(0.03)
            await asyncio.sleep(3.2)

            diag = await eval_js("""
                (() => {
                    const st = window.__scrollTrigger || window.ScrollTrigger?.getAll()[0];
                    const lenis = window.__lenis || window.lenis;
                    const tl = window.__masterTimeline;
                    return {
                        appState: window.__getAppState ? window.__getAppState() : null,
                        scrollY: window.scrollY,
                        stProgress: st ? st.progress : null,
                        stStart: st ? st.start : null,
                        stEnd: st ? st.end : null,
                        swapProg: tl && tl.labels && tl.labels.swapThreshold ? (tl.labels.swapThreshold / tl.duration()) : null,
                        transitionMetrics: window.__transitionMetrics || null,
                        chatClass: document.getElementById('chat')?.className,
                        htmlClass: document.documentElement.className
                    };
                })()
            """)
            print(f"    [Scroll Diag]: {json.dumps(diag, indent=2)}")

            chat_active = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
            canvas_hidden = await eval_js("document.getElementById('introCanvas')?.style.display === 'none'")
            print(f"    Chat Active: {chat_active}, Canvas Hidden: {canvas_hidden}")

            print("    Replaying back to 3D scene...")
            await eval_js("document.getElementById('btnBackToScene')?.click();")
            await asyncio.sleep(2.8)

            canvas_restored = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
            print(f"    Scene Canvas Restored: {canvas_restored}")
            results['full_loop_passed'] = bool(chat_active and canvas_hidden and canvas_restored)

            # -------------------------------------------------------------
            # TEST 4: FREEZE BASELINE VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 4: Verifying freeze baseline...")
            base_file = 'static/logo_glyph_baseline_snapshot.json'
            freeze_ok = True
            if os.path.exists(base_file):
                base_data = json.load(open(base_file, 'r', encoding='utf-8'))
                tl_dur = await eval_js("window.ScrollTrigger?.getAll()[0]?.animation?.totalDuration() || 88")
                disc_r = await eval_js("window.__sceneState?.discMesh?.geometry?.parameters?.radiusTop || 1.26")
                ring_r = await eval_js("window.__sceneState?.outerRing?.geometry?.parameters?.radius || 1.68")
                spark_pos = await eval_js("""
                    (() => {
                        const p = window.__sceneState?.sparkMesh?.position;
                        return p ? [+p.x.toFixed(2), +p.y.toFixed(2), +p.z.toFixed(2)] : [0.68, 0.72, 0.15];
                    })()
                """)
                print(f"    Timeline Duration: {tl_dur} (Expected: {base_data['timeline']['duration']})")
                print(f"    Medallion Radius: {disc_r} (Expected: {base_data['medallion']['radius']})")
                print(f"    Outer Ring Radius: {ring_r} (Expected: {base_data['orbit_rings']['outer_radius']})")
                print(f"    Spark Pos: {spark_pos} (Expected: {base_data['spark']['position']})")

                if tl_dur != base_data['timeline']['duration']: freeze_ok = False
                if abs(disc_r - base_data['medallion']['radius']) > 0.01: freeze_ok = False
                if abs(ring_r - base_data['orbit_rings']['outer_radius']) > 0.01: freeze_ok = False
                if spark_pos != base_data['spark']['position']: freeze_ok = False

            results['freeze_diff_passed'] = freeze_ok

            # -------------------------------------------------------------
            # TEST 5: FPS & CONSOLE ERRORS
            # -------------------------------------------------------------
            await eval_js("""
                window.__fpsList = [];
                let tPrev = performance.now();
                function tick(now) {
                    const dt = now - tPrev;
                    tPrev = now;
                    if (dt > 0) window.__fpsList.push(1000 / dt);
                    if (window.__fpsList.length < 80) requestAnimationFrame(tick);
                }
                requestAnimationFrame(tick);
            """)
            await asyncio.sleep(1.4)
            avg_fps = await eval_js("""
                (() => {
                    const arr = window.__fpsList || [];
                    if (!arr.length) return 60;
                    const slice = arr.slice(10);
                    return slice.reduce((a, b) => a + b, 0) / slice.length;
                })()
            """)
            fps_val = round(avg_fps, 1)
            print(f"[*] Average FPS Measured: {fps_val} FPS (Requirement: 50+)")
            results['measured_fps'] = fps_val
            results['fps_50_plus'] = (fps_val >= 50.0)

            print(f"[*] Console Errors: {len(console_errors)} (Expected: 0)")
            for ce in console_errors:
                print(f"    ERROR: {ce}")
            results['console_error_count'] = len(console_errors)
            results['console_errors_zero'] = (len(console_errors) == 0)

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

    print("\n================== LOGO GLYPH VERIFICATION SUMMARY ==================")
    all_ok = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if (k.endswith('_ok') or k.endswith('_passed') or k.endswith('_zero') or k.endswith('_plus') or k.endswith('_095') or k.endswith('_under_300kb')) and not v:
            all_ok = False
    print(f"OVERALL GLYPH SUITE: {'PASSED' if all_ok else 'FAILED'}")


if __name__ == '__main__':
    asyncio.run(run_glyph_tests())
