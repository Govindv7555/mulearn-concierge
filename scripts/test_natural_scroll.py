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
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False

async def test_natural_scroll_entry():
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

            # Natural mouseWheel scroll down past swap threshold
            print("Dispatching mouseWheel down to trigger swapToChat...")
            for _ in range(30):
                await send_cmd('Input.dispatchMouseEvent', {
                    'type': 'mouseWheel',
                    'x': 720,
                    'y': 450,
                    'deltaX': 0,
                    'deltaY': 250
                })
                await asyncio.sleep(0.04)

            # Wait for swapToChat timeline to complete (2.4s)
            print("Waiting for swapToChat to complete...")
            await asyncio.sleep(3.5)

            # Check scroll positions
            info = await eval_js("""
                (() => {
                    const list = document.getElementById('chatMessages');
                    const bubble = document.querySelector('.message__bubble');
                    const panel = document.querySelector('.chat-panel');
                    const chatSection = document.getElementById('chat');

                    const lRect = list ? list.getBoundingClientRect() : null;
                    const bRect = bubble ? bubble.getBoundingClientRect() : null;

                    return {
                        windowScrollY: window.scrollY,
                        chatSectionScrollTop: chatSection ? chatSection.scrollTop : null,
                        listScrollTop: list ? list.scrollTop : null,
                        listScrollHeight: list ? list.scrollHeight : null,
                        listClientHeight: list ? list.clientHeight : null,
                        bubbleTop: bRect ? bRect.top : null,
                        listTop: lRect ? lRect.top : null,
                        bubbleTopMinusListTop: bRect && lRect ? (bRect.top - lRect.top) : null,
                        bubbleBottomMinusListBottom: bRect && lRect ? (bRect.bottom - lRect.bottom) : null,
                        bubbleHeight: bRect ? bRect.height : null
                    };
                })()
            """)
            print("Natural Scroll Entry Info:", json.dumps(info, indent=2))
            await screenshot('screenshots/natural_scroll_entry_1440x900.png')

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

if __name__ == '__main__':
    asyncio.run(test_natural_scroll_entry())

