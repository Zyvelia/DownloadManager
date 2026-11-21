"""Local download service and desktop dashboard."""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PACKAGE = os.environ.get("ZDM_PACKAGE")
DATA = Path(os.environ.get("ZDM_DATA", Path.home() / ".z-download-manager"))
DATA.mkdir(parents=True, exist_ok=True)
DATABASE = DATA / "state.json"
DEFAULT_PANELS = ["speed", "browser"]
state = json.loads(DATABASE.read_text()) if DATABASE.exists() else {
    "jobs": [], "destination": str(Path.home() / "Downloads"), "limit": 0,
    "parallel": 2, "panels": DEFAULT_PANELS[:], "key": secrets.token_urlsafe(24),
    "hold": False, "last": None,
}
for job in state["jobs"]:
    if job["status"] in {"Downloading", "Pausing"}:
        job.update(status="Paused", speed=0)
lock = threading.RLock()
running = {}
history = []
session_key = secrets.token_urlsafe(24)
last_ping = 0
closing = threading.Event()


def save():
    temp = DATABASE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(DATABASE)


def enqueue(data, source):
    url = str(data.get("url", "")).strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("Enter a direct HTTP or HTTPS link.")
    destination = str(data.get("destination") or state["destination"]) if source == "Desktop" else state["destination"]
    folder = Path(destination).expanduser()
    if not folder.is_absolute():
        raise ValueError("Enter an absolute destination folder.")
    scheduled = float(data.get("scheduled") or 0) if source == "Desktop" else 0
    name = unquote(parsed.path.rsplit("/", 1)[-1])
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(". ")[:160] or "download"
    if re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I):
        name = "_" + name
    job = dict(id=uuid.uuid4().hex, url=url, name=name, destination=str(folder),
               scheduled=scheduled, status="Scheduled" if scheduled > time.time() else "Queued",
               source=source, size=0, received=0, speed=0, error="", validator="")
    state["jobs"].append(job)
    if source == "Browser":
        state["last"] = {"name": name, "time": time.time()}
    save()
    return job


def transfer(job, stop):
    folder = Path(job["destination"])
    partial = folder / (".zdm-" + job["id"] + ".part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        offset = partial.stat().st_size if partial.exists() and job["validator"] else 0
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers.update({"Range": f"bytes={offset}-", "If-Range": job["validator"]})
        request = Request(job["url"], headers=headers)
        with urlopen(request, timeout=12) as response:
            resumed = response.status == 206
            content_range = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if resumed and (not offset or not content_range or int(content_range[1]) != offset):
                raise ValueError("Server returned an unexpected byte range.")
            if not resumed:
                offset = 0
            length = int(response.headers.get("Content-Length") or 0)
            total = int(content_range[3]) if resumed else length
            etag = response.headers.get("ETag", "")
            validator = etag if etag and not etag.startswith("W/") else response.headers.get("Last-Modified", "")
            with partial.open("ab" if resumed else "wb") as output:
                with lock:
                    job.update(size=total, received=offset, validator=validator)
                    save()
                started = time.monotonic()
                sample_time, sample_bytes = started, offset
                received = offset
                while not stop.is_set():
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    now = time.monotonic()
                    with lock:
                        cap = state["limit"] * 1024 / max(1, len(running))
                        job["received"] = received
                        if now - sample_time >= .4:
                            job["speed"] = (received - sample_bytes) / (now - sample_time)
                            sample_time, sample_bytes = now, received
                    if cap:
                        stop.wait(len(chunk) / cap)
        with lock:
            if stop.is_set():
                job["status"] = "Paused"
            else:
                if total and received != total:
                    raise OSError("Transfer ended before the entire file arrived.")
                target = folder / job["name"]
                counter = 1
                while True:
                    try:
                        target.touch(exist_ok=False)
                        break
                    except FileExistsError:
                        target = folder / f"{Path(job['name']).stem} ({counter}){Path(job['name']).suffix}"
                        counter += 1
                try:
                    partial.replace(target)
                except OSError:
                    target.unlink()
                    raise
                job.update(status="Completed", size=received, name=target.name)
    except (OSError, ValueError, HTTPException) as error:
        with lock:
            job.update(status="Paused" if stop.is_set() else "Failed",
                       error="" if stop.is_set() else str(error))
    finally:
        with lock:
            if job["status"] in {"Downloading", "Pausing"}:
                job.update(status="Failed", error="Transfer interrupted.")
            job["speed"] = 0
            running.pop(job["id"], None)
            save()


def scheduler():
    while not closing.wait(.5):
        with lock:
            history.append(sum(job["speed"] for job in state["jobs"]))
            del history[:-600]
            if state["hold"]:
                continue
            for job in state["jobs"]:
                if len(running) >= state["parallel"]:
                    break
                if job["status"] not in {"Queued", "Scheduled"} or job["scheduled"] > time.time():
                    continue
                event = threading.Event()
                running[job["id"]] = event
                job.update(status="Downloading", error="")
                save()
                threading.Thread(target=transfer, args=(job, event)).start()


class Handler(BaseHTTPRequestHandler):
    def reply(self, value, code=200, mime="application/json"):
        body = json.dumps(value).encode() if mime == "application/json" else value.encode()
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def host_valid(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def authenticated(self, token):
        return secrets.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + token).encode())

    def do_GET(self):
        if not self.host_valid():
            return self.reply({"error": "Invalid host"}, 403)
        files = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
                 "/ui.js": ("ui.js", "application/javascript")}
        if self.path == "/package" and PACKAGE:
            body = Path(PACKAGE).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="Zs-Download-Manager.zip"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in files:
            filename, mime = files[self.path]
            content = (ROOT / filename).read_text(encoding="utf-8").replace("__SESSION_KEY__", session_key)
            if self.path == "/":
                content = content.replace("<!-- PACKAGE -->", '<a href="/package">Download app ZIP</a>' if PACKAGE else "")
            return self.reply(content, mime=mime)
        if self.path == "/api/state" and self.authenticated(session_key):
            with lock:
                return self.reply({**state, "history": history, "connected": time.time() - last_ping < 95})
        self.reply({"error": "Unavailable"}, 404)

    def do_POST(self):
        global last_ping
        if not self.host_valid():
            return self.reply({"error": "Invalid host"}, 403)
        browser = self.path in {"/extension/send", "/extension/ping"}
        if not self.authenticated(state["key"] if browser else session_key):
            return self.reply({"error": "Check the connection key."}, 401)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 32768:
                raise ValueError("Invalid request size.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Invalid request body.")
            if self.path == "/api/folder":
                script = ("import sys, tkinter as tk; from tkinter import filedialog; "
                          "root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True); "
                          "print(filedialog.askdirectory(initialdir=sys.argv[1])); root.destroy()")
                result = subprocess.run([sys.executable, "-c", script, state["destination"]],
                                        capture_output=True, text=True)
                if result.returncode:
                    raise ValueError("Folder picker unavailable. Enter the destination path manually.")
                return self.reply({"destination": result.stdout.strip()})
            with lock:
                if browser:
                    last_ping = time.time()
                    if self.path.endswith("/send"):
                        enqueue(data, "Browser")
                elif self.path == "/api/add":
                    enqueue(data, "Desktop")
                elif self.path == "/api/panels":
                    allowed = {"speed", "browser", "recent", "details"}
                    state["panels"] = list(dict.fromkeys(item for item in data["panels"] if item in allowed))
                elif self.path == "/api/settings":
                    destination = Path(data["destination"]).expanduser()
                    if not destination.is_absolute():
                        raise ValueError("Enter an absolute destination folder.")
                    state.update(destination=str(destination), parallel=max(1, min(8, int(data["parallel"]))),
                                 limit=max(0, int(data["limit"])))
                elif self.path == "/api/hold":
                    state["hold"] = bool(data["hold"])
                    if state["hold"]:
                        for job in state["jobs"]:
                            if job["id"] in running:
                                job["status"] = "Pausing"
                                running[job["id"]].set()
                    else:
                        for job in state["jobs"]:
                            if job["status"] == "Paused":
                                job["status"] = "Queued"
                elif self.path == "/api/action":
                    job = next(item for item in state["jobs"] if item["id"] == data["id"])
                    if data["action"] == "pause" and job["id"] in running:
                        job["status"] = "Pausing"
                        running[job["id"]].set()
                    elif data["action"] == "pause" and job["status"] == "Queued":
                        job["status"] = "Paused"
                    if data["action"] == "start" and job["status"] in {"Paused", "Failed", "Scheduled"}:
                        job.update(status="Queued", scheduled=0)
                else:
                    return self.reply({"error": "Unavailable"}, 404)
                save()
                self.reply({"ok": True})
        except (ValueError, KeyError, TypeError, StopIteration, OSError) as error:
            self.reply({"error": str(error) or "Invalid request."}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", options.port), Handler)
    save()
    threading.Thread(target=scheduler, daemon=True).start()
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"Z's Download Manager is running at {address}", flush=True)
    if not options.no_browser:
        candidates = [shutil.which(name) for name in ("msedge", "chrome", "google-chrome", "chromium")]
        if os.name == "nt":
            for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
                if base := os.environ.get(variable):
                    candidates.extend(str(Path(base) / name) for name in (
                        "Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"))
        browser = next((path for path in candidates if path and Path(path).is_file()), None)
        if browser:
            subprocess.Popen([browser, "--app=" + address])
        else:
            webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        closing.set()
        with lock:
            for event in running.values():
                event.set()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
