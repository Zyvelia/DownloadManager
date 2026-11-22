"""Download queue and optional browser extension bridge."""
import argparse
import json
import math
import os
import re
import secrets
import threading
import time
import uuid
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

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
        job.update(status="Queued" if job.pop("queue_hold", False) else "Paused", speed=0)
lock = threading.RLock()
running = {}
history = []
last_ping = 0
closing = threading.Event()


def save():
    temp = DATABASE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(DATABASE)


def make_job(data, source):
    url = str(data.get("url", "")).strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("Enter a direct HTTP or HTTPS link.")
    destination = str(data.get("destination") or state["destination"]) if source == "Desktop" else state["destination"]
    folder = Path(destination).expanduser()
    if not folder.is_absolute():
        raise ValueError("Enter an absolute destination folder.")
    scheduled = float(data.get("scheduled") or 0) if source == "Desktop" else 0
    if not math.isfinite(scheduled) or scheduled < 0:
        raise ValueError("Choose a valid start time.")
    name = unquote(parsed.path.rsplit("/", 1)[-1])
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(". ")[:160] or "download"
    if re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I):
        name = "_" + name
    return dict(id=uuid.uuid4().hex, url=url, name=name, destination=str(folder),
               scheduled=scheduled, status="Scheduled" if scheduled > time.time() else "Queued",
               source=source, size=0, received=0, speed=0, error="", validator="",
               added=time.time(), priority=0)


def enqueue(data, source):
    with lock:
        job = make_job(data, source)
        state["jobs"].append(job)
        if source == "Browser":
            state["last"] = {"name": job["name"], "time": time.time()}
        save()
        return job


def enqueue_many(urls, destination, scheduled):
    if not urls:
        raise ValueError("Paste at least one download link.")
    with lock:
        jobs = [make_job({"url": url, "destination": destination, "scheduled": scheduled}, "Desktop")
                for url in urls]
        state["jobs"].extend(jobs)
        try:
            save()
        except OSError:
            del state["jobs"][-len(jobs):]
            raise
        return jobs


def transfer(job, stop):
    folder = Path(job["destination"])
    partial = folder / (".zdm-" + job["id"] + ".part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        offset = partial.stat().st_size if partial.exists() and job["validator"] else 0
        if job["size"] and offset >= job["size"]:
            offset = 0
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers.update({"Range": f"bytes={offset}-", "If-Range": job["validator"]})
        request = Request(job["url"], headers=headers)
        with urlopen(request, timeout=12) as response:
            resumed = response.status == 206
            content_range = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if resumed and (not offset or not content_range or int(content_range[1]) != offset
                            or int(content_range[2]) + 1 != int(content_range[3])):
                raise ValueError("Server returned an unexpected byte range.")
            if not resumed:
                offset = 0
            length = int(response.headers.get("Content-Length") or 0)
            total = int(content_range[3]) if resumed else length
            etag = response.headers.get("ETag", "")
            validator = etag if etag and not etag.startswith("W/") else response.headers.get("Last-Modified", "")
            if resumed:
                if validator and validator != job["validator"]:
                    raise ValueError("The remote file changed during resume.")
                validator = job["validator"]
                if length and length != total - offset:
                    raise ValueError("Server returned an inconsistent byte range.")
            with partial.open("ab" if resumed else "wb") as output:
                with lock:
                    job.update(size=total, received=offset, validator=validator)
                    save()
                started = time.monotonic()
                sample_time, sample_bytes = started, offset
                received = offset
                while not stop.is_set():
                    chunk_started = time.monotonic()
                    chunk = response.read1(64 * 1024)
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
                        stop.wait(max(0, len(chunk) / cap - (now - chunk_started)))
        with lock:
            if stop.is_set():
                job["status"] = "Queued" if job.get("queue_hold") else "Paused"
                job.pop("queue_hold", None)
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
                job.update(status="Completed", size=received, name=target.name, completed=time.time())
    except (OSError, ValueError, HTTPException) as error:
        with lock:
            status = ("Queued" if job.pop("queue_hold", False) else "Paused") if stop.is_set() else "Failed"
            job.update(status=status,
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
            for job in sorted(state["jobs"], key=lambda item: -item.get("priority", 0)):
                if len(running) >= state["parallel"]:
                    break
                if job["status"] not in {"Queued", "Scheduled"} or job["scheduled"] > time.time():
                    continue
                event = threading.Event()
                running[job["id"]] = event
                job.update(status="Downloading", error="")
                save()
                threading.Thread(target=transfer, args=(job, event)).start()


def set_hold(hold):
    with lock:
        state["hold"] = hold
        for job in state["jobs"]:
            event = running.get(job["id"])
            if hold and event and job["status"] == "Downloading":
                job.update(status="Pausing", queue_hold=True)
                event.set()
        save()


def job_action(job_id):
    with lock:
        job = next((item for item in state["jobs"] if item["id"] == job_id), None)
        if not job:
            return
        event = running.get(job_id)
        if job["status"] == "Downloading" and event:
            job["status"] = "Pausing"
            event.set()
        elif job["status"] == "Queued":
            job["status"] = "Paused"
        elif job["status"] in {"Paused", "Failed", "Scheduled"}:
            job.update(status="Queued", scheduled=0)
        save()


def prioritize(job_id):
    with lock:
        job = next((item for item in state["jobs"] if item["id"] == job_id), None)
        if job and job["status"] != "Completed":
            job["priority"] = 0 if job.get("priority") else 1
            save()


def remove_job(job_id):
    with lock:
        job = next((item for item in state["jobs"] if item["id"] == job_id), None)
        if job is None:
            return
        if job_id in running:
            raise ValueError("Pause the transfer and wait for it to stop before removing it.")
        partial = Path(job["destination"]) / (".zdm-" + job["id"] + ".part")
        partial.unlink(missing_ok=True)
        state["jobs"].remove(job)
        save()


def snapshot():
    with lock:
        return {
            **state, "jobs": [job.copy() for job in state["jobs"]],
            "history": history[:], "connected": time.time() - last_ping < 95,
        }


class ExtensionHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value, code=200):
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply({"error": "Open the desktop app."}, 404)

    def do_POST(self):
        global last_ping
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            return self.reply({"error": "Invalid host"}, 403)
        if self.path not in {"/extension/send", "/extension/ping"}:
            return self.reply({"error": "Invalid endpoint"}, 404)
        token = ("Bearer " + state["key"]).encode()
        if not secrets.compare_digest(self.headers.get("Authorization", "").encode(), token):
            return self.reply({"error": "Check the connection key."}, 401)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 32768:
                raise ValueError("Invalid request size.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Invalid request body.")
            with lock:
                if self.path == "/extension/send":
                    enqueue(data, "Browser")
                last_ping = time.time()
        except (ValueError, OSError) as error:
            return self.reply({"error": str(error)}, 400)
        self.reply({"ok": True})


def start(port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), ExtensionHandler)
    save()
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def shutdown(server):
    closing.set()
    with lock:
        for event in running.values():
            event.set()
    server.shutdown()
    server.server_close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", "--no-browser", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8765, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.headless:
        server = start(options.port)
        try:
            closing.wait()
        except KeyboardInterrupt:
            shutdown(server)
        return
    import tkinter as tk
    from tkinter import messagebox
    from desktop import DownloadManager
    root = tk.Tk()
    try:
        server = start(options.port)
    except OSError as error:
        root.withdraw()
        messagebox.showerror("Z’s Download Manager", f"Could not start the download manager.\n\n{error}", parent=root)
        root.destroy()
        return
    try:
        window = DownloadManager(root)
        if options.smoke_test:
            window.show("Settings")
            window.show("Browser Extension")
            window.show("Scheduler")
            window.show("Downloads")
            window.customize()
            window.reset_layout()
            root.update()
            root.after(300, root.destroy)
        root.mainloop()
    finally:
        shutdown(server)


if __name__ == "__main__":
    # The desktop uses the same engine instance as the executable entry point.
    import sys
    sys.modules["app"] = sys.modules[__name__]
    main()
