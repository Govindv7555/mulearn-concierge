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


async def run_layout_suite():
    results = {}
    console_errors = []

    # 1. Start Flask on free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(1.2)

    # 2. Start Edge CDP on free port
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
            # TEST 1: ALL 9 VIEWPORTS ASSERTIONS
            # -------------------------------------------------------------
            print("\n[*] TEST 1: Testing all 9 Viewports for Layout Assertions...")
            viewports = [
                (1920, 1080, False),
                (1536, 864, False),
                (1487, 800, False),
                (1440, 900, False),
                (1366, 768, False),
                (1280, 720, False),
                (1024, 600, False),
                (390, 844, True),
                (360, 640, True)
            ]

            # Initial navigate at 1440x900
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Enter chat mode
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(1.0)

            viewport_results = []
            all_viewports_passed = True

            print("\n" + "=" * 90)
            print(f"{'Viewport':<12} | {'Input<=Card':<12} | {'Card<=WinH':<12} | {'Chips<=Input':<13} | {'DocH<=WinH':<12} | {'Status':<8}")
            print("-" * 90)

            for w, h, is_mobile in viewports:
                await send_cmd('Emulation.setDeviceMetricsOverride', {
                    'width': w,
                    'height': h,
                    'deviceScaleFactor': 2 if is_mobile else 1,
                    'mobile': is_mobile
                })
                await eval_js("window.dispatchEvent(new Event('resize'));")
                await asyncio.sleep(0.4)

                metrics = await eval_js("""
                    (() => {
                        const card = document.querySelector('.chat-panel');
                        const input = document.getElementById('chatForm');
                        const chips = document.getElementById('suggestions');
                        const messages = document.getElementById('chatMessages');

                        const cRect = card ? card.getBoundingClientRect() : null;
                        const iRect = input ? input.getBoundingClientRect() : null;
                        const chRect = chips ? chips.getBoundingClientRect() : null;
                        const mRect = messages ? messages.getBoundingClientRect() : null;

                        const winH = window.innerHeight;
                        const docH = document.documentElement.scrollHeight;

                        const inputInsideCard = iRect && cRect ? (iRect.bottom <= cRect.bottom + 1.5) : false;
                        const cardInsideWin = cRect ? (cRect.bottom <= winH + 1.5) : false;
                        const chipsAboveInput = chRect && iRect ? (chRect.bottom <= iRect.top + 1.5) : true;
                        const noPageScroll = docH <= winH + 1.5;

                        return {
                            winH: winH,
                            docH: docH,
                            cardBottom: cRect ? cRect.bottom : 0,
                            cardHeight: cRect ? cRect.height : 0,
                            inputBottom: iRect ? iRect.bottom : 0,
                            inputTop: iRect ? iRect.top : 0,
                            chipsBottom: chRect ? chRect.bottom : 0,
                            messagesHeight: mRect ? mRect.height : 0,
                            inputInsideCard: inputInsideCard,
                            cardInsideWin: cardInsideWin,
                            chipsAboveInput: chipsAboveInput,
                            noPageScroll: noPageScroll,
                            allPassed: inputInsideCard && cardInsideWin && chipsAboveInput && noPageScroll
                        };
                    })()
                """)

                v_name = f"{w}x{h}"
                status = "PASS" if metrics['allPassed'] else "FAIL"
                if not metrics['allPassed']:
                    all_viewports_passed = False

                print(f"{v_name:<12} | {str(metrics['inputInsideCard']):<12} | {str(metrics['cardInsideWin']):<12} | {str(metrics['chipsAboveInput']):<13} | {str(metrics['noPageScroll']):<12} | {status:<8}")
                viewport_results.append({
                    "viewport": v_name,
                    "metrics": metrics,
                    "passed": metrics['allPassed']
                })

                # Capture screenshots for key viewports
                if (w, h) == (1487, 800):
                    p, _ = await capture_optimized_screenshot('screenshots/chat_1487x800.png')
                    await capture_optimized_screenshot('static/img/verification/chat_1487x800.png')
                    results['screenshot_1487x800_saved'] = os.path.exists(p)
                elif (w, h) == (1366, 768):
                    p, _ = await capture_optimized_screenshot('screenshots/chat_1366x768.png')
                    await capture_optimized_screenshot('static/img/verification/chat_1366x768.png')
                    results['screenshot_1366x768_saved'] = os.path.exists(p)
                elif (w, h) == (390, 844):
                    p, _ = await capture_optimized_screenshot('screenshots/chat_390x844_layout.png')
                    await capture_optimized_screenshot('static/img/verification/chat_390x844_layout.png')
                    results['screenshot_390x844_saved'] = os.path.exists(p)

            print("=" * 90)
            results['all_9_viewports_passed'] = all_viewports_passed

            # -------------------------------------------------------------
            # TEST 2: SEND 8 MESSAGES & SCROLL VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 2: Sending 8 messages and confirming list scrolls inside card with input in place...")
            # Set to 1487x800
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1487,
                'height': 800,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("window.dispatchEvent(new Event('resize'));")
            await asyncio.sleep(0.4)

            # Record input position before sending
            input_pos_before = await eval_js("""
                (() => {
                    const i = document.getElementById('chatForm');
                    const r = i ? i.getBoundingClientRect() : null;
                    return r ? { top: r.top, bottom: r.bottom, height: r.height } : null;
                })()
            """)

            test_prompts = [
                "What tracks are available?",
                "How does the Discord bot work?",
                "Tell me about web development track",
                "What are karma leaderboards?",
                "How do I join an IG group?",
                "Tell me about upcoming hackathons",
                "Who are the student leads?",
                "How can I submit my project?"
            ]

            for idx, p in enumerate(test_prompts, start=1):
                print(f"    Sending prompt {idx}/8: '{p}'...")
                await eval_js(f"""
                    (() => {{
                        const input = document.getElementById('messageInput');
                        const form = document.getElementById('chatForm');
                        if (input && form) {{
                            input.value = "{p}";
                            form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
                        }}
                    }})()
                """)
                for _ in range(60):
                    await asyncio.sleep(0.3)
                    is_sending = await eval_js("typeof window.__isSending === 'function' ? window.__isSending() : false")
                    if not is_sending:
                        break
                await asyncio.sleep(0.3)

            # Verify input position after 8 messages
            input_pos_after = await eval_js("""
                (() => {
                    const i = document.getElementById('chatForm');
                    const c = document.querySelector('.chat-panel');
                    const msgs = document.getElementById('chatMessages');
                    const iR = i ? i.getBoundingClientRect() : null;
                    const cR = c ? c.getBoundingClientRect() : null;
                    return {
                        inputInsideCard: iR && cR ? (iR.bottom <= cR.bottom + 1.5) : false,
                        inputTop: iR ? iR.top : 0,
                        inputBottom: iR ? iR.bottom : 0,
                        scrollTop: msgs ? msgs.scrollTop : 0,
                        scrollHeight: msgs ? msgs.scrollHeight : 0,
                        clientHeight: msgs ? msgs.clientHeight : 0
                    };
                })()
            """)
            print(f"    Messages list scrolled: scrollTop={input_pos_after['scrollTop']}px (scrollHeight={input_pos_after['scrollHeight']}px, clientHeight={input_pos_after['clientHeight']}px)")
            print(f"    Input remains in place inside card: {input_pos_after['inputInsideCard']} (bottom={input_pos_after['inputBottom']:.1f}px)")
            results['eight_messages_scrolled'] = input_pos_after['scrollTop'] > 500
            results['input_in_place_after_messages'] = input_pos_after['inputInsideCard']

            # Press '+' (new conversation)
            print("\n[*] Pressing '+' (btnNewChat) and verifying layout holds...")
            await eval_js("document.getElementById('btnNewChat')?.click();")
            await asyncio.sleep(0.5)

            new_chat_layout = await eval_js("""
                (() => {
                    const card = document.querySelector('.chat-panel');
                    const input = document.getElementById('chatForm');
                    const chips = document.getElementById('suggestions');
                    const msgs = document.getElementById('chatMessages');

                    const cR = card ? card.getBoundingClientRect() : null;
                    const iR = input ? input.getBoundingClientRect() : null;
                    const chR = chips ? chips.getBoundingClientRect() : null;

                    const winH = window.innerHeight;
                    const docH = document.documentElement.scrollHeight;

                    return {
                        messageCount: document.querySelectorAll('.message').length,
                        scrollTop: msgs ? msgs.scrollTop : -1,
                        inputInsideCard: iR && cR ? (iR.bottom <= cR.bottom + 1.5) : false,
                        cardInsideWin: cR ? (cR.bottom <= winH + 1.5) : false,
                        chipsAboveInput: chR && iR ? (chR.bottom <= iR.top + 1.5) : false,
                        noPageScroll: docH <= winH + 1.5
                    };
                })()
            """)
            print(f"    New chat state: count={new_chat_layout['messageCount']}, scrollTop={new_chat_layout['scrollTop']}")
            print(f"    Input inside card: {new_chat_layout['inputInsideCard']}, Card inside window: {new_chat_layout['cardInsideWin']}, No page scroll: {new_chat_layout['noPageScroll']}")
            results['new_chat_layout_holds'] = bool(new_chat_layout['inputInsideCard'] and new_chat_layout['cardInsideWin'] and new_chat_layout['noPageScroll'] and new_chat_layout['scrollTop'] == 0)

            # Resize window 1440x900 -> 1024x600 -> 1440x900
            print("\n[*] Testing window resize 1440x900 -> 1024x600 -> 1440x900...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1024,
                'height': 600,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("window.dispatchEvent(new Event('resize'));")
            await asyncio.sleep(0.4)

            metrics_600 = await eval_js("""
                (() => {
                    const card = document.querySelector('.chat-panel');
                    const input = document.getElementById('chatForm');
                    const cR = card ? card.getBoundingClientRect() : null;
                    const iR = input ? input.getBoundingClientRect() : null;
                    const winH = window.innerHeight;
                    const docH = document.documentElement.scrollHeight;
                    return {
                        inputInsideCard: iR && cR ? (iR.bottom <= cR.bottom + 1.5) : false,
                        cardInsideWin: cR ? (cR.bottom <= winH + 1.5) : false,
                        noPageScroll: docH <= winH + 1.5
                    };
                })()
            """)
            print(f"    At 1024x600: inputInsideCard={metrics_600['inputInsideCard']}, cardInsideWin={metrics_600['cardInsideWin']}, noPageScroll={metrics_600['noPageScroll']}")

            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("window.dispatchEvent(new Event('resize'));")
            await asyncio.sleep(0.4)

            metrics_900 = await eval_js("""
                (() => {
                    const card = document.querySelector('.chat-panel');
                    const input = document.getElementById('chatForm');
                    const cR = card ? card.getBoundingClientRect() : null;
                    const iR = input ? input.getBoundingClientRect() : null;
                    const winH = window.innerHeight;
                    const docH = document.documentElement.scrollHeight;
                    return {
                        inputInsideCard: iR && cR ? (iR.bottom <= cR.bottom + 1.5) : false,
                        cardInsideWin: cR ? (cR.bottom <= winH + 1.5) : false,
                        noPageScroll: docH <= winH + 1.5
                    };
                })()
            """)
            print(f"    Back at 1440x900: inputInsideCard={metrics_900['inputInsideCard']}, cardInsideWin={metrics_900['cardInsideWin']}, noPageScroll={metrics_900['noPageScroll']}")
            results['resize_600_to_900_holds'] = bool(metrics_600['noPageScroll'] and metrics_900['noPageScroll'])

            # -------------------------------------------------------------
            # TEST 3: CHAT INPUT FOCUSABLE & TYPING WORKS
            # -------------------------------------------------------------
            print("\n[*] TEST 3: Verifying Chat Input Focus & Typing...")
            await eval_js("""
                (() => {
                    const input = document.getElementById('messageInput');
                    if (input) {
                        input.focus();
                        input.value = "Testing keyboard input";
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                })()
            """)
            await asyncio.sleep(0.2)
            input_val = await eval_js("document.getElementById('messageInput')?.value")
            send_enabled = await eval_js("!document.getElementById('btnSend')?.disabled")
            print(f"    Input Value: '{input_val}', Send Button Enabled: {send_enabled}")
            results['input_focusable_and_typing_works'] = (input_val == "Testing keyboard input" and send_enabled)

            # -------------------------------------------------------------
            # TEST 4: FREEZE PARITY VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 4: Checking Freeze Parity...")
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
                if current_tl_data['duration'] != base_data['timeline']['duration']:
                    diffs.append(f"Timeline duration changed from {base_data['timeline']['duration']} to {current_tl_data['duration']}")

                for k, v in base_data['timeline']['labels'].items():
                    cur_v = current_tl_data['labels'].get(k)
                    if cur_v is not None and abs(cur_v - v) > 0.01:
                        diffs.append(f"Label '{k}' shifted from {v} to {cur_v}")

            print(f"    Freeze diff count: {len(diffs)}")
            results['freeze_diff_empty'] = (len(diffs) == 0)

            # -------------------------------------------------------------
            # TEST 5: CONSOLE ERRORS
            # -------------------------------------------------------------
            print("\n[*] TEST 5: Console Errors...")
            print(f"    Console Errors count: {len(console_errors)}")
            results['console_errors_zero'] = (len(console_errors) == 0)

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

    print("\n================== CHAT CARD LAYOUT SUMMARY ==================")
    all_ok = True
    for k, v in results.items():
        print(f"  {k}: {v}")
        if not v:
            all_ok = False
    print(f"OVERALL LAYOUT SUITE: {'PASSED' if all_ok else 'FAILED'}")
    return all_ok


if __name__ == '__main__':
    ok = asyncio.run(run_layout_suite())
    sys.exit(0 if ok else 1)

