"""Own the two production child processes; never kill unrelated port owners."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAG = ROOT / "restart.flag"


def stop(children):
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def ready(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/" + ("api/version" if port == 8080 else ""), timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def main():
    if ready(8080) or ready(5173):
        raise SystemExit("Existing server detected. Stop the old launcher/core/UI before starting.")
    opened = False
    children = []
    try:
        while True:
            FLAG.unlink(missing_ok=True)
            children = []
            for script in ("main.py", "frontend_server.py"):
                children.append(subprocess.Popen([sys.executable, str(ROOT / script)], cwd=ROOT))
            for _ in range(40):
                if any(child.poll() is not None for child in children):
                    raise SystemExit("Core/UI startup failed; inspect console output.")
                if ready(8080) and ready(5173):
                    break
                time.sleep(0.5)
            else:
                raise SystemExit("Core/UI startup timeout.")
            if not opened:
                import webbrowser
                webbrowser.open("http://127.0.0.1:5173")
                opened = True
            while not FLAG.exists() and all(child.poll() is None for child in children):
                time.sleep(1)
            stop(children)
            children = []
            time.sleep(1)
    finally:
        stop(children)


if __name__ == "__main__":
    main()
