# Z’s Download Manager

A native Windows download manager for direct HTTP and HTTPS files.

- Paste a direct link into **Add a download** and press Enter. Use **Batch add** for multiple links or **Scheduler** for a local start time.
- Search and sort the queue, filter by status, and prioritize transfers through the **Actions** menu or by right-clicking a row.
- Pause a transfer, retry a failure, or pause the entire queue. Resume reuses partial files on servers that support validated HTTP range requests. Other servers restart the transfer.
- Monitor throughput, progress, and estimated time remaining. Use **Customize layout** to rearrange, hide, and restore dashboard panels.
- Find completed files in **History**, open the file or destination folder, and remove entries while keeping completed files.
- Set a bandwidth limit and run up to eight downloads at once. **Ctrl+N** opens batch entry and **Ctrl+F** focuses search.

## Run on Windows

Use the **Download for Windows x64** link in the [latest release](https://github.com/Zyvelia/DownloadManager/releases/latest) and double-click it. The Windows x64 executable includes its own runtime. The app opens directly in a desktop window and needs no browser or Python installation.

Keep the app open while downloading or waiting for a scheduled transfer. Active transfers save partial data when you close the app.

## Browser extension

1. Download and extract **Zs-Download-Manager-Extension.zip** from the latest release.
2. Open `chrome://extensions` or `edge://extensions`, enable **Developer mode**, and select **Load unpacked**. Choose the extracted folder containing `manifest.json`.
3. Open **Browser Extension** in the desktop app and copy its connection key. Paste it into the extension popup and choose **Connect**.
4. Paste a link into the popup or right-click a download link and choose **Send to Z’s Download Manager**.

The extension uses an authenticated connection to the app on the same computer. Links requiring browser cookies may need to be downloaded in the browser itself.

## Update

Download **Update Windows.bat** from the release and put it next to **Zs-Download-Manager.exe**. Close the app, then run the updater. It checks the GitHub release checksum before replacing the executable. The queue, settings, connection key, and downloads stay in place. For a source checkout or extracted source archive, the batch file runs the source updater when the executable is absent.

## Run and build from source

Run `python app.py` with Python 3.10 or newer and Tk installed. The native interface works without starting a browser. The release build script needs Python 3.11 or newer and Go 1.24 or newer. Run `python packaging/build_windows.py` to build the Windows x64 executable in `dist/`.

App state is stored in `~/.z-download-manager`.
