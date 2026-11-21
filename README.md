# Z’s Download Manager

A native Windows desktop download manager with a dark purple queue, scheduler, history, live speed graph, and customizable panels.

## Run on Windows

Download **Zs-Download-Manager.exe** from the [latest release](https://github.com/Zyvelia/DownloadManager/releases/latest) and double-click it. The Windows x64 executable includes its own runtime. The app opens directly in a desktop window and needs no browser or Python installation.

Paste a direct HTTP or HTTPS file link and choose a destination. Use **Scheduler** for future downloads, **Settings** for simultaneous transfers and bandwidth limits, and **Customize layout** to rearrange, hide, or restore panels. Close the window to stop active transfers. Pause and resume reuse a partial file when the server supports validated HTTP range requests.

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
