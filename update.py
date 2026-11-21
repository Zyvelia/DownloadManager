"""Update a Git checkout or a ZIP installation from the official repository."""
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parent
REPOSITORY = "https://github.com/Zyvelia/DownloadManager.git"
ARCHIVE = "https://codeload.github.com/Zyvelia/DownloadManager/zip/refs/heads/main"
MAX_ARCHIVE = 16 * 1024 * 1024
CODE_FILES = (
    "app.py", "desktop.py", "README.md",
    "Start Windows.cmd", "Update Windows.bat", "update.py", ".gitignore",
    "packaging/launcher.go", "packaging/build_windows.py",
    "extension/manifest.json", "extension/worker.js", "extension/popup.html",
    "extension/popup.css", "extension/popup.js", "extension/README.md",
)


def git(*arguments, capture=False):
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def update_checkout():
    if git("status", "--porcelain", "--untracked-files=no", capture=True).strip():
        raise RuntimeError("Commit or stash local code changes before updating.")
    if git("branch", "--show-current", capture=True).strip() != "main":
        raise RuntimeError("Switch to the main branch before updating.")
    git("fetch", REPOSITORY, "refs/heads/main")
    git("merge", "--ff-only", "FETCH_HEAD")


def archive_files():
    with urlopen(ARCHIVE, timeout=30) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError("The downloaded archive is too large.")
    with ZipFile(io.BytesIO(data)) as archive:
        root = "DownloadManager-main/"
        members = {}
        for info in archive.infolist():
            name = info.filename.removeprefix(root)
            if info.filename.startswith(root) and name in CODE_FILES:
                if name in members or info.file_size > MAX_ARCHIVE:
                    raise ValueError(f"Invalid archive entry: {name}")
                members[name] = info
        if members.keys() != set(CODE_FILES):
            raise ValueError("The archive is missing required application files.")
        return {name: archive.read(info) for name, info in members.items()}


def replace_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        staging = Path(file.name)
        try:
            file.write(content)
            file.close()
            os.replace(staging, path)
        finally:
            staging.unlink(missing_ok=True)


def update_archive():
    updates = archive_files()
    originals = {}
    for name in updates:
        target = ROOT.joinpath(*PurePosixPath(name).parts)
        if target.resolve() != target or (target.exists() and not target.is_file()):
            raise ValueError(f"Expected an ordinary application file: {name}")
        originals[target] = target.read_bytes() if target.exists() else None

    if all(originals[ROOT / name] == content for name, content in updates.items()):
        return "Already up to date."

    changed = []
    try:
        for name, content in updates.items():
            target = ROOT / name
            if originals[target] != content:
                replace_file(target, content)
                changed.append(target)
    except OSError:
        try:
            for target in reversed(changed):
                original = originals[target]
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    replace_file(target, original)
        except OSError as rollback_error:
            raise RuntimeError(f"Could not restore {target.name}: {rollback_error}") from rollback_error
        raise
    return "Update installed."


def main():
    try:
        if (ROOT / ".git").exists():
            update_checkout()
        else:
            print(update_archive())
        print("Start the app again and reload the unpacked extension if you use it.")
        return 0
    except (OSError, ValueError, RuntimeError, BadZipFile, subprocess.CalledProcessError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
