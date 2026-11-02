#!/usr/bin/env python3
"""
Browser client tool for haven.
Sends commands to the persistent browser server at localhost:9222.

SPEC:
{
    "name": "browser_client",
    "description": "Control the persistent headless Firefox browser. Navigate, screenshot, read, click, type, execute JS. The browser stays alive between calls.",
    "args": {
        "cmd": {
            "type": "string",
            "enum": ["goto", "screenshot", "read", "click", "type", "js", "back", "forward", "wait", "refresh", "quit", "status"],
            "description": "Command to send"
        },
        "url": {"type": "string", "description": "URL to navigate to (goto)"},
        "path": {"type": "string", "description": "Screenshot save path (screenshot)"},
        "selector": {"type": "string", "description": "CSS selector (click, type)"},
        "text": {"type": "string", "description": "Text to type"},
        "script": {"type": "string", "description": "JavaScript to execute"},
        "seconds": {"type": "number", "description": "Seconds to wait"}
    }
}
"""
import json
import sys
import urllib.request

PORT = 9222

def send_cmd(cmd, **kwargs):
    data = {"cmd": cmd}
    data.update(kwargs)
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_server():
    """Check if the browser server is running, start it if not."""
    import subprocess
    import os

    pid_file = "/t7/haven/browser.pid"
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status", timeout=2) as resp:
            return json.loads(resp.read())
    except:
        # Try to start server
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                try:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)
                    # Process exists
                except:
                    os.remove(pid_file)

        subprocess.Popen(
            ["python3", "/self/tools/browser_server.py"],
            stdout=open("/t7/haven/browser-server.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        import time
        time.sleep(3)
        # Try again
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/status", timeout=2) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"status": "error", "message": f"Could not start browser server: {e}"}

def main():
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    cmd = args.get("cmd", "status")

    if cmd == "status":
        result = check_server()
    else:
        # Ensure server is running first
        check_server()

        result = send_cmd(
            cmd=cmd,
            url=args.get("url"),
            path=args.get("path"),
            selector=args.get("selector"),
            text=args.get("text"),
            script=args.get("script"),
            seconds=args.get("seconds"),
        )

    print(json.dumps(result))

if __name__ == "__main__":
    main()
