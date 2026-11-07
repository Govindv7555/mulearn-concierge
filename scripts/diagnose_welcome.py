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

async def diagnose():
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
                    if resp.get('id') == msg_id:
                        return resp

            await send_cmd('Page.enable')
            await send_cmd('Runtime.enable')

            async def eval_js(expr):
                res = await send_cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
                return res.get('result', {}).get('result', {}).get('value')

            async def screenshot(filepath):
                snap = await send_cmd('Page.captureScreenshot', {'format': 'png'})
                img_data = base64.b64decode(snap['result']['data'])
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                print(f"Saved screenshot {filepath}")

            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Skip intro to enter chat
            await eval_js("document.getElementById('btnSkipIntro')?.click();")
            await asyncio.sleep(1.0)

            # Diagnose message area
            diag = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstMsg = document.querySelector('.message');
                    const firstBubble = document.querySelector('.message__bubble');
                    const lRect = list?.getBoundingClientRect();
                    const mRect = firstMsg?.getBoundingClientRect();
                    const bRect = firstBubble?.getBoundingClientRect();

                    const csList = list ? window.getComputedStyle(list) : null;
                    const csMsg = firstMsg ? window.getComputedStyle(firstMsg) : null;
                    const csBubble = firstBubble ? window.getComputedStyle(firstBubble) : null;

                    return {
                        list: {
                            scrollTop: list?.scrollTop,
                            scrollHeight: list?.scrollHeight,
                            clientHeight: list?.clientHeight,
                            rect: lRect ? { top: lRect.top, bottom: lRect.bottom, height: lRect.height } : null,
                            display: csList?.display,
                            flexDirection: csList?.flexDirection,
                            justifyContent: csList?.justifyContent,
                            alignItems: csList?.alignItems,
                            alignContent: csList?.alignContent,
                            paddingTop: csList?.paddingTop,
                            overflowY: csList?.overflowY
                        },
                        firstMsg: {
                            rect: mRect ? { top: mRect.top, bottom: mRect.bottom, height: mRect.height } : null,
                            marginTop: csMsg?.marginTop,
                            marginBottom: csMsg?.marginBottom,
                            alignSelf: csMsg?.alignSelf
                        },
                        firstBubble: {
                            rect: bRect ? { top: bRect.top, bottom: bRect.bottom, height: bRect.height } : null,
                            padding: csBubble?.padding
                        },
                        bubbleTopVsListTop: bRect && lRect ? (bRect.top - lRect.top) : null,
                        msgTopVsListTop: mRect && lRect ? (mRect.top - lRect.top) : null
                    };
                })()
            """)
            print("Diagnostic Data:", json.dumps(diag, indent=2))
            await screenshot('screenshots/diagnose_welcome_1440x900.png')

            # Let's also check mobile 390x844
            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 390,
                'height': 844,
                'deviceScaleFactor': 2,
                'mobile': True
            })
            await asyncio.sleep(0.5)

            diag_mobile = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const firstMsg = document.querySelector('.message');
                    const firstBubble = document.querySelector('.message__bubble');
                    const lRect = list?.getBoundingClientRect();
                    const mRect = firstMsg?.getBoundingClientRect();
                    const bRect = firstBubble?.getBoundingClientRect();
                    return {
                        list: {
                            scrollTop: list?.scrollTop,
                            scrollHeight: list?.scrollHeight,
                            clientHeight: list?.clientHeight,
                            rect: lRect ? { top: lRect.top, bottom: lRect.bottom, height: lRect.height } : null
                        },
                        firstMsg: {
                            rect: mRect ? { top: mRect.top, bottom: mRect.bottom, height: mRect.height } : null
                        },
                        firstBubble: {
                            rect: bRect ? { top: bRect.top, bottom: bRect.bottom, height: bRect.height } : null
                        },
                        bubbleTopVsListTop: bRect && lRect ? (bRect.top - lRect.top) : null
                    };
                })()
            """)
            print("Mobile Diagnostic Data:", json.dumps(diag_mobile, indent=2))
            await screenshot('screenshots/diagnose_welcome_390x844.png')

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

if __name__ == '__main__':
    asyncio.run(diagnose())

