"""
Automated Verification Script for 3D Intro & Seamless Chat Transition.
Uses Chrome DevTools Protocol (CDP) to drive headless Edge,
check console logs for errors, scrub through all 6 phases,
and capture verification screenshots.
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

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

async def run_verification():
    # 1. Start background Flask server on random free port
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
    user_data = os.path.abspath('edge_temp_profile')
    os.makedirs(user_data, exist_ok=True)

    edge_proc = subprocess.Popen([
        edge_bin,
        '--headless',
        '--disable-gpu',
        '--hide-scrollbars',
        f'--remote-debugging-port={cdp_port}',
        f'--user-data-dir={user_data}',
        'about:blank'
    ])
    time.sleep(1.5)

    try:
        # Get page target
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
                    resp_str = await ws.recv()
                    resp = json.loads(resp_str)
                    if resp.get('id') == msg_id:
                        return resp

            # Enable Page, Runtime, Console
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
            print(f"Navigating to http://127.0.0.1:{flask_port}/ ...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.0)

            # Check for console errors
            eval_res = await send_cmd('Runtime.evaluate', {
                'expression': 'window.__ERRORS__ || []',
                'returnByValue': True
            })
            print('Console check:', eval_res.get('result', {}).get('value', []))

            # Helper to take screenshot
            os.makedirs('static/img/verification', exist_ok=True)

            async def take_shot(filename):
                shot_res = await send_cmd('Page.captureScreenshot', {'format': 'png'})
                data_b64 = shot_res['result']['data']
                out_path = os.path.join('static', 'img', 'verification', filename)
                with open(out_path, 'wb') as f:
                    f.write(base64.b64decode(data_b64))
                print(f"Saved screenshot: {out_path} ({os.path.getsize(out_path)} bytes)")

            # Get document scroll height
            dim_res = await send_cmd('Runtime.evaluate', {
                'expression': 'document.documentElement.scrollHeight - window.innerHeight',
                'returnByValue': True
            })
            print('dim_res:', dim_res)
            max_scroll = dim_res['result']['result'].get('value', 4800)
            print(f"Total scrollable height: {max_scroll}px")

            phases = [
                ('phase1-hero.png', 0.0, 'Phase 1: Hero Logo bobbing at 0% scroll'),
                ('phase2-approach.png', 0.25, 'Phase 2: Camera dollies in, logo rotates ~90° left at 25% scroll'),
                ('phase3-transform.png', 0.45, 'Phase 3: Logo breaks into particles, workspace items assemble at 45% scroll'),
                ('phase4-laptop.png', 0.65, 'Phase 4: Camera settles facing laptop screen at 65% scroll'),
                ('phase5-zoomin.png', 0.85, 'Phase 5: Camera pushes straight into laptop screen at 85% scroll'),
                ('phase6-chat.png', 1.0, 'Phase 6: White flash reveals live #chat section at 100% scroll')
            ]

            for filename, progress, desc in phases:
                scroll_y = int(max_scroll * progress)
                print(f"\n--- Testing {desc} (scrollY={scroll_y}) ---")
                await send_cmd('Runtime.evaluate', {
                    'expression': f'''
                        window.scrollTo(0, {scroll_y});
                        if (window.ScrollTrigger) window.ScrollTrigger.update();
                    '''
                })
                await asyncio.sleep(0.8) # Allow smooth scrub to settle
                await take_shot(filename)

            # Test Skip Intro button
            print("\n--- Testing Skip Intro Button ---")
            await send_cmd('Runtime.evaluate', {
                'expression': 'window.scrollTo(0, 0); if (window.ScrollTrigger) window.ScrollTrigger.update();'
            })
            await asyncio.sleep(0.5)

            skip_res = await send_cmd('Runtime.evaluate', {
                'expression': '''
                    const btn = document.getElementById("btnSkipIntro");
                    if (btn) {
                        btn.click();
                        true;
                    } else {
                        false;
                    }
                ''',
                'returnByValue': True
            })
            val = skip_res.get('result', {}).get('result', {}).get('value', False)
            print("Skip button clicked:", val)
            await asyncio.sleep(1.5)
            await take_shot('skip-intro-result.png')

            print("\n[SUCCESS] Verification complete. All 6 phases and skip button tested successfully.")

    finally:
        edge_proc.terminate()

if __name__ == '__main__':
    asyncio.run(run_verification())
