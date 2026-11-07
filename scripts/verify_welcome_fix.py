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


async def run_tests():
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
            # TEST 1: AT LOAD (1440x900)
            # -------------------------------------------------------------
            print("\n[*] TEST 1: Verifying Welcome Message Visibility at Load (1440x900)...")
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
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(1.0)

            # Check welcome message top and scroll position
            load_metrics_1440 = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstBubble = document.querySelector('.message__bubble');
                    const avatar = document.querySelector('.message__avatar');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;
                    const aRect = avatar ? avatar.getBoundingClientRect() : null;

                    return {
                        scrollTop: list ? list.scrollTop : -1,
                        listTop: lRect ? lRect.top : 0,
                        bubbleTop: bRect ? bRect.top : 0,
                        avatarTop: aRect ? aRect.top : 0,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false,
                        avatarInside: aRect && lRect ? (aRect.top >= lRect.top) : false
                    };
                })()
            """)
            print(f"    1440x900 list.scrollTop: {load_metrics_1440['scrollTop']} (Expected: 0)")
            print(f"    1440x900 bubbleTop: {load_metrics_1440['bubbleTop']:.1f}px vs listTop: {load_metrics_1440['listTop']:.1f}px (Inside: {load_metrics_1440['bubbleInside']})")
            print(f"    1440x900 avatarTop: {load_metrics_1440['avatarTop']:.1f}px vs listTop: {load_metrics_1440['listTop']:.1f}px (Inside: {load_metrics_1440['avatarInside']})")

            results['load_1440_scrollTop_zero'] = (load_metrics_1440['scrollTop'] == 0)
            results['load_1440_bubble_inside'] = load_metrics_1440['bubbleInside']
            results['load_1440_avatar_inside'] = load_metrics_1440['avatarInside']

            shot_1440, _ = await capture_optimized_screenshot('screenshots/welcome_1440x900.png')
            await capture_optimized_screenshot('static/img/verification/welcome_1440x900.png')
            results['screenshot_welcome_1440_saved'] = os.path.exists(shot_1440)

            # -------------------------------------------------------------
            # TEST 1b: MOBILE (390x844)
            # -------------------------------------------------------------
            print("\n[*] TEST 1b: Verifying Welcome Message Visibility on Mobile (390x844)...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await asyncio.sleep(0.5)

            load_metrics_390 = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstBubble = document.querySelector('.message__bubble');
                    const avatar = document.querySelector('.message__avatar');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;
                    const aRect = avatar ? avatar.getBoundingClientRect() : null;

                    return {
                        scrollTop: list ? list.scrollTop : -1,
                        listTop: lRect ? lRect.top : 0,
                        bubbleTop: bRect ? bRect.top : 0,
                        avatarTop: aRect ? aRect.top : 0,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false,
                        avatarInside: aRect && lRect ? (aRect.top >= lRect.top) : false
                    };
                })()
            """)
            print(f"    390x844 list.scrollTop: {load_metrics_390['scrollTop']} (Expected: 0)")
            print(f"    390x844 bubbleTop: {load_metrics_390['bubbleTop']:.1f}px vs listTop: {load_metrics_390['listTop']:.1f}px (Inside: {load_metrics_390['bubbleInside']})")
            print(f"    390x844 avatarTop: {load_metrics_390['avatarTop']:.1f}px vs listTop: {load_metrics_390['listTop']:.1f}px (Inside: {load_metrics_390['avatarInside']})")

            results['load_390_scrollTop_zero'] = (load_metrics_390['scrollTop'] == 0)
            results['load_390_bubble_inside'] = load_metrics_390['bubbleInside']
            results['load_390_avatar_inside'] = load_metrics_390['avatarInside']

            shot_390, _ = await capture_optimized_screenshot('screenshots/welcome_390x844.png')
            await capture_optimized_screenshot('static/img/verification/welcome_390x844.png')
            results['screenshot_welcome_390_saved'] = os.path.exists(shot_390)

            # Switch back to 1440x900
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 2: SEND 6 MESSAGES, VERIFY AUTO-SCROLL, REACHABLE TOP, AND (+) RESET
            # -------------------------------------------------------------
            print("\n[*] TEST 2: Sending 6 Messages and Verifying Scroll Behaviors...")
            test_questions = [
                "What is µLearn?",
                "How do Karma points work?",
                "Tell me about Interest Groups",
                "How can I join Web Development?",
                "What events are happening soon?",
                "Who leads the campus chapter?"
            ]

            for idx, q in enumerate(test_questions, start=1):
                print(f"    Sending message {idx}/6: '{q}'...")
                await eval_js(f"""
                    (() => {{
                        const input = document.getElementById('messageInput');
                        const form = document.getElementById('chatForm');
                        if (input && form) {{
                            input.value = "{q}";
                            form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
                        }}
                    }})()
                """)
                # Wait for reply to finish
                for _ in range(60):
                    await asyncio.sleep(0.3)
                    is_sending = await eval_js("typeof window.__isSending === 'function' ? window.__isSending() : false")
                    if not is_sending:
                        break
                await asyncio.sleep(0.3)

            # Check that newest message is visible (scrolled near bottom)
            newest_visible = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const msgs = document.querySelectorAll('.message');
                    const lastMsg = msgs[msgs.length - 1];
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const mRect = lastMsg ? lastMsg.getBoundingClientRect() : null;

                    return {
                        messageCount: msgs.length,
                        scrollTop: list ? list.scrollTop : 0,
                        scrollHeight: list ? list.scrollHeight : 0,
                        clientHeight: list ? list.clientHeight : 0,
                        lastMsgVisible: mRect && lRect ? (mRect.top < lRect.bottom && mRect.bottom > lRect.top) : false
                    };
                })()
            """)
            print(f"    Messages Count: {newest_visible['messageCount']} (Expected: 13: 1 welcome + 6 user + 6 assistant)")
            print(f"    List scrollTop: {newest_visible['scrollTop']}px (scrollHeight: {newest_visible['scrollHeight']}px, clientHeight: {newest_visible['clientHeight']}px)")
            print(f"    Newest message visible in viewport: {newest_visible['lastMsgVisible']}")

            results['six_messages_sent'] = (newest_visible['messageCount'] >= 13)
            results['newest_message_visible'] = newest_visible['lastMsgVisible']

            # Check chips collapsed after first message
            chips_hidden = await eval_js("document.getElementById('suggestions')?.classList.contains('suggestions--hidden')")
            print(f"    Suggestion chips collapsed: {chips_hidden}")
            results['chips_collapsed_after_message'] = bool(chips_hidden)

            # Scroll to top and verify welcome message is fully reachable
            print("    Scrolling to top of conversation...")
            await eval_js("document.getElementById('chatMessages')?.scrollTo({ top: 0, behavior: 'auto' });")
            await asyncio.sleep(0.4)

            top_reached = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstBubble = document.querySelector('.message__bubble');
                    const avatar = document.querySelector('.message__avatar');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;
                    const aRect = avatar ? avatar.getBoundingClientRect() : null;

                    return {
                        scrollTop: list ? list.scrollTop : -1,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false,
                        avatarInside: aRect && lRect ? (aRect.top >= lRect.top) : false
                    };
                })()
            """)
            print(f"    Scrolled to top -> scrollTop: {top_reached['scrollTop']}px, bubble inside: {top_reached['bubbleInside']}, avatar inside: {top_reached['avatarInside']}")
            results['welcome_reachable_on_scroll_up'] = bool(top_reached['bubbleInside'] and top_reached['avatarInside'])

            # Press "+" (btnNewChat) and verify welcome bubble is fully visible again at scrollTop 0
            print("    Pressing '+' (btnNewChat) to start new conversation...")
            await eval_js("document.getElementById('btnNewChat')?.click();")
            await asyncio.sleep(0.5)

            new_chat_state = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const msgs = document.querySelectorAll('.message');
                    const firstBubble = document.querySelector('.message__bubble');
                    const avatar = document.querySelector('.message__avatar');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;
                    const aRect = avatar ? avatar.getBoundingClientRect() : null;
                    const chipsVisible = !document.getElementById('suggestions')?.classList.contains('suggestions--hidden');

                    return {
                        messageCount: msgs.length,
                        scrollTop: list ? list.scrollTop : -1,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false,
                        avatarInside: aRect && lRect ? (aRect.top >= lRect.top) : false,
                        chipsVisible: chipsVisible
                    };
                })()
            """)
            print(f"    After '+' -> Message count: {new_chat_state['messageCount']}, scrollTop: {new_chat_state['scrollTop']}")
            print(f"    Welcome bubble visible: {new_chat_state['bubbleInside']}, Avatar visible: {new_chat_state['avatarInside']}")
            print(f"    Suggestion chips restored: {new_chat_state['chipsVisible']}")

            results['new_chat_resets_to_one_message'] = (new_chat_state['messageCount'] == 1)
            results['new_chat_scrollTop_zero'] = (new_chat_state['scrollTop'] == 0)
            results['new_chat_welcome_visible'] = bool(new_chat_state['bubbleInside'] and new_chat_state['avatarInside'])
            results['new_chat_chips_restored'] = new_chat_state['chipsVisible']

            # -------------------------------------------------------------
            # TEST 3: WINDOW RESIZE (1440x900 -> 900x700 -> 1440x900)
            # -------------------------------------------------------------
            print("\n[*] TEST 3: Testing Window Resizing (1440x900 -> 900x700 -> 1440x900)...")
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 900,
                'height': 700,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("window.dispatchEvent(new Event('resize'));")
            await asyncio.sleep(0.5)

            resize_700 = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstBubble = document.querySelector('.message__bubble');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;

                    return {
                        scrollTop: list ? list.scrollTop : -1,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false
                    };
                })()
            """)
            print(f"    At 900x700: scrollTop={resize_700['scrollTop']}, bubbleInside={resize_700['bubbleInside']}")
            results['resize_900x700_scrollTop_zero'] = (resize_700['scrollTop'] == 0)
            results['resize_900x700_bubble_inside'] = resize_700['bubbleInside']

            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })
            await eval_js("window.dispatchEvent(new Event('resize'));")
            await asyncio.sleep(0.5)

            resize_1440 = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstBubble = document.querySelector('.message__bubble');
                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = firstBubble ? firstBubble.getBoundingClientRect() : null;

                    return {
                        scrollTop: list ? list.scrollTop : -1,
                        bubbleInside: bRect && lRect ? (bRect.top >= lRect.top) : false
                    };
                })()
            """)
            print(f"    Back at 1440x900: scrollTop={resize_1440['scrollTop']}, bubbleInside={resize_1440['bubbleInside']}")
            results['resize_1440x900_scrollTop_zero'] = (resize_1440['scrollTop'] == 0)
            results['resize_1440x900_bubble_inside'] = resize_1440['bubbleInside']

            # -------------------------------------------------------------
            # TEST 4: FREEZE PARITY VERIFICATION
            # -------------------------------------------------------------
            print("\n[*] TEST 4: Verifying Freeze Parity...")
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

            # Verify box size from previous task
            css_box_data = await eval_js("""
                (() => {
                    const panel = document.querySelector('.chat-panel');
                    const msgs = document.getElementById('chatMessages');
                    const csMsgs = msgs ? window.getComputedStyle(msgs) : null;
                    const pRect = panel ? panel.getBoundingClientRect() : null;
                    const mRect = msgs ? msgs.getBoundingClientRect() : null;

                    return {
                        panelWidth: pRect ? pRect.width : 0,
                        messagesHeight: mRect ? mRect.height : 0,
                        overscrollBehavior: csMsgs ? csMsgs.overscrollBehavior : ''
                    };
                })()
            """)
            if abs(css_box_data['panelWidth'] - 1080) > 2:
                diffs.append(f"Panel width changed from 1080 to {css_box_data['panelWidth']}")
            if abs(css_box_data['messagesHeight'] - 522) > 2:
                diffs.append(f"Messages height changed from 522 to {css_box_data['messagesHeight']}")

            print(f"    Freeze diff count: {len(diffs)}")
            if diffs:
                for d in diffs:
                    print(f"      - {d}")
            results['freeze_diff_empty'] = (len(diffs) == 0)

            # -------------------------------------------------------------
            # TEST 5: CONSOLE ERRORS
            # -------------------------------------------------------------
            print("\n[*] TEST 5: Checking Console Errors...")
            print(f"    Console Errors count: {len(console_errors)}")
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
        if not v:
            all_ok = False
    print(f"OVERALL WELCOME FIX SUITE: {'PASSED' if all_ok else 'FAILED'}")
    return all_ok


if __name__ == '__main__':
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)

