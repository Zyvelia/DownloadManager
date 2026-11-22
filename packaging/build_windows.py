"""Build a portable Windows x64 executable on a machine with Python and Go."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT = Path(__file__).resolve().parents[1]
RUNTIME_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/20261110/"
               "cpython-3.12.16%2B20261110-x86_64-pc-windows-msvc-install_only.tar.gz")
RUNTIME_SHA256 = "e23fe5b16926de1d81661b1a97352e89fb167549c55a6825796ccd0f32ec7f1b"
ROOT_FILES = {"LICENSE.txt", "pythonw.exe", "python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
SKIP_LIB = {"test", "idlelib", "site-packages", "ensurepip", "venv", "turtledemo", "__pycache__"}


def include(relative):
    parts = PurePosixPath(relative).parts
    if len(parts) == 1:
        return relative in ROOT_FILES
    if parts[0] == "DLLs":
        return relative.endswith((".dll", ".pyd")) and not parts[-1].startswith("_test")
    if parts[0] == "tcl":
        return parts[1] in {"tcl8.6", "tk8.6", "tcl8"}
    return parts[0] == "Lib" and not any(part in SKIP_LIB for part in parts)


def build(go, runtime, output):
    with tempfile.TemporaryDirectory(prefix="zdm-build-") as directory:
        build_dir = Path(directory)
        if runtime is None:
            runtime = build_dir / "runtime.tar.gz"
            with urlopen(RUNTIME_URL, timeout=60) as source, runtime.open("wb") as target:
                shutil.copyfileobj(source, target)
        with runtime.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != RUNTIME_SHA256:
                raise ValueError("Bundled Windows runtime did not match the expected SHA-256.")
        with tarfile.open(runtime, "r:gz") as source, ZipFile(build_dir / "payload.zip", "w", ZIP_DEFLATED) as bundle:
            for member in source:
                name = member.name.removeprefix("python/")
                if member.isfile() and member.name.startswith("python/") and include(name):
                    bundle.writestr(name, source.extractfile(member).read())
            for name in ("app.py", "desktop.py", "assets/app.png"):
                bundle.write(PROJECT / name, name)
            names = set(bundle.namelist())
            required = ROOT_FILES | {"DLLs/_tkinter.pyd", "DLLs/tcl86t.dll", "DLLs/tk86t.dll",
                                     "tcl/tcl8.6/init.tcl", "tcl/tk8.6/tk.tcl", "Lib/tkinter/__init__.py"}
            if required - names:
                raise ValueError("Bundled runtime is missing desktop dependencies.")
        shutil.copyfile(PROJECT / "packaging" / "launcher.go", build_dir / "launcher.go")
        (build_dir / "go.mod").write_text("module zdm-launcher\n\ngo 1.24\n", encoding="ascii")
        subprocess.run([go, "run", "github.com/akavel/rsrc@v0.10.2", "-arch", "amd64",
                        "-ico", str(PROJECT / "assets" / "app.ico"), "-o", "icon_windows_amd64.syso"],
                       cwd=build_dir, check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([go, "build", "-buildvcs=false", "-trimpath", "-ldflags", "-s -w -H windowsgui",
                        "-o", str(output), "."], cwd=build_dir, check=True,
                       env={**os.environ, "GOOS": "windows", "GOARCH": "amd64", "CGO_ENABLED": "0"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "dist" / "Zs-Download-Manager.exe")
    args = parser.parse_args()
    build(args.go, args.runtime, args.output.resolve())
