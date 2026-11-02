#!/usr/bin/env python3
"""
Persistent browser server for haven.
Listens on localhost:9222 for JSON commands over stdin/stdout or a simple HTTP interface.
Maintains a single Firefox instance that stays alive between commands.

Commands (JSON on stdin, JSON response on stdout):
  {"cmd": "goto", "url": "https://example.com"}
  {"cmd": "screenshot", "path": "/path/to/shot.png"}
  {"cmd": "read"}
  {"cmd": "click", "selector": "#btn"}
  {"cmd": "type", "selector": "#input", "text": "hello"}
  {"cmd": "js", "script": "return document.title"}
  {"cmd": "back"}
  {"cmd": "wait", "seconds": 5}
  {"cmd": "quit"}
"""
import json
import os
import sys
import signal
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DRIVER_PATH = "/usr/local/bin/geckodriver"
SCREENSHOT_DIR = "/t7/haven/browser-screenshots"
PORT = 9222
PID_FILE = "/t7/haven/browser.pid"

os.environ["DISPLAY"] = ":98"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

driver = None

def ensure_driver():
    global driver
    if driver is None:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--width=1280")
        options.add_argument("--height=720")
        service = Service(DRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(30)
    return driver

def handle_cmd(data):
    d = ensure_driver()
    cmd = data.get("cmd", "")

    try:
        if cmd == "goto":
            d.get(data["url"])
            return {
                "status": "ok",
                "url": d.current_url,
                "title": d.title
            }
        elif cmd == "screenshot":
            path = data.get("path")
            if path is None:
                path = os.path.join(SCREENSHOT_DIR, f"screenshot-{int(time.time())}.png")
            d.save_screenshot(path)
            return {"status": "ok", "path": path, "size": os.path.getsize(path)}
        elif cmd == "read":
            body = d.find_element(By.TAG_NAME, "body")
            text = body.text
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            return {
                "status": "ok",
                "url": d.current_url,
                "title": d.title,
                "text": "\n".join(lines[:300])
            }
        elif cmd == "click":
            elem = WebDriverWait(d, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, data["selector"]))
            )
            elem.click()
            time.sleep(0.5)
            return {"status": "ok", "selector": data["selector"]}
        elif cmd == "type":
            elem = WebDriverWait(d, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, data["selector"]))
            )
            elem.clear()
            elem.send_keys(data["text"])
            return {"status": "ok", "selector": data["selector"]}
        elif cmd == "js":
            result = d.execute_script(data["script"])
            return {"status": "ok", "result": result}
        elif cmd == "back":
            d.back()
            return {"status": "ok", "url": d.current_url, "title": d.title}
        elif cmd == "forward":
            d.forward()
            return {"status": "ok", "url": d.current_url, "title": d.title}
        elif cmd == "wait":
            time.sleep(data.get("seconds", 1))
            return {"status": "ok"}
        elif cmd == "refresh":
            d.refresh()
            return {"status": "ok", "url": d.current_url, "title": d.title}
        elif cmd == "quit":
            d.quit()
            global driver
            driver = None
            return {"status": "quit"}
        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class BrowserHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode())
            return

        result = handle_cmd(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if driver:
                self.wfile.write(json.dumps({
                    "status": "running",
                    "url": driver.current_url,
                    "title": driver.title
                }).encode())
            else:
                self.wfile.write(json.dumps({"status": "no browser"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs

def run_server():
    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Handle shutdown
    def shutdown(sig, frame):
        if driver:
            driver.quit()
        sys.exit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server = HTTPServer(("127.0.0.1", PORT), BrowserHandler)
    print(f"Browser server running on port {PORT}", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    run_server()
