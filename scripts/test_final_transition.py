"""
µLearn Concierge — Final Transition & Two-State FSM Verification Suite (CDP)
Tests:
1. Real wheel input (top, mid, end of scene) & transition flash timing (0.8s in, 0.6s hold, 1.0s out).
2. CHAT state clickability (elementFromPoint on input, chip, send; click suggestion; type & send).
3. CHAT state cleanup (canvas, wrapper, spacer display: none; flash pointer-events: none; RAF stopped).
4. Replay 3 full cycles (btnBackToScene, wheel-up at chat top, message list wheel containment).
5. Cross-checks (390px mobile touch, keyboard Space/PageDown/Arrows, direct #chat, skip button, reduced-motion).
6. Screenshots (phase5-zoomin.png and phase6-chat.png replaced and assert < 300 KB).
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

# Ensure offline mock mode for Flask API calls
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False  # offline fallback, no live API call


async def run_final_transition_tests():
    results = {}

    # 1. Allocate free port and start Flask
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

            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
                return res.get('result', {}).get('result', {}).get('value')

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
                await asyncio.sleep(0.4)

            async def wait_for_state(target_state, max_seconds=4.0):
                t0 = time.time()
                while time.time() - t0 < max_seconds:
                    st = await eval_js('window.__getAppState ? window.__getAppState() : null')
                    if st == target_state:
                        return True
                    await asyncio.sleep(0.1)
                return False

            async def capture_screenshot(filename):
                os.makedirs('static/img/verification', exist_ok=True)
                shot_res = await send_cmd('Page.captureScreenshot', {'format': 'png'})
                data = base64.b64decode(shot_res['result']['data'])
                out_path = os.path.join('static', 'img', 'verification', filename)
                with open(out_path, 'wb') as f:
                    f.write(data)
                size_kb = os.path.getsize(out_path) / 1024
                print(f"  [Screenshot] Saved {filename} ({size_kb:.1f} KB)")
                return size_kb

            # Initialize 1280x800 viewport
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1280,
                'height': 800,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            # Navigate to Concierge app
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.0)

            print("\n=======================================================")
            print("RUNNING FINAL TRANSITION VERIFICATION (MANDATORY CDP)")
            print("=======================================================")

            # =========================================================
            # ITEM 1: Real wheel input & Flash transition timings
            # =========================================================
            print("\n--- ITEM 1: Real Wheel Input & Flash Duration ---")

            # 1a. Wheel at top of page
            s0 = await eval_js('window.scrollY')
            await send_wheel(640, 400, delta_y=120, count=5)
            s1 = await eval_js('window.scrollY')
            p1 = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            w_top_pass = s1 > s0 and p1 > 0
            results['1a. Wheel at top of page advances timeline'] = (
                f"PASS (scrollY: {s0} -> {s1}, progress: {p1:.3f})" if w_top_pass
                else f"FAIL (scrollY: {s0} -> {s1})"
            )
            print("•", results['1a. Wheel at top of page advances timeline'])

            # 1b. Wheel mid-scene (progress ~0.45)
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
            await send_wheel(640, 400, delta_y=120, count=5)
            s_mid1 = await eval_js('window.scrollY')
            w_mid_pass = s_mid1 > s_mid0
            results['1b. Wheel mid-scene advances timeline'] = (
                f"PASS (scrollY: {s_mid0} -> {s_mid1})" if w_mid_pass
                else f"FAIL (scrollY: {s_mid0} -> {s_mid1})"
            )
            print("•", results['1b. Wheel mid-scene advances timeline'])

            # 1c. Capture phase5-zoomin screenshot before the trigger (progress ~0.89)
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const p89 = st.start + 0.89 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(p89, { immediate: true });
                    else window.scrollTo(0, p89);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.6)
            sz_p5 = await capture_screenshot('phase5-zoomin.png')

            # 1d. Wheel near end of scene (crosses 0.92, triggers time-based swap)
            t_start = time.time()
            await send_wheel(640, 400, delta_y=120, count=5)

            # Wait and poll flash opacity during transition
            opacities = []
            for _ in range(28):
                op = await eval_js('parseFloat(getComputedStyle(document.getElementById("flashOverlay")).opacity)')
                disp = await eval_js('getComputedStyle(document.getElementById("flashOverlay")).display')
                opacities.append((round(time.time() - t_start, 2), op, disp))
                await asyncio.sleep(0.1)

            # Wait for transition completion to CHAT
            await wait_for_state('CHAT', max_seconds=3.0)
            chat_state = await eval_js('window.__getAppState ? window.__getAppState() : null')
            metrics = await eval_js('window.__transitionMetrics')
            print(f"  Transition metrics: {metrics}")

            t_fade_in = metrics.get('fadeInDuration', 0)
            t_hold = metrics.get('holdDuration', 0)
            t_fade_out = metrics.get('fadeOutDuration', 0)
            t_total = metrics.get('totalDuration', 0)
            timing_pass = (
                t_fade_in == 0.8 and
                t_hold == 0.6 and
                t_fade_out == 1.0 and
                t_total == 2.4 and
                chat_state == 'CHAT'
            )
            results['1c. Flash swap: 0.8s in, 0.6s hold, 1.0s out -> CHAT'] = (
                f"PASS (in: {t_fade_in}s, hold: {t_hold}s, out: {t_fade_out}s, total: {t_total}s, state: {chat_state})"
                if timing_pass else f"FAIL (state: {chat_state}, metrics: {metrics})"
            )
            print("•", results['1c. Flash swap: 0.8s in, 0.6s hold, 1.0s out -> CHAT'])

            # =========================================================
            # ITEM 2: CHAT state clickability & interaction
            # =========================================================
            print("\n--- ITEM 2: CHAT State Clickability & Interaction ---")

            # 2a. elementFromPoint checks for messageInput, suggestion chip, and send button
            el_tests = await eval_js('''
                (() => {
                    const input = document.getElementById("messageInput");
                    const chip = document.querySelector(".chip");
                    const sendBtn = document.getElementById("btnSend");

                    function checkCenter(el) {
                        const r = el.getBoundingClientRect();
                        const cx = r.left + r.width / 2;
                        const cy = r.top + r.height / 2;
                        const hit = document.elementFromPoint(cx, cy);
                        return {
                            id: el.id || el.className,
                            hitTag: hit ? hit.tagName : null,
                            hitId: hit ? hit.id : null,
                            hitClass: hit ? hit.className : null,
                            isContained: el.contains(hit) || hit === el
                        };
                    }

                    return {
                        input: checkCenter(input),
                        chip: checkCenter(chip),
                        sendBtn: checkCenter(sendBtn)
                    };
                })()
            ''')
            print(f"  elementFromPoint inspection: {el_tests}")
            el_pass = (
                el_tests['input']['isContained'] and
                el_tests['chip']['isContained'] and
                el_tests['sendBtn']['isContained']
            )
            results['2a. elementFromPoint hits exact chat interactive elements'] = (
                f"PASS (input: {el_tests['input']['hitTag']}, chip: {el_tests['chip']['hitTag']}, send: {el_tests['sendBtn']['hitTag']})"
                if el_pass else f"FAIL ({el_tests})"
            )
            print("•", results['2a. elementFromPoint hits exact chat interactive elements'])

            # 2b. Click suggestion chip and verify assistant response appears
            print("  Clicking suggestion chip 'What is µLearn?'...")
            init_msg_count = await eval_js('document.querySelectorAll(".message").length')
            await eval_js('document.querySelector(".chip").click()')

            # Wait for assistant response and typewriter animation to complete
            await asyncio.sleep(0.5)
            for _ in range(60):
                sending = await eval_js('window.__isSending ? window.__isSending() : false')
                if not sending:
                    break
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.5)

            post_chip_msg_count = await eval_js('document.querySelectorAll(".message").length')
            last_msg_text = await eval_js('''
                (() => {
                    const msgs = document.querySelectorAll(".message__bubble");
                    return msgs[msgs.length - 1] ? msgs[msgs.length - 1].textContent.trim() : "";
                })()
            ''')
            chip_pass = post_chip_msg_count >= init_msg_count + 2 and len(last_msg_text) > 10
            results['2b. Suggestion chip click sends query & renders assistant reply'] = (
                f"PASS (messages: {init_msg_count} -> {post_chip_msg_count}, reply len: {len(last_msg_text)})"
                if chip_pass else f"FAIL (messages: {init_msg_count} -> {post_chip_msg_count})"
            )
            print("•", results['2b. Suggestion chip click sends query & renders assistant reply'])

            # 2c. Type query in message input, submit, verify assistant responds
            print("  Typing question into #messageInput and submitting...")
            for _ in range(40):
                if not await eval_js('window.__isSending ? window.__isSending() : false'):
                    break
                await asyncio.sleep(0.1)

            await eval_js('''
                (() => {
                    const input = document.getElementById("messageInput");
                    input.focus();
                    input.value = "What are Karma points?";
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    const btn = document.getElementById("btnSend");
                    if (btn && !btn.disabled) {
                        btn.click();
                    } else {
                        const form = document.getElementById("chatForm");
                        form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
                    }
                })()
            ''')

            # Wait for assistant response and typewriter animation to complete
            await asyncio.sleep(0.5)
            for _ in range(60):
                sending = await eval_js('window.__isSending ? window.__isSending() : false')
                if not sending:
                    break
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.5)

            post_send_msg_count = await eval_js('document.querySelectorAll(".message").length')
            last_reply = await eval_js('''
                (() => {
                    const msgs = document.querySelectorAll(".message__bubble");
                    return msgs[msgs.length - 1] ? msgs[msgs.length - 1].textContent.trim() : "";
                })()
            ''')
            send_pass = post_send_msg_count >= post_chip_msg_count + 2 and "karma" in last_reply.lower()
            results['2c. Type in #messageInput & submit returns assistant response'] = (
                f"PASS (messages: {post_send_msg_count}, response cites Karma)"
                if send_pass else f"FAIL (reply: {last_reply[:60]}...)"
            )
            print("•", results['2c. Type in #messageInput & submit returns assistant response'])

            # =========================================================
            # ITEM 3: CHAT state cleanup & non-interactivity
            # =========================================================
            print("\n--- ITEM 3: CHAT State DOM Cleanup & Render Loop Stopped ---")
            cleanup_info = await eval_js('''
                (() => {
                    const canvas = document.getElementById("introCanvas");
                    const wrapper = document.getElementById("introContainer");
                    const spacer = document.getElementById("introSpacer");
                    const flash = document.getElementById("flashOverlay");
                    const isLoop = window.__isRenderLoopRunning ? window.__isRenderLoopRunning() : true;

                    return {
                        canvasDisplay: getComputedStyle(canvas).display,
                        wrapperDisplay: getComputedStyle(wrapper).display,
                        spacerDisplay: getComputedStyle(spacer).display,
                        flashDisplay: getComputedStyle(flash).display,
                        flashPointerEvents: getComputedStyle(flash).pointerEvents,
                        isLoopRunning: isLoop
                    };
                })()
            ''')
            print(f"  Cleanup diagnostics: {cleanup_info}")
            cleanup_pass = (
                cleanup_info['canvasDisplay'] == 'none' and
                cleanup_info['wrapperDisplay'] == 'none' and
                cleanup_info['spacerDisplay'] == 'none' and
                cleanup_info['flashDisplay'] == 'none' and
                cleanup_info['flashPointerEvents'] == 'none' and
                cleanup_info['isLoopRunning'] is False
            )
            results['3. Scene wrapper, canvas, spacer hidden & RAF loop stopped in CHAT'] = (
                f"PASS (canvas: {cleanup_info['canvasDisplay']}, spacer: {cleanup_info['spacerDisplay']}, RAF running: {cleanup_info['isLoopRunning']})"
                if cleanup_pass else f"FAIL ({cleanup_info})"
            )
            print("•", results['3. Scene wrapper, canvas, spacer hidden & RAF loop stopped in CHAT'])

            # Capture phase6-chat screenshot
            sz_p6 = await capture_screenshot('phase6-chat.png')

            # =========================================================
            # ITEM 4: Replay Cycles (3 Full Cycles Scene <-> Chat)
            # =========================================================
            print("\n--- ITEM 4: Replay Cycles (3 Full Cycles) & Containment ---")

            # 4a. Wheel inside message list does NOT trigger replay
            print("  Testing wheel containment inside #chatMessages list...")
            msg_center = await eval_js('''
                (() => {
                    const el = document.getElementById("chatMessages");
                    const r = el.getBoundingClientRect();
                    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                })()
            ''')
            await send_wheel(x=int(msg_center['x']), y=int(msg_center['y']), delta_y=-120, count=5)
            await asyncio.sleep(0.5)
            state_after_msg_wheel = await eval_js('window.__getAppState()')
            contain_pass = (state_after_msg_wheel == 'CHAT')
            results['4a. Wheel inside message list does NOT trigger scene transition'] = (
                f"PASS (state remained {state_after_msg_wheel})"
                if contain_pass else f"FAIL (unexpected state: {state_after_msg_wheel})"
            )
            print("•", results['4a. Wheel inside message list does NOT trigger scene transition'])

            # 4b. Replay cycle 1: Click #btnBackToScene -> Scene -> scroll to Chat
            print("  Cycle 1: Clicking #btnBackToScene...")
            await eval_js('document.getElementById("btnBackToScene").click()')
            await wait_for_state('SCENE', max_seconds=3.5)
            c1_scene_state = await eval_js('window.__getAppState()')
            c1_loop = await eval_js('window.__isRenderLoopRunning()')
            c1_canvas_disp = await eval_js('getComputedStyle(document.getElementById("introCanvas")).display')
            s_prog1 = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            print(f"    Restored: state={c1_scene_state}, RAF running={c1_loop}, canvas={c1_canvas_disp}, progress={s_prog1:.3f}")

            # Scroll forward to return to CHAT
            await send_wheel(640, 400, delta_y=120, count=7)
            await wait_for_state('CHAT', max_seconds=3.5)
            c1_chat_state = await eval_js('window.__getAppState()')
            c1_pass = (c1_scene_state == 'SCENE' and c1_loop is True and c1_canvas_disp == 'block' and c1_chat_state == 'CHAT')
            print(f"    Cycle 1 result: {'PASS' if c1_pass else 'FAIL'} (final state: {c1_chat_state})")

            # 4c. Replay cycle 2: Deliberate wheel-up at chat top -> Scene -> scroll to Chat
            print("  Cycle 2: Deliberate wheel-up at chat top (outside message list)...")
            header_pt = await eval_js('''
                (() => {
                    const el = document.querySelector(".chat-header");
                    const r = el.getBoundingClientRect();
                    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                })()
            ''')
            await send_wheel(x=int(header_pt['x']), y=int(header_pt['y']), delta_y=-120, count=5)
            await wait_for_state('SCENE', max_seconds=3.5)
            c2_scene_state = await eval_js('window.__getAppState()')
            c2_loop = await eval_js('window.__isRenderLoopRunning()')
            s_prog2 = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            print(f"    Restored: state={c2_scene_state}, RAF running={c2_loop}, progress={s_prog2:.3f}")

            # Scroll forward to return to CHAT
            await send_wheel(640, 400, delta_y=120, count=7)
            await wait_for_state('CHAT', max_seconds=3.5)
            c2_chat_state = await eval_js('window.__getAppState()')
            c2_pass = (c2_scene_state == 'SCENE' and c2_loop is True and c2_chat_state == 'CHAT')
            print(f"    Cycle 2 result: {'PASS' if c2_pass else 'FAIL'} (final state: {c2_chat_state})")

            # 4d. Replay cycle 3: Click #btnBackToScene -> Scene -> scroll to Chat
            print("  Cycle 3: Third roundtrip via button...")
            await eval_js('document.getElementById("btnBackToScene").click()')
            await wait_for_state('SCENE', max_seconds=3.5)
            c3_scene_state = await eval_js('window.__getAppState()')
            c3_loop = await eval_js('window.__isRenderLoopRunning()')
            s_prog3 = await eval_js('window.ScrollTrigger ? window.ScrollTrigger.getAll()[0].progress : 0')
            print(f"    Restored: state={c3_scene_state}, RAF running={c3_loop}, progress={s_prog3:.3f}")

            # Scroll forward to return to CHAT
            await send_wheel(640, 400, delta_y=120, count=7)
            await wait_for_state('CHAT', max_seconds=3.5)
            c3_chat_state = await eval_js('window.__getAppState()')
            c3_pass = (c3_scene_state == 'SCENE' and c3_loop is True and c3_chat_state == 'CHAT')
            print(f"    Cycle 3 result: {'PASS' if c3_pass else 'FAIL'} (final state: {c3_chat_state})")

            cycles_pass = c1_pass and c2_pass and c3_pass
            results['4b. 3 Full Replay Cycles (Scene <-> Chat) without stuck state'] = (
                f"PASS (all 3 cycles completed seamlessly)"
                if cycles_pass else f"FAIL (c1: {c1_pass}, c2: {c2_pass}, c3: {c3_pass})"
            )
            print("•", results['4b. 3 Full Replay Cycles (Scene <-> Chat) without stuck state'])

            # =========================================================
            # ITEM 5: Cross-checks (Keyboard, Mobile, Direct Load)
            # =========================================================
            print("\n--- ITEM 5: Cross-checks (Keyboard, Mobile, Direct Skip) ---")

            # 5a. Keyboard in SCENE state (Space, PageDown, Down Arrow)
            print("  Testing keyboard scrolling in SCENE state...")
            # Return to scene first
            await eval_js('document.getElementById("btnBackToScene").click()')
            await wait_for_state('SCENE', max_seconds=3.5)
            # Set scroll to middle of scene
            await eval_js('''
                (() => {
                    const st = window.ScrollTrigger.getAll()[0];
                    const p30 = st.start + 0.30 * (st.end - st.start);
                    if (window.lenis) window.lenis.scrollTo(p30, { immediate: true });
                    else window.scrollTo(0, p30);
                    st.update();
                })()
            ''')
            await asyncio.sleep(0.4)
            k0 = await eval_js('window.scrollY')

            # PageDown key
            await send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'windowsVirtualKeyCode': 34, 'code': 'PageDown', 'key': 'PageDown'})
            await send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'windowsVirtualKeyCode': 34, 'code': 'PageDown', 'key': 'PageDown'})
            await asyncio.sleep(0.4)

            # ArrowDown keys
            for _ in range(4):
                await send_cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'windowsVirtualKeyCode': 40, 'code': 'ArrowDown', 'key': 'ArrowDown'})
                await send_cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'windowsVirtualKeyCode': 40, 'code': 'ArrowDown', 'key': 'ArrowDown'})
                await asyncio.sleep(0.04)
            await asyncio.sleep(0.6)
            k1 = await eval_js('window.scrollY')
            key_pass = (k1 > k0)
            results['5a. Keyboard navigation (PageDown / Down Arrow) advances timeline'] = (
                f"PASS (scrollY: {k0} -> {k1})" if key_pass else f"FAIL (scrollY: {k0} -> {k1})"
            )
            print("•", results['5a. Keyboard navigation (PageDown / Down Arrow) advances timeline'])

            # 5b. Mobile 390px Viewport Touch Emulation
            print("  Testing 390px mobile viewport & touch gestures...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await send_cmd('Emulation.setTouchEmulationEnabled', {'enabled': True})
            await eval_js('window.scrollTo(0, 0); if (window.lenis) window.lenis.scrollTo(0, { immediate: true });')
            await asyncio.sleep(0.4)

            # Touch swipe up to advance timeline
            await send_cmd('Input.dispatchTouchEvent', {
                'type': 'touchStart',
                'touchPoints': [{'x': 195, 'y': 600}]
            })
            await asyncio.sleep(0.04)
            for step in range(5):
                await send_cmd('Input.dispatchTouchEvent', {
                    'type': 'touchMove',
                    'touchPoints': [{'x': 195, 'y': 600 - (step + 1) * 60}]
                })
                await asyncio.sleep(0.04)
            await send_cmd('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            await asyncio.sleep(0.8)
            mob_s = await eval_js('window.scrollY')
            mob_pass = mob_s > 0
            results['5b. Mobile 390px viewport touch scroll advances timeline'] = (
                f"PASS (scrollY: {mob_s})" if mob_pass else f"FAIL (scrollY: {mob_s})"
            )
            print("•", results['5b. Mobile 390px viewport touch scroll advances timeline'])

            # Reset mobile emulation
            await send_cmd('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False})
            await send_cmd('Emulation.setTouchEmulationEnabled', {'enabled': False})

            # 5c. Skip Intro Button
            print("  Testing Skip Intro button...")
            await eval_js('window.scrollTo(0, 0); if (window.lenis) window.lenis.scrollTo(0, { immediate: true });')
            await asyncio.sleep(0.4)
            await eval_js('document.getElementById("btnSkipIntro").click()')
            await wait_for_state('CHAT', max_seconds=2.0)
            skip_state = await eval_js('window.__getAppState()')
            skip_chat_disp = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            skip_pass = (skip_state == 'CHAT' and skip_chat_disp == 'visible')
            results['5c. Skip intro button instantly enters CHAT state'] = (
                f"PASS (state: {skip_state}, chat visibility: {skip_chat_disp})"
                if skip_pass else f"FAIL (state: {skip_state})"
            )
            print("•", results['5c. Skip intro button instantly enters CHAT state'])

            # 5d. Direct #chat Hash Navigation
            print("  Testing direct /#chat hash navigation...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/#chat'})
            await asyncio.sleep(2.0)
            hash_state = await eval_js('window.__getAppState ? window.__getAppState() : null')
            hash_canvas = await eval_js('getComputedStyle(document.getElementById("introCanvas")).display')
            hash_pass = (hash_state == 'CHAT' and hash_canvas == 'none')
            results['5d. Direct /#chat hash enters CHAT state with no scene running'] = (
                f"PASS (state: {hash_state}, canvas: {hash_canvas})"
                if hash_pass else f"FAIL (state: {hash_state})"
            )
            print("•", results['5d. Direct /#chat hash enters CHAT state with no scene running'])

            # 5e. prefers-reduced-motion Accessibility
            print("  Testing prefers-reduced-motion accessibility emulation...")
            await send_cmd('Emulation.setEmulatedMedia', {
                'media': 'screen',
                'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]
            })
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.0)
            red_state = await eval_js('window.__getAppState ? window.__getAppState() : null')
            red_canvas = await eval_js('getComputedStyle(document.getElementById("introCanvas")).display')
            red_chat_vis = await eval_js('getComputedStyle(document.getElementById("chat")).visibility')
            red_pass = (red_state == 'CHAT' and red_canvas == 'none' and red_chat_vis == 'visible')
            results['5e. prefers-reduced-motion enters CHAT immediately without 3D scene'] = (
                f"PASS (state: {red_state}, canvas: {red_canvas}, chat: {red_chat_vis})"
                if red_pass else f"FAIL (state: {red_state}, canvas: {red_canvas})"
            )
            print("•", results['5e. prefers-reduced-motion enters CHAT immediately without 3D scene'])

            # =========================================================
            # ITEM 6: Screenshot Verification & Size Assertion
            # =========================================================
            print("\n--- ITEM 6: Screenshot Files & Size Assertions (< 300 KB) ---")
            p5_ok = sz_p5 < 300
            p6_ok = sz_p6 < 300
            shots_pass = p5_ok and p6_ok
            results['6. Verification screenshots < 300 KB'] = (
                f"PASS (phase5-zoomin: {sz_p5:.1f} KB, phase6-chat: {sz_p6:.1f} KB)"
                if shots_pass else f"FAIL (p5: {sz_p5:.1f} KB, p6: {sz_p6:.1f} KB)"
            )
            print("•", results['6. Verification screenshots < 300 KB'])

    finally:
        edge_proc.terminate()

    print("\n=======================================================")
    print("MANDATORY CDP TEST SUMMARY RESULTS")
    print("=======================================================")
    all_passed = True
    for test_key, res in results.items():
        print(f"• {test_key}: {res}")
        if not res.startswith("PASS"):
            all_passed = False

    print("\nOVERALL TEST STATUS:", "ALL PASSED" if all_passed else "FAILURES DETECTED")
    return all_passed


if __name__ == '__main__':
    ok = asyncio.run(run_final_transition_tests())
    sys.exit(0 if ok else 1)
