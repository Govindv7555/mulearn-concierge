"""
Capture JSON Snapshot of Current Workspace Objects and Materials before modifications.
"""
import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets

async def capture_snapshot():
    # Find free port for CDP
    cdp_port = 9222
    edge_bin = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    
    # We can launch Edge or connect to existing
    # Let's run a quick Flask server and headless Edge
    import socket, threading
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    flask_port = s.getsockname()[1]
    s.close()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    cdp_port = s.getsockname()[1]
    s.close()

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import app as flask_module
    from app import app
    flask_module.is_api_available = lambda: False

    def run_flask():
        app.run(host='127.0.0.1', port=flask_port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(1.2)

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

            print("Navigating to app...")
            await send_cmd('Page.navigate', {'url': f'http://127.0.0.1:{flask_port}/'})
            await asyncio.sleep(2.5)

            # Ensure sceneState is ready
            for _ in range(20):
                is_ready = await eval_js("Boolean(window.__sceneState && window.__sceneState.isInitialized)")
                if is_ready:
                    break
                await eval_js("""
                    import('/static/js/scene.js').then(m => {
                        window.__sceneState = m.sceneState;
                    });
                """)
                await asyncio.sleep(0.5)

            snapshot = await eval_js("""
                (async () => {
                    const THREE = await import('/static/vendor/three.module.js');
                    const s = window.__sceneState;
                    if (!s || !s.scene) return null;

                    // Set to assembled resting state
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

                    const snapshot = {};

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
                                metalness: mat.metalness !== undefined ? +mat.metalness.toFixed(3) : null,
                                opacity: mat.opacity !== undefined ? +mat.opacity.toFixed(3) : null,
                                transparent: mat.transparent || false,
                                hasMap: Boolean(mat.map)
                            };
                        }

                        snapshot[id] = entry;

                        obj.children.forEach((child, idx) => {
                            const childName = child.name ? child.name : `${child.type}_${idx}`;
                            recordObject(child, `${id}/${childName}`);
                        });
                    }

                    if (s.workspaceGroup) recordObject(s.workspaceGroup, 'workspaceGroup');
                    if (s.roomGroup) recordObject(s.roomGroup, 'roomGroup');

                    return snapshot;
                })()
            """)

            with open('static/verification_snapshot_before.json', 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2)
            print(f"Captured {len(snapshot)} scene nodes into static/verification_snapshot_before.json")

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()

if __name__ == '__main__':
    asyncio.run(capture_snapshot())
