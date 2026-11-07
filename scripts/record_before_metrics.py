import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as flask_module
from app import app
flask_module.is_api_available = lambda: False

async def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    import threading
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
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
        tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{cdp_port}/json').read().decode('utf-8'))
        ws_url = next(tab for tab in tabs if tab.get('type') == 'page')['webSocketDebuggerUrl']

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

            await send_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 1440,
                'height': 900,
                'deviceScaleFactor': 1,
                'mobile': False
            })

            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Record rotation angle at scrollY = 0, 40, 120, 300, 600
            targets = [0, 40, 120, 300, 600]
            rotations = {}
            for sy in targets:
                # scroll to sy using window.scrollTo
                await eval_js(f"""
                    (() => {{
                        window.scrollTo(0, {sy});
                        if (window.ScrollTrigger) window.ScrollTrigger.update();
                        const lenis = window.__lenis;
                        if (lenis) lenis.scrollTo({sy}, {{ immediate: true, force: true }});
                        const st = window.ScrollTrigger?.getAll()[0];
                        if (st) {{
                            st.scroll({sy});
                            st.update();
                        }}
                    }})()
                """)
                await asyncio.sleep(0.3)
                rot_y = await eval_js("""
                    (() => {
                        const s = window.__sceneState;
                        return s?.logoGroup?.rotation?.y || 0;
                    })()
                """)
                rot_deg = round(-rot_y * 180 / 3.141592653589793, 2)
                rotations[sy] = {"rotY_rad": round(rot_y, 4), "rot_deg": rot_deg}
                print(f"scrollY={sy}px -> rotY={rot_y:.4f} rad ({rot_deg:.2f}°)")

            # Also record pose at key checkpoints
            # Rotation end: progress 0.30
            # Lift start: progress 0.228
            # Phase 3 end: progress 0.62
            # Phase 5 end: progress 0.89
            checkpoints = {
                "lift_start": 0.228,
                "rotation_end": 0.30,
                "phase3_end": 0.62,
                "phase5_end": 0.89
            }
            poses = {}
            for name, prog in checkpoints.items():
                await eval_js(f"""
                    (() => {{
                        const st = window.ScrollTrigger?.getAll()[0];
                        if (st && st.animation) {{
                            st.animation.progress({prog});
                            st.update();
                        }}
                    }})()
                """)
                await asyncio.sleep(0.25)
                pose_data = await eval_js("""
                    (() => {
                        const s = window.__sceneState;
                        const c = s?.camera;
                        const pos = c ? { x: +c.position.x.toFixed(4), y: +c.position.y.toFixed(4), z: +c.position.z.toFixed(4) } : null;
                        const uProgress = s?.morphMaterial?.uniforms?.uProgress?.value ?? null;
                        const uLift = s?.morphMaterial?.uniforms?.uLift?.value ?? null;
                        const cov = typeof window.__getScreenViewportMetrics === 'function' ? window.__getScreenViewportMetrics()?.coveragePct : null;
                        return { pos, uProgress, uLift, screenCoverage: cov };
                    })()
                """)
                poses[name] = pose_data
                print(f"Checkpoint '{name}' (prog={prog}): {json.dumps(pose_data)}")

            out = {
                "rotations_before": rotations,
                "poses_before": poses
            }
            with open('static/metrics_before_deadzone_fix.json', 'w') as f:
                json.dump(out, f, indent=2)
            print("Saved metrics to static/metrics_before_deadzone_fix.json")

    finally:
        edge_proc.terminate()

asyncio.run(main())

