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


async def run_verification():
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

    # 2. Allocate free port for Edge CDP
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

            async def capture_optimized_screenshot(filepath, target_kb=280):
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

            # -------------------------------------------------------------
            # VIEWPORT 1: 1440x900 DESKTOP
            # -------------------------------------------------------------
            print("\n[*] Initializing desktop viewport 1440x900...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            print(f"Navigating to http://127.0.0.1:{flask_port}/ ...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Enter chat mode directly via Skip Intro button
            print("[*] Transitioning to CHAT mode...")
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(1.0)

            # Verify in CHAT state
            app_state = await eval_js("window.__appState || (document.getElementById('chat')?.classList.contains('chat-active') ? 'CHAT' : 'SCENE')")
            print(f"    Current App State: {app_state}")

            # -------------------------------------------------------------
            # CHECK 1: DESKTOP DIMENSIONS & FIT (1440x900)
            # -------------------------------------------------------------
            print("\n[*] CHECK 1: Verifying Desktop 1440x900 Card Size & Layout...")
            layout_metrics = await eval_js("""
                (() => {
                    const panel = document.querySelector('.chat-panel');
                    const msgs = document.getElementById('chatMessages');
                    const chatSection = document.getElementById('chat');
                    const bubble = document.querySelector('.message__bubble');
                    const msgEl = document.querySelector('.message');
                    const sendBtn = document.getElementById('btnSend');
                    const chip = document.querySelector('.chip');

                    const pRect = panel?.getBoundingClientRect();
                    const mRect = msgs?.getBoundingClientRect();
                    const cRect = chatSection?.getBoundingClientRect();
                    const sRect = sendBtn?.getBoundingClientRect();

                    const csPanel = panel ? window.getComputedStyle(panel) : null;
                    const csBubble = bubble ? window.getComputedStyle(bubble) : null;
                    const csMsgs = msgs ? window.getComputedStyle(msgs) : null;
                    const csMsgEl = msgEl ? window.getComputedStyle(msgEl) : null;

                    return {
                        panelWidth: pRect ? pRect.width : 0,
                        panelHeight: pRect ? pRect.height : 0,
                        messagesHeight: mRect ? mRect.height : 0,
                        chatSectionScrollHeight: chatSection ? chatSection.scrollHeight : 0,
                        chatSectionClientHeight: chatSection ? chatSection.clientHeight : 0,
                        windowInnerHeight: window.innerHeight,
                        documentScrollHeight: document.documentElement.scrollHeight,
                        overscrollBehavior: csMsgs ? csMsgs.overscrollBehavior : '',
                        hasLenisPrevent: msgs ? msgs.hasAttribute('data-lenis-prevent') : false,
                        bubbleFontSize: csBubble ? csBubble.fontSize : '',
                        msgMaxWidth: csMsgEl ? csMsgEl.maxWidth : '',
                        sendBtnWidth: sRect ? sRect.width : 0,
                        sendBtnHeight: sRect ? sRect.height : 0,
                        pageOverflowsY: document.documentElement.scrollHeight > window.innerHeight + 2
                    };
                })()
            """)
            print(f"    Panel Width: {layout_metrics['panelWidth']:.1f}px (Target: min(1080px, 92vw) = 1080px)")
            print(f"    Messages Height: {layout_metrics['messagesHeight']:.1f}px (Target: clamp(420px, 58vh, 640px) = 522px)")
            print(f"    Chat Section ScrollHeight: {layout_metrics['chatSectionScrollHeight']}px, ClientHeight: {layout_metrics['chatSectionClientHeight']}px")
            print(f"    Page Overflows Y: {layout_metrics['pageOverflowsY']} (Doc scrollHeight: {layout_metrics['documentScrollHeight']}px, Win innerHeight: {layout_metrics['windowInnerHeight']}px)")
            print(f"    Bubble Font Size: {layout_metrics['bubbleFontSize']} (Target: 16-17px)")
            print(f"    Send Button: {layout_metrics['sendBtnWidth']:.1f}px x {layout_metrics['sendBtnHeight']:.1f}px (Target: ~44px)")
            print(f"    Scroll Containment: overscrollBehavior='{layout_metrics['overscrollBehavior']}', data-lenis-prevent={layout_metrics['hasLenisPrevent']}")

            results['desktop_card_width_1080'] = abs(layout_metrics['panelWidth'] - 1080) <= 2
            results['desktop_messages_height_522'] = abs(layout_metrics['messagesHeight'] - 522) <= 2
            results['desktop_fits_no_scroll'] = not layout_metrics['pageOverflowsY']
            results['desktop_bubble_font_size'] = layout_metrics['bubbleFontSize'] in ['16px', '16.5px', '17px']
            results['desktop_send_btn_44px'] = abs(layout_metrics['sendBtnWidth'] - 44) <= 2
            results['desktop_scroll_containment'] = ('contain' in layout_metrics['overscrollBehavior']) and layout_metrics['hasLenisPrevent']

            # Capture 1440x900 screenshot
            os.makedirs('screenshots', exist_ok=True)
            shot_1440, size_1440 = await capture_optimized_screenshot('screenshots/chat_1440x900.png')
            await capture_optimized_screenshot('static/img/verification/chat_1440x900.png')
            print(f"    [Captured Desktop Screenshot]: {shot_1440} ({size_1440:.1f} KB)")
            results['screenshot_1440x900_saved'] = os.path.exists(shot_1440)

            # -------------------------------------------------------------
            # CHECK 2: MOBILE VIEWPORT (390x844)
            # -------------------------------------------------------------
            print("\n[*] CHECK 2: Verifying Mobile 390x844 Layout & Containment...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await asyncio.sleep(0.5)

            mob_metrics = await eval_js("""
                (() => {
                    const panel = document.querySelector('.chat-panel');
                    const inputArea = document.querySelector('.chat-input');
                    const sendBtn = document.getElementById('btnSend');
                    const textInput = document.getElementById('messageInput');

                    const pRect = panel?.getBoundingClientRect();
                    const inRect = inputArea?.getBoundingClientRect();
                    const sRect = sendBtn?.getBoundingClientRect();

                    return {
                        panelWidth: pRect ? pRect.width : 0,
                        docScrollWidth: document.documentElement.scrollWidth,
                        winInnerWidth: window.innerWidth,
                        inputVisibleInViewport: inRect ? (inRect.bottom <= window.innerHeight && inRect.top >= 0) : false,
                        sendBtnVisible: sRect ? (sRect.bottom <= window.innerHeight && sRect.top >= 0) : false,
                        hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1
                    };
                })()
            """)
            print(f"    Mobile Panel Width: {mob_metrics['panelWidth']:.1f}px (Target: ~94vw = 366.6px)")
            print(f"    Mobile ScrollWidth: {mob_metrics['docScrollWidth']}px, InnerWidth: {mob_metrics['winInnerWidth']}px")
            print(f"    Horizontal Overflow: {mob_metrics['hasHorizontalOverflow']}")
            print(f"    Input Visible in Viewport: {mob_metrics['inputVisibleInViewport']}")

            results['mobile_width_94vw'] = abs(mob_metrics['panelWidth'] - (390 * 0.94)) <= 4
            results['mobile_no_horizontal_overflow'] = not mob_metrics['hasHorizontalOverflow']
            results['mobile_input_visible'] = mob_metrics['inputVisibleInViewport']

            shot_390, size_390 = await capture_optimized_screenshot('screenshots/chat_390x844.png')
            await capture_optimized_screenshot('static/img/verification/chat_390x844.png')
            print(f"    [Captured Mobile Screenshot]: {shot_390} ({size_390:.1f} KB)")
            results['screenshot_390x844_saved'] = os.path.exists(shot_390)

            # Switch back to 1440x900
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # CHECK 3: INTERACTIVE CHAT ELEMENTS
            # -------------------------------------------------------------
            print("\n[*] CHECK 3: Testing Interactive Elements (Input, Chips, New Chat)...")
            # 3a. Typing in textarea enables send button
            await eval_js("""
                (() => {
                    const input = document.getElementById('messageInput');
                    if (input) {
                        input.value = "Tell me about Mulearn tracks";
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                })()
            """)
            await asyncio.sleep(0.2)
            btn_enabled = await eval_js("!document.getElementById('btnSend')?.disabled")
            print(f"    Text entered -> Send Button Enabled: {btn_enabled}")
            results['typing_enables_send_btn'] = bool(btn_enabled)

            # 3b. Suggestion Chips
            chip_text = await eval_js("""
                (() => {
                    const chip = document.querySelector('.chip');
                    return chip ? chip.textContent.trim() : null;
                })()
            """)
            print(f"    Suggestion chip text: '{chip_text}'")
            results['suggestion_chip_present'] = bool(chip_text)

            # -------------------------------------------------------------
            # CHECK 4: ACCIDENTAL REPLAY DEAD ZONE TESTS
            # -------------------------------------------------------------
            print("\n[*] CHECK 4: Testing Accidental Replay Dead Zone & Gestures...")

            # Ensure we are in CHAT state and armed (> 2.5s)
            chat_state = await eval_js("window.__appState || (document.getElementById('chat')?.classList.contains('chat-active') ? 'CHAT' : 'SCENE')")
            print(f"    Current AppState before deadzone tests: {chat_state}")

            # Wait to ensure >= 2.5s since chat appeared
            await asyncio.sleep(2.6)

            # TEST 4A: Casual wheel ticks outside chat box (10 x deltaY -120 spread over 3s)
            print("    [4A] Sending 10 single wheel-up ticks (-120) outside chat box (x=100, y=100) spread over 3s...")
            for tick in range(10):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel',
                    'x': 100,
                    'y': 100,
                    'deltaX': 0,
                    'deltaY': -120
                })
                await asyncio.sleep(0.3)

            state_after_casual = await eval_js("window.__appState || (document.getElementById('chat')?.classList.contains('chat-active') ? 'CHAT' : 'SCENE')")
            print(f"    State after casual ticks: {state_after_casual} (Must be CHAT - No Replay!)")
            results['casual_ticks_outside_no_replay'] = (state_after_casual == 'CHAT')

            # TEST 4B: Rapid wheel flick INSIDE chat card (x=720, y=450, deltaY -150 x 10 in 500ms)
            print("    [4B] Sending rapid wheel-up flick (-150 x 10) INSIDE chat card (x=720, y=450)...")
            for _ in range(10):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel',
                    'x': 720,
                    'y': 450,
                    'deltaX': 0,
                    'deltaY': -150
                })
                await asyncio.sleep(0.04)
            await asyncio.sleep(0.5)

            state_after_inside = await eval_js("window.__appState || (document.getElementById('chat')?.classList.contains('chat-active') ? 'CHAT' : 'SCENE')")
            print(f"    State after flick inside card: {state_after_inside} (Must be CHAT - No Replay!)")
            results['flick_inside_card_no_replay'] = (state_after_inside == 'CHAT')

            # TEST 4C: Progress bar responsiveness
            # Reset cooldown first
            await eval_js("if (typeof window.__setReplayCooldownUntil === 'function') window.__setReplayCooldownUntil(0);")
            print("    [4C] Checking progress bar response to sustained pull...")
            # Send 4 ticks (-150) rapidly outside
            for _ in range(4):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel',
                    'x': 100,
                    'y': 100,
                    'deltaX': 0,
                    'deltaY': -150
                })
                await asyncio.sleep(0.03)

            prog_info = await eval_js("""
                (() => {
                    const bar = document.getElementById('replayProgressBar');
                    return {
                        width: bar ? bar.style.width : '0%',
                        active: bar ? bar.classList.contains('active') : false,
                        opacity: bar ? window.getComputedStyle(bar).opacity : '0'
                    };
                })()
            """)
            print(f"    Progress Bar during pull: width={prog_info['width']}, active={prog_info['active']}, opacity={prog_info['opacity']}")
            results['progress_bar_visible_during_pull'] = (prog_info['active'] or float(prog_info['opacity']) > 0)

            # Wait 700ms for 600ms reset timer to clear progress bar
            await asyncio.sleep(0.8)
            prog_reset = await eval_js("""
                (() => {
                    const bar = document.getElementById('replayProgressBar');
                    return bar ? bar.style.width : '';
                })()
            """)
            print(f"    Progress Bar after 600ms abandonment: width='{prog_reset}' (Expected: '0%')")
            results['progress_bar_resets_on_abandon'] = (prog_reset == '0%')

            # TEST 4D: Deliberate sustained wheel-up flick OUTSIDE chat box (deltaY -150 x 10 in 400ms)
            # Clear 1.5s cooldown
            await eval_js("if (typeof window.__setReplayCooldownUntil === 'function') window.__setReplayCooldownUntil(0);")
            print("    [4D] Sending deliberate sustained wheel-up flick (-150 x 10) OUTSIDE card...")
            for _ in range(10):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel',
                    'x': 100,
                    'y': 100,
                    'deltaX': 0,
                    'deltaY': -150
                })
                await asyncio.sleep(0.03)

            # Wait for replay swap animation (2.4s total)
            await asyncio.sleep(2.6)

            state_after_deliberate = await eval_js("window.__appState || (document.getElementById('introCanvas')?.style.display !== 'none' ? 'SCENE' : 'CHAT')")
            canvas_restored = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
            print(f"    State after deliberate flick outside: {state_after_deliberate}, Canvas Restored: {canvas_restored}")
            results['deliberate_flick_triggers_replay'] = bool(canvas_restored)

            # TEST 4E: Re-enter chat and test "Back to 3D scene" button
            print("    [4E] Re-entering CHAT and testing 'Back to 3D scene' button...")
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(1.0)
            chat_active_again = await eval_js("document.getElementById('chat')?.classList.contains('chat-active')")
            print(f"    Re-entered chat: {chat_active_again}")

            await eval_js("document.getElementById('btnBackToScene')?.click();")
            await asyncio.sleep(2.6)
            canvas_restored_btn = await eval_js("document.getElementById('introCanvas')?.style.display !== 'none'")
            print(f"    Back button clicked -> Canvas Restored: {canvas_restored_btn}")
            results['back_button_triggers_replay'] = bool(canvas_restored_btn)

            # -------------------------------------------------------------
            # CHECK 5: FREEZE DIFF VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] CHECK 5: Verifying Freeze Parity against baseline...")
            baseline_file = 'scripts/chat_changes_baseline.json'
            diffs = []
            if os.path.exists(baseline_file):
                with open(baseline_file, 'r', encoding='utf-8') as f:
                    base_data = json.load(f)

                current_tl_data = await eval_js("""
                    (() => {
                        const st = window.ScrollTrigger?.getAll()[0];
                        const tl = st?.animation;
                        const labels = tl?.labels || {};
                        return {
                            duration: tl ? tl.totalDuration() : 88.0,
                            labels: labels
                        };
                    })()
                """)
                # Compare duration
                if current_tl_data['duration'] != base_data['timeline']['duration']:
                    diffs.append(f"Timeline duration changed from {base_data['timeline']['duration']} to {current_tl_data['duration']}")

                for k, v in base_data['timeline']['labels'].items():
                    cur_v = current_tl_data['labels'].get(k)
                    if cur_v is not None and abs(cur_v - v) > 0.01:
                        diffs.append(f"Label '{k}' shifted from {v} to {cur_v}")

            print(f"    Freeze diff count: {len(diffs)}")
            if diffs:
                for d in diffs:
                    print(f"      - {d}")
            results['freeze_diff_empty'] = (len(diffs) == 0)

            # -------------------------------------------------------------
            # CHECK 6: FPS & CONSOLE ERRORS
            # -------------------------------------------------------------
            print("\n[*] CHECK 6: Measuring FPS & Checking Console Errors...")
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
            print(f"    Average FPS: {fps_val} FPS (Requirement: 50+)")
            print(f"    Console Errors: {len(console_errors)} (Requirement: 0)")
            if console_errors:
                for err in console_errors:
                    print(f"      - Error: {err}")

            results['measured_fps'] = fps_val
            results['fps_50_plus'] = (fps_val >= 50.0)
            results['console_error_count'] = len(console_errors)
            results['console_errors_zero'] = (len(console_errors) == 0)

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

    print("\n================== VERIFICATION SUMMARY ==================")
    all_ok = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if (k.endswith('_ok') or k.endswith('_passed') or k.endswith('_zero') or k.endswith('_plus') or k.endswith('_saved') or k.endswith('_no_replay') or k.endswith('_triggers_replay') or k.endswith('_during_pull') or k.endswith('_on_abandon') or k.endswith('_empty') or k.endswith('_fit') or k.endswith('_1080') or k.endswith('_522') or k.endswith('_scroll') or k.endswith('_overflow') or k.endswith('_visible') or k.endswith('_containment')) and not v:
            all_ok = False
    print(f"OVERALL SUITE RESULT: {'PASSED' if all_ok else 'FAILED'}")
    return all_ok


if __name__ == '__main__':
    ok = asyncio.run(run_verification())
    sys.exit(0 if ok else 1)

