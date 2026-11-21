# Z’s Download Manager

A local desktop download manager with a dark purple interface and a text-only sidebar. It runs a Python transfer service and opens its workspace in an Edge or Chrome app window when available.

## Start

1. Extract the whole ZIP.
2. Install Python 3.10 or newer. On Windows, double-click **Start Windows.cmd**. On macOS or Linux, run `python3 app.py`.
3. Keep the launcher running while downloads are active. If the window does not open automatically, visit http://127.0.0.1:8765.

The app starts with an empty queue. Paste a direct HTTP or HTTPS file link and choose a destination. Use Scheduler for future downloads and Settings for simultaneous transfers and bandwidth limits. The folder picker uses Tk when available. The destination can always be entered manually.

Pause and resume use a partial file when the server supports validated HTTP range requests. Otherwise the transfer restarts. Failed jobs can be retried from the queue. Files with duplicate names receive a numbered suffix. The queue and layout persist locally in `~/.z-download-manager`.

In **Customize layout**, drag side panels or use their move buttons. Hide a panel with **×**, restore it from **Hidden panels**, then select **Done** to save. **Reset layout** restores the defaults.

## Browser extension

1. Run the desktop app on the default port, then open **Browser Extension** in its sidebar.
2. In Chrome or Edge, open the browser’s extensions page, enable Developer mode, choose **Load unpacked**, and select the extracted `extension` folder.
3. Open the extension popup. Paste the connection key from the desktop app and select **Connect**.
4. Paste a direct download link into the popup or right-click a link and choose **Send to Z’s Download Manager**.

The extension queues links at the app’s default destination. Sites that require browser cookies or an existing browser session may require downloading through the browser itself.

## Update on Windows

Close the download manager and its launcher, then double-click **Update Windows.bat**. The updater fetches the latest code from this repository’s `main` branch. A Git checkout requires Git and uses a fast-forward update. An installation extracted from a ZIP uses Python to refresh the application and extension files in place.

The queue, connection key, settings, and downloaded files stay in their existing locations. If you installed the browser extension, select **Reload** for it on the browser’s extensions page after updating.
