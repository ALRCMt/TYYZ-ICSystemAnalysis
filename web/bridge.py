# -*- coding: utf-8 -*-
"""
本地桥：给 web/index.html 调用，跑 libnfc_hardnested.exe 破解 S8/S9 密钥。
启动：python bridge.py
默认监听 http://127.0.0.1:8091
"""
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = r"C:\工具Tools\PCR532"
EXE = os.path.join(BASE, "nfc-bin", "libnfc_hardnested.exe")

STATE = {
    "running": False,
    "done": False,
    "percent": 0.0,
    "lines": [],
    "keys": {},
    "error": None,
    "started": 0,
}
LOCK = threading.Lock()

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.log")

RE_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
RE_KEY = re.compile(r"Key\s*=\s*\[\s*([0-9A-Fa-f]{12})\s*\]")
RE_KEY2 = re.compile(r"(?:Key|KEY)\W{0,4}([0-9A-Fa-f]{12})")


def add_line(text):
    try:
        print(text, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(text + "\n")
    except Exception:
        pass
    with LOCK:
        STATE["lines"].append(text)
        if len(STATE["lines"]) > 200:
            STATE["lines"] = STATE["lines"][-200:]
        m = RE_PCT.search(text)
        if m:
            try:
                STATE["percent"] = max(STATE["percent"], float(m.group(1)))
            except ValueError:
                pass
        m = RE_KEY.search(text)
        if m:
            STATE["keys"][str(len(STATE["keys"]))] = m.group(1).upper()
        else:
            m = RE_KEY2.search(text)
            if m and "Key" in text and "=" in text:
                STATE["keys"][str(len(STATE["keys"]))] = m.group(1).upper()


def run_reset():
    """跑一次 nfc-list.exe，用 libnfc 的标准初始化序列把 PN532 拉回正常状态。"""
    exe = os.path.join(BASE, "nfc-bin", "nfc-list.exe")
    if not os.path.exists(exe):
        return {"ok": False, "output": "找不到 nfc-list.exe"}
    try:
        proc = subprocess.run([exe], cwd=BASE, capture_output=True, timeout=12)
        out = (proc.stdout or b"") + (proc.stderr or b"")
        text = out.decode("gbk", "replace").strip()
        return {"ok": True, "output": text[:3000]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "nfc-list 超时（可能需要手动关闭占用端口的程序）"}
    except Exception as e:
        return {"ok": False, "output": str(e)}


def run_job(known_key, known_block, target_block):
    with LOCK:
        STATE.update(running=True, done=False, percent=0.0, lines=[], keys={}, error=None,
                     started=time.time())
    args = [EXE, known_key, str(known_block), "A", str(target_block), "A"]
    try:
        proc = subprocess.Popen(
            args, cwd=BASE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        )
    except Exception as e:
        with LOCK:
            STATE.update(running=False, done=True, error=f"启动失败: {e}")
        return

    buf = b""
    try:
        while True:
            ch = proc.stdout.read(1)
            if not ch:
                break
            if ch in (b"\r", b"\n"):
                if buf:
                    text = buf.decode("gbk", "replace").strip()
                    buf = b""
                    if text:
                        add_line(text)
            else:
                buf += ch
                if len(buf) > 4096:
                    text = buf.decode("gbk", "replace")
                    buf = b""
                    add_line(text)
    finally:
        if buf:
            add_line(buf.decode("gbk", "replace").strip())
        proc.wait()

    # 兜底：从新生成的 txt 里找 key
    try:
        files = []
        for f in os.listdir(BASE):
            if f.lower().endswith(".txt") and f.lower().startswith("0x"):
                p = os.path.join(BASE, f)
                if os.path.getmtime(p) >= STATE["started"] - 5:
                    files.append(p)
        for p in files:
            txt = open(p, "r", errors="replace").read()
            for m in re.finditer(r"[0-9A-Fa-f]{12}", txt):
                with LOCK:
                    STATE["keys"].setdefault(str(len(STATE["keys"])), m.group(0).upper())
    except Exception:
        pass

    with LOCK:
        STATE["running"] = False
        STATE["done"] = True
        if not STATE["keys"] and not STATE["error"]:
            STATE["error"] = "没有解析到密钥，请查看日志"


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/progress"):
            with LOCK:
                out = dict(STATE)
                out["elapsed"] = round(time.time() - STATE["started"], 1) if STATE["started"] else 0
            self._json(out)
        elif self.path.startswith("/ping"):
            self._json({"ok": True, "exe": EXE, "exe_exists": os.path.exists(EXE)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.startswith("/reset"):
            self._json(run_reset())
            return
        if not self.path.startswith("/crack"):
            self._json({"error": "not found"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._json({"error": "bad json"}, 400)
            return
        with LOCK:
            if STATE["running"]:
                self._json({"error": "已有任务在运行"}, 409)
                return
        known_key = re.sub(r"[^0-9A-Fa-f]", "", str(data.get("knownKey", ""))).upper()
        if len(known_key) != 12:
            self._json({"error": "knownKey 必须是 12 位十六进制"}, 400)
            return
        known_block = int(data.get("knownBlock", 4))
        target_block = int(data.get("targetBlock", 32))
        threading.Thread(target=run_job, args=(known_key, known_block, target_block), daemon=True).start()
        self._json({"ok": True})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    try:
        open(LOG_PATH, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(f"桥已启动: http://127.0.0.1:8091")
    print(f"破解工具: {EXE}  (存在: {os.path.exists(EXE)})")
    print(f"工作目录: {BASE}  (libnfc.conf 指向 pn532_uart:COM3)")
    try:
        ThreadingHTTPServer(("127.0.0.1", 8091), Handler).serve_forever()
    except OSError as e:
        print(f"启动失败：端口 8091 被占用（可能旧桥还开着）: {e}")
        print("请先关闭旧的 bridge.py 窗口，再重新运行。")
