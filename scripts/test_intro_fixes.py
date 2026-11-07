"""
Comprehensive Automated Test Suite for 3D Intro & Smooth Scroll Fixes.
Uses Chrome DevTools Protocol (CDP) to drive headless Edge.
Tests real wheel input, reverse scrubbing, chat containment, keyboard, mobile, and reduced motion.
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

async def run_all_tests():
    results = {}

    # 1. Start background Flask server on free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(1.2)

    # 2. Start Headless Edge with remote debugging
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
            await send_cmd('Console.enable')

            # Set viewport to 1280x800
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1280,
                'height': 800,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            # Navigate to Flask app
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.0)

            # Helper to evaluate JS expression
            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
                return res.get('result', {}).get('result', {}).get('value')

            # Helper to dispatch mouseWheel
            async def send_wheel(x, y, delta_y=120, count=5, delay=0.08):
                for _ in range(count):
                    await send_cmd('Input.dispatchMouseEvent', {
                        'type': 'mouseWheel',
                        'x': x,
                        'y': y,
                        'deltaX': 0,
                        'deltaY': delta_y
                    })
                    await asyncio.sleep(delay)
                await asyncio.sleep(0.6)

            # Helper to capture screenshot
            async def capture_shot(filename):
                os.makedirs('static/img/verification', exist_ok=True)
                shot_res = await send_cmd('Page.captureScreenshot', {'format': 'png'})
                data = base64.b64decode(shot_res['result']['data'])
                out_path = os.path.join('static', 'img', 'verification', filename)
                with open(out_path, 'wb') as f:
                    f.write(data)
                size_kb = os.path.getsize(out_path) / 1024
                print(f"Captured {filename}: {size_kb:.1f} KB")
                return size_kb

            print("\n=== RUNNING MANDATORY TEST SUITE ===")

            # -------------------------------------------------------------
            # TEST 1: Real wheel input at top of page
            # -------------------------------------------------------------
            print("\n[Test 1] Real wheel input at top of page...")
            s0 = await eval_js('window.scrollY')
            await send_wheel(x=640, y=400, delta_y=120, count=6)
            s1 = await eval_js('window.scrollY')
            prog1 = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            test1_pass = s1 > s0 and prog1 > 0
            results['Wheel at top of page (advances timeline)'] = (
                f"PASS (scrollY: {s0} -> {s1}, progress: {prog1:.3f})" if test1_pass
                else f"FAIL (scrollY: {s0} -> {s1})"
            )
            print(results['Wheel at top of page (advances timeline)'])

            # -------------------------------------------------------------
            # TEST 2: Real wheel input mid-scene (~45% scroll)
            # -------------------------------------------------------------
            print("\n[Test 2] Real wheel input mid-scene (progress ~0.45)...")
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const mid = st.start + 0.45 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(mid, { immediate: true });
                    else window.scrollTo(0, mid);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.4)
            s_mid0 = await eval_js('window.scrollY')
            await send_wheel(x=640, y=400, delta_y=120, count=6)
            s_mid1 = await eval_js('window.scrollY')
            test2_pass = s_mid1 > s_mid0
            results['Wheel mid-scene (advances timeline)'] = (
                f"PASS (scrollY: {s_mid0} -> {s_mid1})" if test2_pass
                else f"FAIL (scrollY: {s_mid0} -> {s_mid1})"
            )
            print(results['Wheel mid-scene (advances timeline)'])

            # -------------------------------------------------------------
            # TEST 3: Real wheel input near end of scene (phase 5 zoom, progress ~0.85)
            # -------------------------------------------------------------
            print("\n[Test 3] Real wheel input near end of scene (phase 5 zoom, progress ~0.85)...")
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const p85 = st.start + 0.85 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(p85, { immediate: true });
                    else window.scrollTo(0, p85);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.4)
            s_end0 = await eval_js('window.scrollY')
            chat_vis_end0 = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            chat_op_end0 = await eval_js('getComputedStyle(document.getElementById("chat")).opacity')
            await send_wheel(x=640, y=400, delta_y=120, count=6)
            s_end1 = await eval_js('window.scrollY')
            test3_pass = s_end1 > s_end0 and chat_vis_end0 == 'hidden' and float(chat_op_end0) == 0.0
            results['Wheel near end of scene (chat hidden during zoom)'] = (
                f"PASS (scrollY: {s_end0} -> {s_end1}, chat visibility: {chat_vis_end0})" if test3_pass
                else f"FAIL (scrollY: {s_end0} -> {s_end1}, chat: {chat_vis_end0})"
            )
            print(results['Wheel near end of scene (chat hidden during zoom)'])

            # Capture new Phase 4, Phase 5, Phase 6 screenshots
            print("\nCapturing updated screenshots for phases 4, 5, 6...")
            # Phase 4 (65%)
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const p65 = st.start + 0.65 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(p65, { immediate: true });
                    else window.scrollTo(0, p65);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.8)
            sz4 = await capture_shot('phase4-laptop.png')

            # Phase 5 (85%)
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const p85 = st.start + 0.85 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(p85, { immediate: true });
                    else window.scrollTo(0, p85);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.8)
            sz5 = await capture_shot('phase5-zoomin.png')

            # Phase 6 (100% - live chat)
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    if (window.lenis) window.lenis.scrollTo(st.end, { immediate: true });
                    else window.scrollTo(0, st.end);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.8)
            sz6 = await capture_shot('phase6-chat.png')

            test_shots_pass = sz4 < 300 and sz5 < 300 and sz6 < 300
            results['Screenshots under 300 KB'] = (
                f"PASS (P4: {sz4:.1f}KB, P5: {sz5:.1f}KB, P6: {sz6:.1f}KB)" if test_shots_pass
                else f"FAIL"
            )

            # -------------------------------------------------------------
            # TEST 4: Wheel over chat message list (page must NOT scroll)
            # -------------------------------------------------------------
            print("\n[Test 4] Wheel over chat message list containment...")
            # Scroll directly into #chat section
            await eval_js('''
                (() => {
                    const chat = document.getElementById("chat");
                    if (window.lenis) window.lenis.scrollTo(chat.offsetTop, { immediate: true });
                    else window.scrollTo(0, chat.offsetTop);
                })()
            ''')
            await asyncio.sleep(0.5)

            msg_box = await eval_js('''
                (() => {
                    const el = document.getElementById("chatMessages");
                    const rect = el.getBoundingClientRect();
                    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                })()
            ''')
            print(f"Chat messages center: {msg_box}")
            scroll_before = await eval_js('window.scrollY')
            # Dispatch wheel events directly inside chatMessages
            await send_wheel(x=int(msg_box['x']), y=int(msg_box['y']), delta_y=120, count=5)
            scroll_after = await eval_js('window.scrollY')
            test4_pass = abs(scroll_after - scroll_before) < 5
            results['Wheel over chat message list does NOT scroll page'] = (
                f"PASS (page scroll stayed at {scroll_after}px)" if test4_pass
                else f"FAIL (page scrolled: {scroll_before} -> {scroll_after})"
            )
            print(results['Wheel over chat message list does NOT scroll page'])

            # -------------------------------------------------------------
            # TEST 5: Full Reverse Scroll (100% -> 0%)
            # -------------------------------------------------------------
            print("\n[Test 5] Reverse scroll from 100% back to top (0%)...")
            # Smooth scroll back up via Lenis
            await eval_js('if (window.lenis) window.lenis.scrollTo(0, { duration: 1.5 }); else window.scrollTo({ top: 0, behavior: "smooth" });')
            await asyncio.sleep(2.0)
            rev_s = await eval_js('window.scrollY')
            chat_vis_rev = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            rev_prog = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            test5_pass = rev_s < 20 and rev_prog < 0.05 and chat_vis_rev == 'hidden'
            results['Reversible scroll (back to 0, chat hidden)'] = (
                f"PASS (scrollY: {rev_s}, progress: {rev_prog:.3f}, chat visibility: {chat_vis_rev})" if test5_pass
                else f"FAIL (scrollY: {rev_s}, progress: {rev_prog:.3f}, chat: {chat_vis_rev})"
            )
            print(results['Reversible scroll (back to 0, chat hidden)'])

            # -------------------------------------------------------------
            # TEST 6: Keyboard scrolling (PageDown / ArrowDown)
            # -------------------------------------------------------------
            print("\n[Test 6] Keyboard scrolling...")
            k0 = await eval_js('window.scrollY')
            # Dispatch PageDown
            await send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'windowsVirtualKeyCode': 34, 'code': 'PageDown', 'key': 'PageDown'})
            await send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'windowsVirtualKeyCode': 34, 'code': 'PageDown', 'key': 'PageDown'})
            await asyncio.sleep(0.5)
            # Dispatch ArrowDown a few times
            for _ in range(4):
                await send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'windowsVirtualKeyCode': 40, 'code': 'ArrowDown', 'key': 'ArrowDown'})
                await send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'windowsVirtualKeyCode': 40, 'code': 'ArrowDown', 'key': 'ArrowDown'})
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.8)
            k1 = await eval_js('window.scrollY')
            test6_pass = k1 > k0
            results['Keyboard scrolling (PageDown / Arrows)'] = (
                f"PASS (scrollY: {k0} -> {k1})" if test6_pass
                else f"FAIL (scrollY: {k0} -> {k1})"
            )
            print(results['Keyboard scrolling (PageDown / Arrows)'])

            # -------------------------------------------------------------
            # TEST 7: Skip Intro button
            # -------------------------------------------------------------
            print("\n[Test 7] Skip Intro button...")
            await eval_js('if (window.lenis) window.lenis.scrollTo(0, { immediate: true }); else window.scrollTo(0, 0);')
            await asyncio.sleep(0.4)
            await eval_js('document.getElementById("btnSkipIntro").click();')
            await asyncio.sleep(1.8)
            skip_s = await eval_js('window.scrollY')
            skip_chat_vis = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            test7_pass = skip_s > 3000 and skip_chat_vis == 'visible'
            results['Skip intro button (jumps and reveals #chat)'] = (
                f"PASS (scrollY: {skip_s}, chat: {skip_chat_vis})" if test7_pass
                else f"FAIL (scrollY: {skip_s}, chat: {skip_chat_vis})"
            )
            print(results['Skip intro button (jumps and reveals #chat)'])

            # -------------------------------------------------------------
            # TEST 8: Mobile Touch Emulation (390px width)
            # -------------------------------------------------------------
            print("\n[Test 8] Mobile touch emulation (390x844)...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await send_cmd('Emulation.setTouchEmulationEnabled', {'enabled': True})
            await eval_js('window.scrollTo(0, 0); if (window.lenis) window.lenis.scrollTo(0, { immediate: true });')
            await asyncio.sleep(0.5)

            # Send touch scroll gesture
            await send_cmd('Input.dispatchTouchEvent', {
                'type': 'touchStart',
                'touchPoints': [{'x': 195, 'y': 600}]
            })
            await asyncio.sleep(0.05)
            for step in range(5):
                await send_cmd('Input.dispatchTouchEvent', {
                    'type': 'touchMove',
                    'touchPoints': [{'x': 195, 'y': 600 - (step + 1) * 60}]
                })
                await asyncio.sleep(0.04)
            await send_cmd('Input.dispatchTouchEvent', {
                'type': 'touchEnd',
                'touchPoints': []
            })
            await asyncio.sleep(1.0)
            mob_s = await eval_js('window.scrollY')
            test8_pass = mob_s > 0
            results['Touch emulation on 390px mobile'] = (
                f"PASS (scrollY: {mob_s})" if test8_pass
                else f"FAIL (scrollY: {mob_s})"
            )
            print(results['Touch emulation on 390px mobile'])

            # Reset emulation
            await send_cmd('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False})
            await send_cmd('Emulation.setTouchEmulationEnabled', {'enabled': False})

            # -------------------------------------------------------------
            # TEST 9: Accessibility prefers-reduced-motion
            # -------------------------------------------------------------
            print("\n[Test 9] Accessibility prefers-reduced-motion...")
            await send_cmd('Emulation.setEmulatedMedia', {
                'media': 'screen',
                'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]
            })
            # Reload page with reduced motion
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.0)
            red_chat_vis = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            red_chat_op = await eval_js('getComputedStyle(document.getElementById("chat")).opacity')
            red_intro_disp = await eval_js('getComputedStyle(document.getElementById("introContainer")).display')
            test9_pass = red_chat_vis == 'visible' and float(red_chat_op) == 1.0 and red_intro_disp == 'none'
            results['Accessibility prefers-reduced-motion (skips intro, chat visible)'] = (
                f"PASS (chat: {red_chat_vis}, opacity: {red_chat_op}, intro: {red_intro_disp})" if test9_pass
                else f"FAIL (chat: {red_chat_vis}, intro: {red_intro_disp})"
            )
            print(results['Accessibility prefers-reduced-motion (skips intro, chat visible)'])

    finally:
        edge_proc.terminate()

    print("\n================ FINAL RESULTS SUMMARY ================")
    all_passed = True
    for test_name, result in results.items():
        print(f"• {test_name}: {result}")
        if not result.startswith("PASS"):
            all_passed = False

    print(f"\nOVERALL STATUS: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed

if __name__ == '__main__':
    ok = asyncio.run(run_all_tests())
    sys.exit(0 if ok else 1)
