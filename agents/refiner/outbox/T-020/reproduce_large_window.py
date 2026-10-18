"""Run a local viewer and measure real DOM playback controls in headless Edge.

Requires requests and websocket-client. Run from agents/refiner with:
  python outbox/T-020/reproduce_large_window.py --script path/to/odb_viewer_web.py
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
import websocket


ROOT = Path(__file__).resolve().parents[2]
NPZ = ROOT.parent / "drafter/inbox/T-012/v500_viewer.npz"
VIEWER_DIR = ROOT.parent.parent / "verification/roar"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CDP:
    def __init__(self, port):
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                tabs = requests.get(f"http://127.0.0.1:{port}/json", timeout=1).json()
                target = next(t for t in tabs if t["type"] == "page")
                self.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
                self.seq = 0
                return
            except Exception:
                time.sleep(.2)
        raise RuntimeError("Edge CDP unavailable")

    def call(self, method, params=None):
        self.seq += 1
        seq = self.seq
        self.ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == seq:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def js(self, expression):
        r = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"])
        return r.get("result", {}).get("value")


def wait_for(url, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.get(url, timeout=1).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(.2)
    raise RuntimeError(f"Viewer unavailable: {url}")


def measure(script, width, height, dpr, rendering="remote"):
    port, cdp_port = free_port(), free_port()
    server_log = tempfile.TemporaryFile(mode="w+t")
    server = subprocess.Popen(["python", str(script), str(NPZ), "--port", str(port), "--host", "127.0.0.1", "--no-browser", "--viewer-dir", str(VIEWER_DIR), "--rendering", rendering], stdout=server_log, stderr=subprocess.STDOUT)
    browser = None
    try:
        wait_for(f"http://127.0.0.1:{port}")
        browser = subprocess.Popen([str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-allow-origins=*", f"--remote-debugging-port={cdp_port}", f"--window-size={width},{height}", f"--force-device-scale-factor={dpr}", f"--user-data-dir={tempfile.mkdtemp(prefix='edge-t020-')}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = CDP(cdp_port)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}"})
        ready = time.time() + 45
        while time.time() < ready:
            if cdp.js("document.body && document.body.innerText.toLowerCase().includes('play') && document.body.innerText.includes('Frame')"):
                break
            time.sleep(.2)
        else:
            raise RuntimeError(f"Viewer UI did not load: {cdp.js('({url:location.href,text:document.body?.innerText?.slice(0,1000)})')}")
        cdp.js("window.sent=[];let oldSend=WebSocket.prototype.send;WebSocket.prototype.send=function(x){window.sent.push({t:performance.now(),data:String(x).slice(0,300)});return oldSend.call(this,x)}")
        viewport = cdp.js("({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})")
        cdp.js("""window.samples=[]; window.obs=new MutationObserver(()=>{let x=document.body.innerText.match(/Frame (\\d+)\\/(\\d+)/);if(x){let n=+x[1],s=window.samples;if(!s.length||s[s.length-1].n!==n)s.push({n,t:performance.now()})}});window.obs.observe(document.body,{subtree:true,childList:true,characterData:true});""")
        btn = "[...document.querySelectorAll('button')].find(b=>b.innerText.trim().toLowerCase()===%s)"
        def click(label):
            return cdp.js(f"(()=>{{let b={btn % json.dumps(label.lower())};if(!b)return false;b.click();return true}})()")
        if not click("Play"):
            raise RuntimeError("Play button absent")
        time.sleep(5)
        status_play = cdp.js("({label:document.body.innerText.match(/Frame \\d+\\/\\d+/)?.[0],buttons:[...document.querySelectorAll('button')].map(x=>x.innerText.trim()).filter(Boolean),samples:window.samples.length})")
        t_pause = cdp.js("performance.now()")
        pause_clicked = click("Pause")
        sent_after_pause = cdp.js("window.sent.slice(-5)")
        time.sleep(2)
        t_end = cdp.js("performance.now()")
        status_pause = cdp.js("({label:document.body.innerText.match(/Frame \\d+\\/\\d+/)?.[0],play:[...document.querySelectorAll('button')].map(x=>x.innerText.trim()).find(x=>x==='PLAY'||x==='PAUSE')})")
        samples = cdp.js("window.samples")
        post = [s for s in samples if s["t"] >= t_pause]
        changes = [((b["n"] - a["n"]) % 150) for a,b in zip(samples,samples[1:])]
        active = [s for s in samples if s["t"] < t_pause and s["t"] >= t_pause-4000]
        fps = (len(active)-1)/((active[-1]["t"]-active[0]["t"])/1000) if len(active)>1 else 0
        # While paused, the step should increment one frame and the camera buttons should remain clickable.
        step_clicked = cdp.js(f"(()=>{{let b=document.querySelector('button .mdi-step-forward');if(!b)return false;b.closest('button').click();return true}})()")
        time.sleep(.5)
        after_step = cdp.js("document.body.innerText.match(/Frame \\d+\\/\\d+/)?.[0]")
        click("Play")
        time.sleep(.5)
        camera_clicked = click("Symmetry")
        time.sleep(.5)
        camera_playing = cdp.js("({label:document.body.innerText.match(/Frame \\d+\\/\\d+/)?.[0],play:[...document.querySelectorAll('button')].map(x=>x.innerText.trim()).find(x=>x==='PLAY'||x==='PAUSE')})")
        speed_point = cdp.js("(()=>{let i=[...document.querySelectorAll('input')].find(x=>x.value==='1');let r=i?.closest('.v-field')?.getBoundingClientRect();return r?{x:r.x+r.width/2,y:r.y+r.height/2}:null})()")
        if speed_point:
            cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":speed_point["x"],"y":speed_point["y"],"button":"left","clickCount":1})
            cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":speed_point["x"],"y":speed_point["y"],"button":"left","clickCount":1})
        time.sleep(.2)
        speed_options = cdp.js("[...document.querySelectorAll('.v-list-item')].map(x=>x.innerText.trim())")
        speed_clicked = cdp.js("(()=>{let x=[...document.querySelectorAll('.v-list-item')].find(x=>x.innerText.trim()==='2');if(!x)return false;x.click();return true})()")
        time.sleep(.5)
        speed_display = cdp.js("[...document.querySelectorAll('input')].map(x=>({value:x.value,aria:x.getAttribute('aria-label')}))")
        step_playing_clicked = cdp.js("(()=>{let b=document.querySelector('button .mdi-step-forward');if(!b)return false;b.closest('button').click();return true})()")
        time.sleep(1)
        step_playing_status = cdp.js("({label:document.body.innerText.match(/Frame \\d+\\/\\d+/)?.[0],play:[...document.querySelectorAll('button')].map(x=>x.innerText.trim()).find(x=>x==='PLAY'||x==='PAUSE')})")
        return {"size": [width,height], "dpr":dpr, "viewport":viewport, "status_play":status_play, "status_pause":status_pause, "pause_clicked":pause_clicked, "sent_after_pause":sent_after_pause, "pause_last_frame_ms": round(post[-1]["t"]-t_pause,1) if post else 0, "pause_observed_ms": round(t_end-t_pause,1), "post_pause_frames":len(post), "fps_last_4s":round(fps,2), "max_gap":max(changes,default=0), "skipped":sum(max(0,g-1) for g in changes), "step_clicked":step_clicked, "after_step":after_step, "camera_clicked_while_playing":camera_clicked, "camera_playing":camera_playing, "speed_options":speed_options, "speed_clicked":speed_clicked, "speed_display":speed_display, "step_playing_clicked":step_playing_clicked, "step_playing_status":step_playing_status, "samples":samples}
    finally:
        if browser:
            browser.terminate()
            try: browser.wait(timeout=5)
            except subprocess.TimeoutExpired: browser.kill()
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill()
        server_log.seek(0)
        log = server_log.read()
        if "Traceback" in log:
            print(log[-4000:], file=sys.stderr)
        server_log.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--script", type=Path, required=True)
    p.add_argument("--size", default="1920x1080")
    p.add_argument("--dpr", type=int, default=1)
    p.add_argument("--rendering", choices=["remote", "local"], default="remote")
    a = p.parse_args()
    w,h = map(int,a.size.split("x"))
    print(json.dumps(measure(a.script.resolve(),w,h,a.dpr,a.rendering), indent=2))
