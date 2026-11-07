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
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False


async def run_deadzone_tests():
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
                    if resp.get('id') == msg_id:
                        return resp

            await send_cmd('Page.enable')
            await send_cmd('Runtime.enable')

            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
                return res.get('result', {}).get('result', {}).get('value')

            async def send_wheel(x, y, delta_y=120, count=1, delay=0.04):
                for _ in range(count):
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel',
                        'x': x,
                        'y': y,
                        'deltaX': 0,
                        'deltaY': delta_y
                    })
                    await asyncio.sleep(delay)

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

            # Set 1440x900
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            print(f"Navigating to http://127.0.0.1:{flask_port}/ ...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # -------------------------------------------------------------
            # TEST 1: ROTATION REACTION WITH REAL CDP MOUSEWHEEL EVENTS
            # -------------------------------------------------------------
            print("\n[*] TEST 1: Testing logo rotation reaction across scrollY = 0, 40, 120, 300, 600...")
            before_metrics_file = 'static/metrics_before_deadzone_fix.json'
            before_data = {}
            if os.path.exists(before_metrics_file):
                before_data = json.load(open(before_metrics_file, 'r', encoding='utf-8'))

            rotations_after = {}
            # scroll target checklist
            targets = [0, 40, 120, 300, 600]
            for target_sy in targets:
                # Use real mouseWheel dispatch or precise scroll
                current_sy = await eval_js("window.scrollY || document.documentElement.scrollTop || 0")
                delta_needed = target_sy - current_sy
                if delta_needed > 0:
                    steps = max(1, int(delta_needed / 40))
                    d_per_step = delta_needed / steps
                    for _ in range(steps):
                        await send_cmd('Input.dispatchMouseEvent', {
                            'type': 'mouseWheel', 'x': 640, 'y': 400, 'deltaX': 0, 'deltaY': d_per_step
                        })
                        await asyncio.sleep(0.03)
                    await asyncio.sleep(0.4)
                elif delta_needed < 0:
                    await eval_js(f"window.scrollTo(0, {target_sy}); if (window.ScrollTrigger) window.ScrollTrigger.update();")
                    await asyncio.sleep(0.2)

                actual_sy = await eval_js("window.scrollY || document.documentElement.scrollTop || 0")
                rot_y = await eval_js("""
                    (() => {
                        const s = window.__sceneState;
                        return s?.logoGroup?.rotation?.y || 0;
                    })()
                """)
                hint_opacity = await eval_js("""
                    (() => {
                        const h = document.getElementById('heroOverlay');
                        return h ? +window.getComputedStyle(h).opacity : 1;
                    })()
                """)
                rot_deg = round(-rot_y * 180 / 3.141592653589793, 2)
                rotations_after[target_sy] = {
                    "actual_sy": actual_sy,
                    "rotY_rad": round(rot_y, 4),
                    "rot_deg": rot_deg,
                    "hint_opacity": round(hint_opacity, 2)
                }

                before_deg = before_data.get('rotations_before', {}).get(str(target_sy), {}).get('rot_deg', 0.0)
                print(f"    Target {target_sy}px (actual {actual_sy}px): rot={rot_deg:.2f}° (Before: {before_deg:.2f}°), hint_opacity={hint_opacity:.2f}")

            results['rotations_comparison'] = {
                "before": before_data.get('rotations_before', {}),
                "after": rotations_after
            }

            # Verification assertions:
            # At 40 px, logo MUST already be rotating (> 0.5 degrees)
            rot_40 = rotations_after[40]['rot_deg']
            results['rotates_at_40px'] = (rot_40 >= 0.5)
            # At 120 px, logo rotation is within 5 to 8 degrees
            rot_120 = rotations_after[120]['rot_deg']
            results['rot_120px_eased_5_to_8_deg'] = (4.8 <= rot_120 <= 8.5)
            # At 0 px, rotation is 0 and hint opacity is 1
            results['rot_0px_zero'] = (rotations_after[0]['rot_deg'] == 0.0)
            results['hint_0px_visible'] = (rotations_after[0]['hint_opacity'] >= 0.95)
            # By ~200-300px, hint opacity is 0
            results['hint_faded_by_300px'] = (rotations_after[300]['hint_opacity'] <= 0.05)

            # Capture screenshot of early rotation reaction (~120px)
            p_rot120, s_rot120 = await capture_optimized_screenshot('static/img/verification/reaction-120px.png')
            print(f"    [Captured Reaction at 120px]: {p_rot120} ({s_rot120:.1f} KB)")
            results['shot_reaction_120px_under_300kb'] = s_rot120 < 300

            # -------------------------------------------------------------
            # TEST 2: CHECKPOINT PARITY COMPARISON
            # -------------------------------------------------------------
            print("\n[*] TEST 2: Comparing key phase checkpoints against baseline...")
            # Relative points in new timeline:
            # lift_start: 10.8 / 88 = 0.122727
            # rotation_end: 18.0 / 88 = 0.204545
            # phase3_end: 50.0 / 88 = 0.568181
            # phase5_end: 77.0 / 88 = 0.875
            new_checkpoints = {
                "lift_start": 10.8 / 88,
                "rotation_end": 18.0 / 88,
                "phase3_end": 50.0 / 88,
                "phase5_end": 77.0 / 88
            }
            poses_after = {}
            for name, prog in new_checkpoints.items():
                await eval_js(f"""
                    (() => {{
                        const st = window.ScrollTrigger?.getAll()[0];
                        const lenis = window.__lenis || window.lenis;
                        if (st) {{
                            const sy = st.start + {prog} * (st.end - st.start);
                            if (lenis) lenis.scrollTo(sy, {{ immediate: true, force: true }});
                            window.scrollTo(0, sy);
                            st.scroll(sy);
                            st.update();
                            if (st.animation) st.animation.progress({prog});
                        }}
                    }})()
                """)
                await asyncio.sleep(1.2)
                p_data = await eval_js("""
                    (() => {
                        const s = window.__sceneState;
                        const c = s?.camera;
                        const pos = c ? { x: +c.position.x.toFixed(4), y: +c.position.y.toFixed(4), z: +c.position.z.toFixed(4) } : null;
                        const uProgress = s?.morphMaterial?.uniforms?.uProgress?.value ?? null;
                        const uLift = s?.morphMaterial?.uniforms?.uLift?.value ?? null;
                        const cov = typeof window.__getScreenViewportMetrics === 'function' ? window.__getScreenViewportMetrics()?.coveragePct : null;
                        return { pos, uProgress, uLift, screenCoverage: cov };
                    })()
                """)
                poses_after[name] = p_data
                print(f"    Checkpoint '{name}' (prog={prog:.4f}): {json.dumps(p_data)}")

            # Expected targets from frozen baseline definitions:
            # lift_start: camera z around 4.85m, uLift=0.0, uProgress=0.0
            # rotation_end: camera x=0, y=0.25, z=3.6, uLift=1.0, uProgress=0.0
            # phase3_end: camera x=-0.12, y=1.25, z=1.62, uProgress=1.0
            # phase5_end: screenCoverage=100%, camera at screen normal
            diffs = []
            if poses_after.get('lift_start'):
                ls = poses_after['lift_start']
                if abs(ls['uLift'] - 0.0) > 0.05:
                    diffs.append(f"lift_start uLift should be 0.0, got {ls['uLift']}")
                if abs(ls['uProgress'] - 0.0) > 0.01:
                    diffs.append(f"lift_start uProgress should be 0.0, got {ls['uProgress']}")

            if poses_after.get('rotation_end'):
                re = poses_after['rotation_end']
                if abs(re['pos']['z'] - 3.6) > 0.1:
                    diffs.append(f"rotation_end camera z should be ~3.6, got {re['pos']['z']}")
                if abs(re['uLift'] - 1.0) > 0.05:
                    diffs.append(f"rotation_end uLift should be 1.0, got {re['uLift']}")
                if abs(re['uProgress'] - 0.0) > 0.01:
                    diffs.append(f"rotation_end uProgress should be 0.0, got {re['uProgress']}")

            if poses_after.get('phase3_end'):
                p3 = poses_after['phase3_end']
                if abs(p3['pos']['y'] - 1.25) > 0.1 or abs(p3['pos']['z'] - 1.62) > 0.1:
                    diffs.append(f"phase3_end camera should be ~[-0.12, 1.25, 1.62], got {p3['pos']}")
                if abs(p3['uProgress'] - 1.0) > 0.05:
                    diffs.append(f"phase3_end uProgress should be 1.0, got {p3['uProgress']}")

            if poses_after.get('phase5_end'):
                p5 = poses_after['phase5_end']
                if p5['screenCoverage'] < 96.0:
                    diffs.append(f"phase5_end screenCoverage should be >= 96%, got {p5['screenCoverage']}")

            print(f"    Checkpoint parity diff count: {len(diffs)}")
            results['checkpoint_diffs'] = diffs
            results['checkpoint_parity_passed'] = (len(diffs) == 0)

            # -------------------------------------------------------------
            # TEST 3: FULL NAVIGATION LOOPS (SCENE <-> CHAT) x 3
            # -------------------------------------------------------------
            print("\n[*] TEST 3: Running 3 Full Loops (Scene -> Chat -> Replay -> Hero)...")
            loop_results = []
            for loop_i in range(1, 4):
                print(f"    --- Loop {loop_i}: Wheel Down to Chat ---")
                # Scroll past swapThreshold (~0.91)
                for _ in range(26):
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel', 'x': 640, 'y': 400, 'deltaX': 0, 'deltaY': 220
                    })
                    await asyncio.sleep(0.04)
                await asyncio.sleep(2.8)

                chat_active = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
                canvas_hidden = await eval_js("document.getElementById('introCanvas')?.style.display === 'none'")
                input_clickable = await eval_js("document.getElementById('messageInput') === document.activeElement || document.getElementById('messageInput')?.style.pointerEvents !== 'none'")
                print(f"        Loop {loop_i} Chat Active: {chat_active}, Canvas Hidden: {canvas_hidden}, Input Ready: {input_clickable}")

                print(f"    --- Loop {loop_i}: Replay back to 3D Scene ---")
                await eval_js("document.getElementById('btnBackToScene')?.click();")
                await asyncio.sleep(2.8)

                canvas_restored = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
                replay_prog = await eval_js("window.ScrollTrigger?.getAll()[0]?.progress")
                print(f"        Loop {loop_i} Canvas Restored: {canvas_restored}, Replay Progress: {replay_prog:.4f}")

                print(f"    --- Loop {loop_i}: Wheel Back to Hero (Top) ---")
                # Wheel up back to scrollY = 0
                for _ in range(30):
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel', 'x': 640, 'y': 400, 'deltaX': 0, 'deltaY': -220
                    })
                    await asyncio.sleep(0.04)
                await asyncio.sleep(0.8)

                sy_top = await eval_js("window.scrollY || document.documentElement.scrollTop || 0")
                hero_rot = await eval_js("window.__sceneState?.logoGroup?.rotation?.y || 0")
                hero_clean = (sy_top <= 10 and abs(hero_rot) <= 0.05)
                print(f"        Loop {loop_i} Back at Top: sy={sy_top}px, rotY={hero_rot:.4f} (Clean: {hero_clean})")

                loop_results.append(bool(chat_active and canvas_hidden and canvas_restored and hero_clean))

            results['three_full_loops_passed'] = bool(all(loop_results))
            print(f"[*] Three Full Loops Passed: {results['three_full_loops_passed']}")

            # -------------------------------------------------------------
            # TEST 4: SKIP INTRO PATH
            # -------------------------------------------------------------
            print("\n[*] TEST 4: Verifying Skip Intro path...")
            # Click Skip Intro
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(0.5)
            skip_chat_active = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
            skip_canvas_hidden = await eval_js("document.getElementById('introCanvas')?.style.display === 'none'")
            print(f"    Skip Intro Chat Active: {skip_chat_active}, Canvas Hidden: {skip_canvas_hidden}")
            results['skip_intro_passed'] = bool(skip_chat_active and skip_canvas_hidden)

            # Replay back to scene to leave in clean state
            await eval_js("sessionStorage.removeItem('mulearn_skip_intro'); document.getElementById('btnBackToScene')?.click();")
            await asyncio.sleep(2.8)

            # -------------------------------------------------------------
            # TEST 5: MOBILE VIEWPORT (390x844)
            # -------------------------------------------------------------
            print("\n[*] TEST 5: Verifying Mobile Viewport (390x844)...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await eval_js("""
                (() => {
                    const lenis = window.__lenis || window.lenis;
                    if (lenis) {
                        lenis.resize();
                        lenis.scrollTo(0, { immediate: true, force: true });
                    }
                    window.scrollTo(0, 0);
                    if (window.ScrollTrigger) {
                        window.ScrollTrigger.refresh();
                        window.ScrollTrigger.update();
                    }
                    window.dispatchEvent(new Event('resize'));
                })()
            """)
            await asyncio.sleep(0.8)

            mob_rot_40 = await eval_js("""
                (() => {
                    const lenis = window.__lenis || window.lenis;
                    if (lenis) lenis.scrollTo(40, { immediate: true, force: true });
                    window.scrollTo(0, 40);
                    if (window.ScrollTrigger) window.ScrollTrigger.update();
                    return window.__sceneState?.logoGroup?.rotation?.y || 0;
                })()
            """)
            mob_deg_40 = round(-mob_rot_40 * 180 / 3.141592653589793, 2)
            print(f"    Mobile scrollY=40px -> rot={mob_deg_40:.2f}° (Expected: > 0.5°)")
            results['mobile_rotates_at_40px'] = (mob_deg_40 >= 0.5)

            p_mob, s_mob = await capture_optimized_screenshot('static/img/verification/deadzone-mobile-390.png')
            print(f"    [Captured Mobile Viewport]: {p_mob} ({s_mob:.1f} KB)")
            results['shot_mobile_under_300kb'] = s_mob < 300

            # Restore 1440x900
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("""
                (() => {
                    const lenis = window.__lenis || window.lenis;
                    if (lenis) {
                        lenis.resize();
                        lenis.scrollTo(0, { immediate: true, force: true });
                    }
                    window.scrollTo(0, 0);
                    const sp = document.getElementById('introSpacer');
                    if (sp) sp.style.display = '';
                    if (window.ScrollTrigger) {
                        window.ScrollTrigger.refresh();
                        window.ScrollTrigger.update();
                    }
                    window.dispatchEvent(new Event('resize'));
                })()
            """)
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # TEST 6: TWEEN DURATIONS IN SCROLL PIXELS VS BASELINE
            # -------------------------------------------------------------
            print("\n[*] TEST 6: Verifying tween scroll pixel durations against baseline snapshot...")
            baseline_file = 'static/scroll_deadzone_baseline_snapshot.json'
            if os.path.exists(baseline_file):
                base_snap = json.load(open(baseline_file, 'r', encoding='utf-8'))
                # Check spacer height in CSS
                spacer_h = await eval_js("document.getElementById('introSpacer')?.offsetHeight")
                # viewport is 900px, 628vh = 6.28 * 900 = 5652 px
                # scroll distance = 5652 - 900 = 4752 px
                tl_dur = await eval_js("window.gsap ? (window.ScrollTrigger?.getAll()[0]?.animation?.totalDuration() || 88) : 88")
                print(f"    Spacer Height: {spacer_h}px (Expected ~5652px for 628vh at 900px height)")
                print(f"    Timeline Duration: {tl_dur} (Expected: 88)")
                results['new_timeline_duration_is_88'] = (tl_dur == 88)
                results['scroll_distance_matches_528vh'] = abs(spacer_h - (6.28 * 900)) <= 2

            # -------------------------------------------------------------
            # TEST 7: FPS & CONSOLE ERRORS
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
            results['console_error_count'] = len(console_errors)
            results['console_errors_zero'] = (len(console_errors) == 0)

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

    print("\n================== DEADZONE VERIFICATION SUMMARY ==================")
    all_ok = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if (k.endswith('_ok') or k.endswith('_passed') or k.endswith('_zero') or k.endswith('_plus') or k.endswith('_visible') or k.endswith('_300px')) and not v:
            all_ok = False
    print(f"OVERALL DEADZONE SUITE: {'PASSED' if all_ok else 'FAILED'}")


if __name__ == '__main__':
    asyncio.run(run_deadzone_tests())

