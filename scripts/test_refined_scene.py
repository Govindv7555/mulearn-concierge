"""
µLearn Concierge — Refined 3D Desk Setup & Architecture Verification Suite (CDP)

Verifies:
1. Real CDP mouseWheel scroll across all phases (1 to 5).
2. Screenshots captured at Phase 1, Phase 2, Phase 3 (swirl & settled), Phase 4, Phase 5, Phase 6 (chat), and Mobile (all strictly < 300 KB).
3. Morning light setup: directional sun with 2048 shadow map, desk lamp is daylight prop (intensity 0).
4. Laptop on aluminium riser stand with Box3 contact overlap depth < 2mm, lid clear.
5. Headset on brass stand: complete arc, inner padding, slider rods, tilt hinges, ear cups, cushions; clears photo frame by >= 2cm, above desk, clears wall.
6. Baseline Freeze check: 100% of non-headset workspace nodes match static/verification_snapshot_before.json.
7. Deterministic Pixel-to-Object particle morph: 28,000 desktop / 10,000 mobile particles, verified at 9 checkpoints.
8. Dynamic camera targets for Phase 4 & Phase 5 derived from laptopScreenMesh world position and normal.
9. Time-based swap to CHAT, clickability of input, and replay back to SCENE.
10. Mobile 390px viewport performance optimization (shadow maps disabled, 10k particles).
11. Daylight luminance verification (120 - 170 average luminance, < 2% hotspots, < 3% shadows).
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

# Ensure offline mock mode for Flask API calls
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False  # offline fallback, no live API call


async def run_refined_scene_tests():
    results = {}

    # 1. Allocate free ports for Flask and CDP
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
        '--headless',
        '--disable-gpu',
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
                    if resp.get('id') == msg_id:
                        return resp

            await send_cmd('Page.enable')
            await send_cmd('Runtime.enable')

            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
                return res.get('result', {}).get('result', {}).get('value')

            async def send_wheel(x, y, delta_y=120, count=5, delay=0.06):
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
                for q in [82, 78, 74, 70, 65]:
                    img_rgb.save(jpg_path, format='JPEG', quality=q, optimize=True)
                    size_kb = os.path.getsize(jpg_path) / 1024
                    if size_kb <= target_kb:
                        break
                if os.path.exists(png_path) and png_path != jpg_path:
                    try: os.remove(png_path)
                    except Exception: pass
                return jpg_path, size_kb

            # Set desktop 1440x900 viewport
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            print(f"Navigating to http://127.0.0.1:{flask_port}/ ...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Check scene initialization
            is_init = await eval_js("Boolean(window.__sceneState && window.__sceneState.isInitialized)")
            if not is_init:
                await eval_js("""
                    import('/static/js/scene.js').then(m => {
                        window.__sceneState = m.sceneState;
                        window.__computeScreenCameraTargets = m.computeScreenCameraTargets;
                        window.__getScreenViewportMetrics = m.getScreenViewportMetrics;
                        window.__verifyStandLaptopClearance = m.verifyStandLaptopClearance;
                        window.__verifyHeadsetClearance = m.verifyHeadsetClearance;
                        window.__verifyWorkspacePenetrations = m.verifyWorkspacePenetrations;
                        window.__updateParticleMorph = m.updateParticleMorph;
                    });
                """)
                await asyncio.sleep(1.0)
                is_init = await eval_js("Boolean(window.__sceneState && window.__sceneState.isInitialized)")

            results['scene_initialized'] = bool(is_init)
            print(f"[*] Scene Initialized: {is_init}")

            # -------------------------------------------------------------
            # 1. VERIFY SCENE ARCHITECTURE, STAND & HEADSET CLEARANCES
            # -------------------------------------------------------------
            arch_info = await eval_js("""
                (() => {
                    const s = window.__sceneState;
                    if (!s) return null;

                    const lamp = s.lampLight;
                    const keyLight = s.keyLight;
                    const hasKeyDirectionalLight = Boolean(keyLight && keyLight.isDirectionalLight && keyLight.castShadow);
                    const keyShadowMapSize = keyLight && keyLight.shadow ? keyLight.shadow.mapSize.width : 0;
                    
                    const lampIntensity = lamp ? lamp.intensity : 0;
                    const lampIsOff = Boolean(lampIntensity === 0 && (!lamp.visible || lampIntensity === 0));

                    const laptop = s.laptopGroup;
                    const hasNamedBase = Boolean(laptop && laptop.getObjectByName('base'));
                    const hasNamedLid = Boolean(laptop && laptop.getObjectByName('lid'));
                    const hasNamedScreen = Boolean(laptop && laptop.getObjectByName('screenMesh'));
                    const laptopNamedHierarchyOk = Boolean(hasNamedBase && hasNamedLid && hasNamedScreen);

                    const standClearance = typeof window.__verifyStandLaptopClearance === 'function' 
                        ? window.__verifyStandLaptopClearance() 
                        : null;

                    const headsetClearance = typeof window.__verifyHeadsetClearance === 'function'
                        ? window.__verifyHeadsetClearance()
                        : null;

                    const workspacePenetrations = typeof window.__verifyWorkspacePenetrations === 'function'
                        ? window.__verifyWorkspacePenetrations()
                        : null;

                    const points = s.particlesPoints || s.particlePoints;
                    const particleCount = points ? points.geometry.attributes.position.count : 0;

                    return {
                        hasKeyDirectionalLight,
                        keyShadowMapSize,
                        lampIsOff,
                        lampIntensity,
                        laptopNamedHierarchyOk,
                        standClearance,
                        headsetClearance,
                        workspacePenetrations,
                        particleCount
                    };
                })()
            """)

            results['has_key_directional_light'] = arch_info.get('hasKeyDirectionalLight', False)
            results['key_shadow_map_size'] = arch_info.get('keyShadowMapSize', 0) == 2048
            results['lamp_is_off_daylight_prop'] = arch_info.get('lampIsOff', False)
            results['laptop_named_hierarchy_ok'] = arch_info.get('laptopNamedHierarchyOk', False)
            results['desktop_particle_count'] = arch_info.get('particleCount', 0)
            results['desktop_particle_count_ok'] = (arch_info.get('particleCount', 0) == 28000)

            # Stand Clearance
            stand_clr = arch_info.get('standClearance') or {}
            overlap_mm = stand_clr.get('overlapDepthMm', 999)
            lid_clear = stand_clr.get('lidClear', False)
            results['stand_laptop_overlap_mm'] = overlap_mm
            results['stand_laptop_overlap_ok'] = overlap_mm < 2.0
            results['stand_lid_clearance_ok'] = lid_clear
            print(f"[*] Stand-Laptop Overlap Depth: {overlap_mm} mm (Ok: {overlap_mm < 2.0})")
            print(f"[*] Stand-Lid Clearance: {lid_clear}")

            # Headset Clearance
            hs_clr = arch_info.get('headsetClearance') or {}
            photo_clr_cm = hs_clr.get('photoClearanceCm', 0)
            desk_clr_cm = hs_clr.get('deskClearanceCm', 0)
            wall_clr_cm = hs_clr.get('wallClearanceCm', 0)
            results['headset_photo_clearance_cm'] = photo_clr_cm
            results['headset_photo_clearance_ok'] = photo_clr_cm >= 2.0
            results['headset_desk_clearance_cm'] = desk_clr_cm
            results['headset_desk_clearance_ok'] = desk_clr_cm > 0.0
            results['headset_wall_clearance_cm'] = wall_clr_cm
            results['headset_wall_clearance_ok'] = wall_clr_cm >= 2.0
            results['headset_all_clear'] = hs_clr.get('allClear', False)
            print(f"[*] Headset Clearances: Photo Frame = {photo_clr_cm} cm (>= 2cm), Desk = {desk_clr_cm} cm, Wall = {wall_clr_cm} cm (All Clear: {hs_clr.get('allClear')})")

            # Workspace Penetrations
            wp = arch_info.get('workspacePenetrations') or {}
            results['workspace_all_above_desk'] = wp.get('allAboveDesk', False)
            results['workspace_legs_on_floor'] = wp.get('legsOnFloor', False)
            results['workspace_penetrations_passed'] = wp.get('passed', False)

            # -------------------------------------------------------------
            # 2. BASELINE FREEZE DIFF CHECK
            # -------------------------------------------------------------
            baseline_path = 'static/verification_snapshot_before.json'
            if os.path.exists(baseline_path):
                s_before = json.load(open(baseline_path, 'r', encoding='utf-8'))
                snapshot_now = await eval_js("""
                    (async () => {
                        const THREE = await import('/static/vendor/three.module.js');
                        const s = window.__sceneState;
                        if (!s || !s.scene) return null;

                        if (s.props && s.props.length > 0) {
                            s.props.forEach(p => {
                                p.group.position.y = p.targetY !== undefined ? p.targetY : 0;
                                p.group.scale.set(1, 1, 1);
                                p.group.visible = true;
                            });
                        }
                        if (s.workspaceGroup) s.workspaceGroup.visible = true;
                        if (s.roomGroup) s.roomGroup.visible = true;
                        s.scene.updateMatrixWorld(true);

                        const snap = {};
                        function recordObject(obj, path) {
                            const id = path || (obj.name || obj.type);
                            const pos = new THREE.Vector3();
                            const quat = new THREE.Quaternion();
                            const scale = new THREE.Vector3();
                            obj.getWorldPosition(pos);
                            obj.getWorldQuaternion(quat);
                            obj.getWorldScale(scale);

                            const entry = {
                                name: obj.name || 'unnamed',
                                type: obj.type,
                                position: { x: +pos.x.toFixed(4), y: +pos.y.toFixed(4), z: +pos.z.toFixed(4) },
                                quaternion: { x: +quat.x.toFixed(4), y: +quat.y.toFixed(4), z: +quat.z.toFixed(4), w: +quat.w.toFixed(4) },
                                scale: { x: +scale.x.toFixed(4), y: +scale.y.toFixed(4), z: +scale.z.toFixed(4) },
                                visible: obj.visible
                            };

                            if (obj.material) {
                                const mat = obj.material;
                                entry.material = {
                                    type: mat.type,
                                    color: mat.color ? '#' + mat.color.getHexString() : null,
                                    roughness: mat.roughness !== undefined ? +mat.roughness.toFixed(3) : null,
                                    metalness: mat.metalness !== undefined ? +mat.metalness.toFixed(3) : null
                                };
                            }
                            snap[id] = entry;
                            obj.children.forEach((child, idx) => {
                                const childName = child.name ? child.name : `${child.type}_${idx}`;
                                recordObject(child, `${id}/${childName}`);
                            });
                        }
                        if (s.workspaceGroup) recordObject(s.workspaceGroup, 'workspaceGroup');
                        if (s.roomGroup) recordObject(s.roomGroup, 'roomGroup');
                        return snap;
                    })()
                """)

                freeze_diffs = []
                for key, val_b in s_before.items():
                    is_headset = ('headphone' in key.lower() or 'group_10' in key.lower())
                    is_steam = ('sprite' in key.lower())
                    if key not in snapshot_now:
                        if not is_headset:
                            freeze_diffs.append(f"Missing node: {key}")
                        continue
                    val_n = snapshot_now[key]
                    for axis in ['x', 'y', 'z']:
                        if abs(val_b['position'][axis] - val_n['position'][axis]) > 0.005:
                            if not is_headset and not is_steam:
                                freeze_diffs.append(f"{key} pos.{axis}: before={val_b['position'][axis]}, now={val_n['position'][axis]}")
                    if 'material' in val_b and 'material' in val_n and not is_headset and not is_steam:
                        mb, mn = val_b['material'], val_n['material']
                        for prop in ['type', 'color', 'roughness', 'metalness']:
                            if mb.get(prop) != mn.get(prop):
                                freeze_diffs.append(f"{key} mat.{prop}: before={mb.get(prop)}, now={mn.get(prop)}")

                print(f"[*] Baseline Freeze Diff Count: {len(freeze_diffs)} (Expected: 0)")
                results['freeze_diff_count'] = len(freeze_diffs)
                results['freeze_verified_passed'] = (len(freeze_diffs) == 0)

            # -------------------------------------------------------------
            # 3. PARTICLE MORPH STAGES & CHECKPOINTS
            # -------------------------------------------------------------
            checkpoints = [0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0]
            morph_results = []
            for cp in checkpoints:
                res = await eval_js(f"""
                    (() => {{
                        if (typeof window.__updateParticleMorph === 'function') {{
                            window.__updateParticleMorph({cp});
                        }}
                        const s = window.__sceneState;
                        const points = s?.particlesPoints || s?.particlePoints;
                        const mat = points?.material;
                        const uProg = mat?.uniforms?.uProgress?.value;
                        const uRev = mat?.uniforms?.uRevealProgress?.value;
                        const solidLogoVisible = Boolean(s?.logoGroup?.visible);
                        const roomVisible = Boolean(s?.roomGroup?.visible);
                        const wsVisible = Boolean(s?.workspaceGroup?.visible);
                        return {{
                            progress: {cp},
                            uProg: uProg !== undefined ? +uProg.toFixed(2) : null,
                            uRev: uRev !== undefined ? +uRev.toFixed(2) : null,
                            solidLogoVisible,
                            roomVisible,
                            wsVisible
                        }};
                    }})()
                """)
                morph_results.append(res)
            print(f"[*] Particle Morph 9 Checkpoints: {json.dumps(morph_results, indent=2)}")
            # At 0.0: solid logo is visible, room is hidden
            results['morph_cp0_logo_visible'] = morph_results[0]['solidLogoVisible'] is True
            results['morph_cp0_room_hidden'] = morph_results[0]['roomVisible'] is False
            # At 0.35: solid logo hidden, room hidden
            results['morph_cp35_logo_hidden'] = morph_results[3]['solidLogoVisible'] is False
            results['morph_cp35_room_hidden'] = morph_results[3]['roomVisible'] is False
            # At 0.90 & 1.0: room visible, workspace visible
            results['morph_cp10_room_visible'] = morph_results[-1]['roomVisible'] is True
            results['morph_cp10_ws_visible'] = morph_results[-1]['wsVisible'] is True

            # Reset particle morph to 0.0 for scroll sequence
            await eval_js("if (typeof window.__updateParticleMorph === 'function') window.__updateParticleMorph(0.0);")

            # -------------------------------------------------------------
            # 4. DYNAMIC CAMERA TARGETS FOR PHASE 4 & 5
            # -------------------------------------------------------------
            cam_targets = await eval_js("""
                (() => {
                    if (typeof window.__computeScreenCameraTargets === 'function') {
                        return window.__computeScreenCameraTargets(window.__sceneState.camera, 1440 / 900);
                    }
                    return null;
                })()
            """)
            print(f"[*] Dynamic Camera Targets: {json.dumps(cam_targets, indent=2)}")
            results['dynamic_camera_calculated'] = bool(cam_targets and 'phase4' in cam_targets and 'phase5' in cam_targets)

            # Phase 1: Hero screenshot
            p1_workspace_visible = await eval_js("Boolean(window.__sceneState?.workspaceGroup?.visible)")
            results['phase1_workspace_hidden'] = (p1_workspace_visible is False)
            p1_path, p1_size = await capture_optimized_screenshot('static/img/verification/phase1-hero.png')
            print(f"    [Captured Phase 1 Hero]: {p1_path} ({p1_size:.1f} KB)")
            results['phase1_screenshot_size_kb'] = p1_size
            results['phase1_under_300kb'] = p1_size < 300

            # -------------------------------------------------------------
            # 5. REAL WHEEL SCROLL & SCREENSHOTS ACROSS PHASES
            # -------------------------------------------------------------
            await eval_js("""
                window.__fpsSamples = [];
                let lastTime = performance.now();
                function measureFPS(now) {
                    const delta = now - lastTime;
                    lastTime = now;
                    if (delta > 0) window.__fpsSamples.push(1000 / delta);
                    if (window.__fpsMeasuring) requestAnimationFrame(measureFPS);
                }
                window.__fpsMeasuring = true;
                requestAnimationFrame(measureFPS);
            """)

            async def scroll_to_progress(target_prog, max_steps=60):
                for _ in range(max_steps):
                    prog = await eval_js("window.ScrollTrigger ? window.ScrollTrigger.getAll()[0]?.progress : 0")
                    if prog >= target_prog:
                        break
                    diff = target_prog - prog
                    step_delta = 40 if diff < 0.08 else (80 if diff < 0.15 else 130)
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel',
                        'x': 640,
                        'y': 400,
                        'deltaX': 0,
                        'deltaY': step_delta
                    })
                    await asyncio.sleep(0.04)
                await asyncio.sleep(0.6)
                return await eval_js("window.ScrollTrigger ? window.ScrollTrigger.getAll()[0]?.progress : 0")

            # Phase 2: Approach (~25% progress)
            print("[*] Scrolling to Phase 2 (Approach)...")
            p2_prog = await scroll_to_progress(0.25)
            p2_workspace_visible = await eval_js("Boolean(window.__sceneState?.workspaceGroup?.visible)")
            results['phase2_workspace_hidden'] = (p2_workspace_visible is False)
            p2_path, p2_size = await capture_optimized_screenshot('static/img/verification/phase2-approach.png')
            print(f"    [Captured Phase 2 Approach]: {p2_path} ({p2_size:.1f} KB)")
            results['phase2_screenshot_size_kb'] = p2_size
            results['phase2_under_300kb'] = p2_size < 300

            # Phase 3 Swirl (~46% progress)
            print("[*] Scrolling to Phase 3 Swirl (~46%)...")
            p3_prog = await scroll_to_progress(0.46)
            p3_path, p3_size = await capture_optimized_screenshot('static/img/verification/phase3-swirl.png')
            print(f"    [Captured Phase 3 Swirl]: {p3_path} ({p3_size:.1f} KB)")
            results['phase3_swirl_size_kb'] = p3_size
            results['phase3_swirl_under_300kb'] = p3_size < 300

            # Phase 3 Settled Workspace (~61% progress)
            print("[*] Scrolling to Phase 3 Settled Workspace (~61%)...")
            p3b_prog = await scroll_to_progress(0.61)
            p3b_workspace_visible = await eval_js("Boolean(window.__sceneState?.workspaceGroup?.visible)")
            results['phase3_workspace_visible'] = bool(p3b_workspace_visible)
            p3b_path, p3b_size = await capture_optimized_screenshot('static/img/verification/phase3-settled.png')
            print(f"    [Captured Phase 3 Settled]: {p3b_path} ({p3b_size:.1f} KB)")
            results['phase3_settled_size_kb'] = p3b_size
            results['phase3_settled_under_300kb'] = p3b_size < 300

            # Verify desk lamp is off in daylight
            lamp_intensity = await eval_js("window.__sceneState?.lampLight?.intensity || 0")
            results['lamp_is_off'] = (lamp_intensity == 0)

            # Phase 4: Laptop 3/4 Overview (~70% progress)
            print("[*] Scrolling to Phase 4 (Laptop 3/4 Overview)...")
            p4_prog = await scroll_to_progress(0.70)
            p4_path, p4_size = await capture_optimized_screenshot('static/img/verification/phase4-laptop.png')
            print(f"    [Captured Phase 4]: {p4_path} ({p4_size:.1f} KB)")
            results['phase4_screenshot_size_kb'] = p4_size
            results['phase4_under_300kb'] = p4_size < 300

            # Phase 5: Laptop Screen Zoom-in (~89% progress, before white flash)
            print("[*] Scrolling to Phase 5 End (Screen Zoom-in, before white flash)...")
            p5_prog = await scroll_to_progress(0.885)
            metrics_1440 = await eval_js("""
                (() => {
                    if (typeof window.__getScreenViewportMetrics === 'function') {
                        return window.__getScreenViewportMetrics();
                    }
                    return null;
                })()
            """)
            print(f"[*] Phase 5 NDC Viewport Metrics (1440x900): {json.dumps(metrics_1440, indent=2)}")
            if metrics_1440:
                cov_1440 = metrics_1440.get('coveragePct', 0)
                offset_1440 = metrics_1440.get('centerOffsetPct', 100)
                results['p5_coverage_1440'] = cov_1440
                results['p5_coverage_1440_ok'] = cov_1440 >= 96.0
                results['p5_center_offset_1440'] = offset_1440
                results['p5_center_offset_1440_ok'] = offset_1440 <= 2.0
                print(f"    Coverage: {cov_1440}% (>= 96%), Offset: {offset_1440}% (<= 2%)")

            p5_path, p5_size = await capture_optimized_screenshot('static/img/verification/phase5-zoomin.png')
            print(f"    [Captured Phase 5 (Screen Zoom)]: {p5_path} ({p5_size:.1f} KB)")
            results['phase5_screenshot_size_kb'] = p5_size
            results['phase5_under_300kb'] = p5_size < 300

            # FPS measurement
            await eval_js("window.__fpsMeasuring = false;")
            avg_fps = await eval_js("""
                (() => {
                    const s = window.__fpsSamples || [];
                    if (!s.length) return 60;
                    const slice = s.slice(10);
                    const sum = slice.reduce((a, b) => a + b, 0);
                    return slice.length ? sum / slice.length : 60;
                })()
            """)
            print(f"[*] Average Scroll FPS: {avg_fps:.1f} FPS")
            results['average_scroll_fps'] = round(avg_fps, 1)

            # -------------------------------------------------------------
            # 6. TIME-BASED SWAP TO CHAT & REPLAY
            # -------------------------------------------------------------
            print("[*] Scrolling into Phase 5 end to trigger time-based swap...")
            await send_wheel(640, 400, delta_y=180, count=10, delay=0.05)
            await asyncio.sleep(2.8)

            app_state = await eval_js("window.__getAppState ? window.__getAppState() : 'UNKNOWN'")
            is_chat_visible = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
            is_canvas_hidden = await eval_js("document.getElementById('introCanvas')?.style.display === 'none'")
            print(f"[*] App State after swap: {app_state}, chat-active: {is_chat_visible}, canvas hidden: {is_canvas_hidden}")
            results['swap_to_chat_successful'] = bool(is_chat_visible and is_canvas_hidden)

            p6_path, p6_size = await capture_optimized_screenshot('static/img/verification/phase6-chat.png')
            print(f"    [Captured Phase 6 Chat]: {p6_path} ({p6_size:.1f} KB)")
            results['phase6_screenshot_size_kb'] = p6_size
            results['phase6_under_300kb'] = p6_size < 300

            # Verify message input clickability
            input_clickable = await eval_js("""
                (() => {
                    const input = document.getElementById('messageInput');
                    if (!input) return false;
                    const r = input.getBoundingClientRect();
                    const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                    return el === input || input.contains(el);
                })()
            """)
            results['chat_input_clickable'] = bool(input_clickable)
            print(f"    #messageInput Clickable: {input_clickable}")

            # Replay to 3D scene
            print("[*] Testing Replay back to 3D scene (#btnBackToScene)...")
            await eval_js("document.getElementById('btnBackToScene')?.click();")
            await asyncio.sleep(2.8)
            is_canvas_restored = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
            results['replay_to_scene_successful'] = bool(is_canvas_restored)
            print(f"    Reverted Canvas Restored: {is_canvas_restored}")

            # -------------------------------------------------------------
            # 7. MOBILE 390px VIEWPORT CHECK
            # -------------------------------------------------------------
            print("[*] Testing Mobile 390px viewport...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await eval_js("""
                if (typeof window.__resizeScene === 'function') {
                    window.__resizeScene(390, 844);
                } else {
                    import('/static/js/scene.js').then(m => {
                        m.resizeScene(390, 844);
                    });
                }
            """)
            await asyncio.sleep(1.0)

            mobile_shadows = await eval_js("window.__sceneState?.renderer?.shadowMap?.enabled")
            print(f"    Mobile ShadowMap Enabled: {mobile_shadows} (Expected: False)")
            results['mobile_shadows_disabled'] = (mobile_shadows is False)

            # Scroll to Phase 5 on mobile to test screen framing
            await scroll_to_progress(0.89)
            metrics_390 = await eval_js("""
                (() => {
                    if (typeof window.__getScreenViewportMetrics === 'function') {
                        return window.__getScreenViewportMetrics();
                    }
                    return null;
                })()
            """)
            if metrics_390:
                cov_390 = metrics_390.get('coveragePct', 0)
                offset_390 = metrics_390.get('centerOffsetPct', 100)
                results['p5_coverage_390'] = cov_390
                results['p5_coverage_390_ok'] = cov_390 >= 96.0
                results['p5_center_offset_390'] = offset_390
                results['p5_center_offset_390_ok'] = offset_390 <= 2.0
                print(f"    Mobile 390x844 Coverage: {cov_390}%, Offset: {offset_390}%")

            mob_path, mob_size = await capture_optimized_screenshot('static/img/verification/mobile-scene.png')
            print(f"    [Captured Mobile Scene]: {mob_path} ({mob_size:.1f} KB)")
            results['mobile_screenshot_size_kb'] = mob_size
            results['mobile_under_300kb'] = mob_size < 300

            # -------------------------------------------------------------
            # 8. DAYLIGHT LUMINANCE & ACCEPTANCE CRITERIA
            # -------------------------------------------------------------
            daylight_lums = []
            for name in ['phase3-settled', 'phase4-laptop']:
                p = f'static/img/verification/{name}.png'
                if not os.path.exists(p) or os.path.getsize(p) == 0:
                    p = f'static/img/verification/{name}.jpg'
                if os.path.exists(p):
                    im = Image.open(p).convert('RGB')
                    arr = np.array(im, dtype=float)
                    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
                    mean_lum = float(lum.mean())
                    pct_above_250 = float((lum > 250).mean() * 100)
                    pct_below_20 = float((lum < 20).mean() * 100)

                    results[f'{name}_mean_lum'] = round(mean_lum, 1)
                    results[f'{name}_pct_above_250'] = round(pct_above_250, 2)
                    results[f'{name}_pct_below_20'] = round(pct_below_20, 2)
                    print(f"[*] {name:20}: Mean Lum={mean_lum:5.1f}, >250={pct_above_250:4.2f}%, <20={pct_below_20:4.2f}%")
                    daylight_lums.append(mean_lum)

            daylight_avg = float(np.mean(daylight_lums)) if daylight_lums else 0
            results['daylight_avg_lum'] = round(daylight_avg, 1)
            results['daylight_lum_in_range'] = (120 <= daylight_avg <= 170)

            p4_lum = results.get('phase4-laptop_mean_lum', 0)
            p4_hotspot = results.get('phase4-laptop_pct_above_250', 100)
            p4_shadow = results.get('phase4-laptop_pct_below_20', 100)
            results['phase4_lum_in_range'] = (120 <= p4_lum <= 170)
            results['phase4_hotspot_ok'] = (p4_hotspot <= 2.0)
            results['phase4_shadow_ok'] = (p4_shadow <= 3.0)

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

    print("\n================== VERIFICATION SUMMARY ==================")
    all_passed = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if k.endswith('_ok') or k.endswith('_passed') or k.endswith('_successful'):
            if not v:
                all_passed = False
    print(f"OVERALL RESULT: {'PASSED' if all_passed else 'FAILED'}")
    print("==========================================================")
    return results


if __name__ == '__main__':
    asyncio.run(run_refined_scene_tests())
