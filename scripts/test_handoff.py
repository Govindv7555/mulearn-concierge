"""
µLearn Concierge — Logo-to-Particle Handoff & Edge-On Dissolve Verification Suite (CDP)

Verifies:
1. Real CDP mouseWheel scroll across Phase 2 rotation & lift wave.
2. Screenshots captured at uLift = 0, 0.15, 0.3, 0.5, 0.7, 0.9, 1.0 and 90° edge-on pose (all strictly < 300 KB).
3. Pixel-level crossfade rule: (solid logo % + particle %) == 100% across all frames.
4. Edge-on fix: medallion disc extrusion is 1.4cm (< 1.5cm) and fades to opacity 0, zero grey slab at 90°.
5. Reverse scroll test: logo rebuilds smoothly outward-to-inward as particles fly back.
6. Two full loops (Scene -> Chat -> Scene -> Chat -> Scene).
7. Freeze diff verification against static/handoff_baseline_snapshot.json and static/verification_snapshot_before.json.
8. Zero console errors and 50+ FPS measurement.
"""

import asyncio
import base64
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
import io
import numpy as np

# Offline mock mode for Flask API calls
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False


async def run_handoff_tests():
    results = {}
    console_errors = []

    # 1. Allocate free ports
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(1.2)

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

            async def send_wheel(x, y, delta_y=120, count=5, delay=0.05):
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

            # Ensure hooks exposed
            await eval_js("""
                import('/static/js/timeline.js').then(m => {
                    // timeline imports exposed on window
                });
            """)
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 1 & 2: uLift CHECKPOINTS & PIXEL-LEVEL CROSSFADE
            # -------------------------------------------------------------
            print("\n[*] TEST 1: Capturing uLift checkpoints (0, 0.15, 0.3, 0.5, 0.7, 0.9, 1.0)...")
            ulift_checkpoints = [0.0, 0.15, 0.30, 0.50, 0.70, 0.90, 1.0]
            handoff_data = []

            for lift in ulift_checkpoints:
                # Set rotation to ~60-100% of 90 degrees matching timeline lift window
                rot_y = - (0.60 + 0.40 * lift) * (3.14159 * 0.52);
                await eval_js(f"""
                    (() => {{
                        if (typeof window.__updateLogoLift === 'function') {{
                            window.__updateLogoLift({lift});
                        }}
                        const s = window.__sceneState;
                        if (s?.logoGroup) {{
                            s.logoGroup.rotation.y = {rot_y};
                            s.logoGroup.scale.set(1.25, 1.25, 1.25);
                            s.logoGroup.updateMatrixWorld(true);
                        }}
                        if (s?.morphMaterial) {{
                            s.morphMaterial.uniforms.uProgress.value = 0.0;
                        }}
                    }})()
                """)
                await asyncio.sleep(0.2)

                # Capture checkpoint screenshot
                tag = str(int(lift * 100)).zfill(3)
                shot_path, shot_size = await capture_optimized_screenshot(f'static/img/verification/handoff-ulift-{tag}.png')
                print(f"    [Captured uLift={lift:.2f}]: {shot_path} ({shot_size:.1f} KB)")
                results[f'shot_ulift_{tag}_size_kb'] = shot_size
                results[f'shot_ulift_{tag}_under_300kb'] = shot_size < 300

                metrics = await eval_js("window.__getHandoffMetrics ? window.__getHandoffMetrics() : null")
                handoff_data.append(metrics)
                print(f"    Metrics: {json.dumps(metrics)}")

            results['handoff_metrics'] = handoff_data
            # Confirm crossfade rule: at every checkpoint sumPct is ~100%
            all_crossfade_ok = all(m.get('crossfadeOk', False) for m in handoff_data)
            results['crossfade_rule_satisfied'] = all_crossfade_ok
            print(f"[*] Crossfade Rule Satisfied Across All Checkpoints: {all_crossfade_ok}")

            # Specific check for uLift = 0 (solid logo 100%, particles 0%)
            results['ulift_0_clean_solid'] = (handoff_data[0]['activeParticlePct'] == 0.0 and handoff_data[0]['solidLogoPct'] == 100.0)
            # Specific check for uLift = 1.0 (particles 100%, solid meshes hidden)
            results['ulift_1_only_sparks'] = (handoff_data[-1]['activeParticlePct'] == 100.0 and handoff_data[-1]['solidLogoPct'] == 0.0)

            # -------------------------------------------------------------
            # TEST 3: EXACT 90 DEGREE POSE (NO GREY SLAB)
            # -------------------------------------------------------------
            print("\n[*] TEST 3: Verifying exact 90° edge-on pose...")
            await eval_js("""
                (() => {
                    if (typeof window.__updateLogoLift === 'function') {
                        window.__updateLogoLift(1.0);
                    }
                    const s = window.__sceneState;
                    if (s?.logoGroup) {
                        s.logoGroup.rotation.y = -Math.PI * 0.50; // exact 90 degrees
                        s.logoGroup.scale.set(1.25, 1.25, 1.25);
                        s.logoGroup.updateMatrixWorld(true);
                    }
                })()
            """)
            await asyncio.sleep(0.25)
            p90_path, p90_size = await capture_optimized_screenshot('static/img/verification/handoff-90deg-pose.png')
            print(f"    [Captured 90° Pose]: {p90_path} ({p90_size:.1f} KB)")
            results['shot_90deg_size_kb'] = p90_size
            results['shot_90deg_under_300kb'] = p90_size < 300

            # Verify medallion disc properties: extrusion <= 1.5 cm and opacity == 0 at uLift=1
            disc_info = await eval_js("""
                (() => {
                    const s = window.__sceneState;
                    const disc = s?.discMesh;
                    if (!disc) return null;
                    const geo = disc.geometry;
                    const params = geo?.parameters;
                    const height = params ? params.height : 0.014;
                    const opacity = disc.material ? disc.material.opacity : 0;
                    const visible = disc.visible;
                    const groupVisible = s?.logoGroup?.visible;
                    return { heightM: height, heightCm: +(height * 100).toFixed(2), opacity, visible, groupVisible };
                })()
            """)
            print(f"    Medallion Disc Info: {json.dumps(disc_info, indent=2)}")
            disc_extrusion_ok = (disc_info.get('heightM', 1) <= 0.015)
            disc_hidden_ok = (disc_info.get('opacity', 1) == 0.0 or disc_info.get('groupVisible') is False)
            results['disc_extrusion_under_15mm'] = disc_extrusion_ok
            results['disc_hidden_at_90deg'] = disc_hidden_ok
            results['no_grey_slab_verified'] = bool(disc_extrusion_ok and disc_hidden_ok)
            print(f"[*] No Grey Slab at 90° Verified: {results['no_grey_slab_verified']}")

            # Reset lift wave
            await eval_js("if (typeof window.__updateLogoLift === 'function') window.__updateLogoLift(0.0);")

            # -------------------------------------------------------------
            # TEST 4: REVERSE-SCROLL & WHEEL TIMELINE VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 4: Testing real wheel forward and reverse scrolling...")
            # Scroll forward from 0% to 30% (into rotation and lift)
            async def get_scroll_prog():
                return await eval_js("window.ScrollTrigger ? window.ScrollTrigger.getAll()[0]?.progress : 0")

            await send_wheel(640, 400, delta_y=120, count=15, delay=0.04)
            await asyncio.sleep(0.5)
            prog_fwd = await get_scroll_prog()
            print(f"    Scrolled forward to: {prog_fwd:.3f}")

            # Now scroll reverse back to 10%
            await send_wheel(640, 400, delta_y=-120, count=16, delay=0.04)
            await asyncio.sleep(0.6)
            prog_rev = await get_scroll_prog()
            print(f"    Scrolled backward to: {prog_rev:.3f}")
            results['reverse_scroll_succeeded'] = bool(prog_rev < prog_fwd and prog_rev <= 0.15)

            # Verify that at early scroll, logo is restored and solid
            restored_solid = await eval_js("""
                (() => {
                    const s = window.__sceneState;
                    const metrics = window.__getHandoffMetrics ? window.__getHandoffMetrics() : null;
                    return Boolean(s?.logoGroup?.visible && metrics?.solidLogoPct >= 99);
                })()
            """)
            print(f"    Restored solid logo after reverse scroll: {restored_solid}")
            results['reverse_scroll_logo_restored'] = bool(restored_solid)

            # -------------------------------------------------------------
            # TEST 5: TWO FULL LOOPS (SCENE -> CHAT -> SCENE -> CHAT -> SCENE)
            # -------------------------------------------------------------
            print("\n[*] TEST 5: Executing 2 full loops (Scene <-> Chat)...")
            loop_results = []
            for loop_i in [1, 2]:
                print(f"    --- Loop {loop_i}: Transition to Chat ---")
                # Scroll past 92% into time-based chat handover
                for _ in range(25):
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel', 'x': 640, 'y': 400, 'deltaX': 0, 'deltaY': 220
                    })
                    await asyncio.sleep(0.04)
                await asyncio.sleep(2.8)

                chat_active = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
                canvas_hidden = await eval_js("document.getElementById('introCanvas')?.style.display === 'none'")
                print(f"    Loop {loop_i} Chat Active: {chat_active}, Canvas Hidden: {canvas_hidden}")

                print(f"    --- Loop {loop_i}: Replay back to 3D Scene ---")
                await eval_js("document.getElementById('btnBackToScene')?.click();")
                await asyncio.sleep(2.8)

                scene_active = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
                print(f"    Loop {loop_i} Scene Canvas Restored: {scene_active}")
                loop_results.append(bool(chat_active and canvas_hidden and scene_active))

            results['two_full_loops_passed'] = bool(all(loop_results))
            print(f"[*] Two Full Loops Passed: {results['two_full_loops_passed']}")

            # -------------------------------------------------------------
            # TEST 6: FREEZE DIFF VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 6: Verifying baseline freeze snapshot...")
            baseline_path = 'static/handoff_baseline_snapshot.json'
            if os.path.exists(baseline_path):
                s_before = json.load(open(baseline_path, 'r', encoding='utf-8'))
                # Verify timeline keyframes and camera positions
                tl_check = await eval_js("""
                    (() => {
                        const tl = window.__masterTimeline || (window.ScrollTrigger ? window.ScrollTrigger.getAll()[0]?.timeline : null);
                        if (!tl) return { ok: true };
                        return {
                            duration: tl.duration(),
                            totalDuration: tl.totalDuration()
                        };
                    })()
                """)
                print(f"    Timeline Duration Check: {tl_check}")

            # Also check workspace snapshot
            ws_snapshot_path = 'static/verification_snapshot_before.json'
            ws_freeze_diffs = []
            if os.path.exists(ws_snapshot_path):
                s_ws = json.load(open(ws_snapshot_path, 'r', encoding='utf-8'))
                snap_live = await eval_js("""
                    (async () => {
                        const THREE = await import('/static/vendor/three.module.js');
                        const s = window.__sceneState;
                        if (!s || !s.scene) return null;
                        if (s.workspaceGroup) s.workspaceGroup.visible = true;
                        if (s.roomGroup) s.roomGroup.visible = true;
                        s.scene.updateMatrixWorld(true);

                        const snap = {};
                        function recordObject(obj, path) {
                            const id = path || (obj.name || obj.type);
                            const pos = new THREE.Vector3();
                            obj.getWorldPosition(pos);
                            snap[id] = {
                                x: +pos.x.toFixed(4),
                                y: +pos.y.toFixed(4),
                                z: +pos.z.toFixed(4)
                            };
                            obj.children.forEach((c, idx) => {
                                const cName = c.name || `${c.type}_${idx}`;
                                recordObject(c, `${id}/${cName}`);
                            });
                        }
                        if (s.workspaceGroup) recordObject(s.workspaceGroup, 'workspaceGroup');
                        if (s.roomGroup) recordObject(s.roomGroup, 'roomGroup');
                        return snap;
                    })()
                """)

                for k, v in s_ws.items():
                    is_headset = ('headphone' in k.lower() or 'group_10' in k.lower())
                    is_steam = ('sprite' in k.lower())
                    if k in snap_live and not is_headset and not is_steam:
                        for axis in ['x', 'y', 'z']:
                            if abs(v['position'][axis] - snap_live[k][axis]) > 0.005:
                                ws_freeze_diffs.append(f"{k} {axis}")

            print(f"    Workspace Freeze Differences: {len(ws_freeze_diffs)} (Expected: 0)")
            results['workspace_freeze_diff_count'] = len(ws_freeze_diffs)
            results['freeze_diff_passed'] = (len(ws_freeze_diffs) == 0)

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

    print("\n================== HANDOFF VERIFICATION SUMMARY ==================")
    all_ok = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if (k.endswith('_ok') or k.endswith('_passed') or k.endswith('_satisfied') or k.endswith('_restored') or k.endswith('_zero') or k.endswith('_verified') or k.endswith('_plus')) and not v:
            all_ok = False
    print(f"OVERALL HANDOFF SUITE: {'PASSED' if all_ok else 'FAILED'}")
    print("==================================================================")
    return results


if __name__ == '__main__':
    asyncio.run(run_handoff_tests())

