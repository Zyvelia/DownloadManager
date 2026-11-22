"""Native desktop window for Z's Download Manager."""
from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import app

BG, SIDE, PANEL, INPUT = "#f4f3fa", "#19142b", "#ffffff", "#f7f6fb"
LINE, INK, MUTED = "#e5e0ef", "#241a37", "#655d75"
PURPLE, LILAC = "#6a38bc", "#7541c3"
SIDE_MUTED, SIDE_HOVER = "#bcafd4", "#312449"
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
TITLE = "Z’s Download Manager"
PANELS = {"speed": "Transfer speed", "browser": "Browser extension",
          "recent": "Recent downloads", "details": "Transfer details"}
ACTIONS = {"Downloading": "Pause", "Queued": "Pause", "Paused": "Resume",
           "Scheduled": "Start now", "Failed": "Retry"}


def rate(speed):
    return f"{speed / 1048576:.1f} MiB/s" if speed >= 1048576 else f"{speed / 1024:.0f} KiB/s"


def file_size(size):
    for divisor, unit in ((1073741824, "GiB"), (1048576, "MiB"), (1024, "KiB")):
        if size >= divisor:
            return f"{size / divisor:.1f} {unit}"
    return f"{size} B"


def date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class DownloadManager:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.geometry("1350x850")
        root.minsize(1060, 700)
        root.configure(bg=BG)
        self.view = "Downloads"
        self.filter = "All"
        self.draft = None
        self.selected = None
        self.destination = tk.StringVar(value=app.snapshot()["destination"])
        self.status = tk.StringVar()
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.update_live())
        self.sort_column = "added"
        self.menu = None
        self.sort_reverse = True
        self.nav = {}
        self.cards = {}
        self.configure_style()
        shell = tk.Frame(root, bg=BG)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=SIDE, width=205)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=SIDE)
        brand.pack(fill="x", padx=17, pady=(28, 32))
        logo = tk.Canvas(brand, width=34, height=34, bg=SIDE, highlightthickness=0)
        logo.pack(side="left", padx=(0, 9))
        logo.create_rectangle(1, 1, 33, 33, fill="#8554d7", outline="")
        logo.create_line(17, 8, 17, 21, fill="white", width=2)
        logo.create_line(11, 15, 17, 21, 23, 15, fill="white", width=2)
        logo.create_line(10, 25, 24, 25, fill="white", width=2)
        self.label(brand, "Z’s Download\nManager", bg=SIDE, fg="white", size=10,
                   bold=True, justify="left").pack(side="left")
        for section, links in (
            ("WORKSPACE", (("Downloads", "↓"), ("Scheduler", "◷"), ("History", "≡"))),
            ("PREFERENCES", (("Browser Extension", "↗"), ("Settings", "⚙"))),
        ):
            self.label(sidebar, section, bg=SIDE, fg=SIDE_MUTED, size=8, bold=True).pack(
                anchor="w", padx=22, pady=(0, 8))
            for name, symbol in links:
                button = self.button(sidebar, f"{symbol}    {name}", lambda name=name: self.show(name),
                                     anchor="w", sidebar=True)
                button.pack(fill="x", padx=12, pady=(0, 4))
                self.nav[name] = button
            tk.Frame(sidebar, height=22, bg=SIDE).pack()
        self.label(sidebar, "●  Local download engine", bg=SIDE, fg=SIDE_MUTED, size=9).pack(
            side="bottom", anchor="w", padx=19, pady=20)
        content = tk.Frame(shell, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        self.main = tk.Frame(content, bg=BG)
        self.main.pack(fill="both", expand=True, padx=25, pady=(22, 12))
        footer = tk.Frame(content, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        footer.pack(fill="x")
        self.label(footer, fg=MUTED, textvariable=self.status, size=9).pack(side="left", padx=16, pady=9)
        self.footer_speed = self.label(footer, fg=MUTED, size=9)
        self.footer_speed.pack(side="right", padx=16)
        root.bind("<Control-n>", lambda _: self.new_download(False))
        root.bind("<Control-f>", lambda _: self.focus_search())
        self.show(self.view)
        self.refresh()

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=INPUT, fieldbackground=INPUT, foreground=INK,
                        rowheight=43, borderwidth=0, font=(FONT, 10))
        style.configure("Treeview.Heading", background="#f0edf7", foreground=INK,
                        relief="flat", font=(FONT, 10, "bold"), padding=(8, 8))
        style.map("Treeview", background=[("selected", "#e6dbfb")], foreground=[("selected", INK)])
        style.map("Treeview.Heading", background=[("active", "#e5def2")])

    def label(self, parent, text="", bg=PANEL, fg=INK, size=10, bold=False, **options):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, size, "bold" if bold else "normal"), **options)

    def button(self, parent, text, command, primary=False, sidebar=False, **options):
        bg = SIDE if sidebar else PURPLE if primary else "#ede8f7"
        fg = SIDE_MUTED if sidebar else "white" if primary else INK
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=SIDE_HOVER if sidebar else "#d9caf2",
                         activeforeground="white" if sidebar else INK,
                         disabledforeground="#797185", relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=bg, highlightcolor=LILAC, cursor="hand2",
                         font=(FONT, 9, "bold"), padx=11, pady=7, **options)

    def entry(self, parent, variable=None, width=22):
        field = tk.Entry(parent, textvariable=variable, width=width, background=INPUT, foreground=INK,
                         insertbackground=INK, relief="flat", highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=LILAC, font=(FONT, 10))
        field.variable = variable
        return field

    def panel(self, parent):
        return tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightthickness=1, highlightbackground=LINE)

    def heading(self, parent, title):
        self.label(parent, title, size=11, bold=True).pack(anchor="w", pady=(0, 8))

    def show(self, view):
        self.view = view
        self.cards.clear()
        self.metrics = []
        self.search = None
        for child in self.main.winfo_children():
            child.destroy()
        for name, button in self.nav.items():
            button.configure(bg=SIDE_HOVER if name == view else SIDE,
                             fg="white" if name == view else SIDE_MUTED,
                             highlightbackground=SIDE_HOVER if name == view else SIDE)
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x", pady=(0, 18))
        title = tk.Frame(header, bg=BG)
        title.pack(side="left")
        self.label(title, view, bg=BG, size=27, bold=True).pack(anchor="w")
        subtitles = {
            "Downloads": "Manage your queue and monitor live transfers.",
            "Scheduler": "Queue transfers to start at a specific time.",
            "History": "Find and open files you’ve downloaded.",
            "Browser Extension": "Send download links directly from Chrome or Edge.",
            "Settings": "Choose where files go and how the queue runs.",
        }
        self.label(title, subtitles[view], bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 0))
        if view in {"Downloads", "Scheduler"}:
            scheduled = view == "Scheduler"
            self.button(header, "+  Schedule" if scheduled else "+  New download",
                        lambda: self.new_download(scheduled), True).pack(side="right", padx=(8, 0))
        if view == "Downloads":
            if self.draft is None:
                self.button(header, "Customize layout", self.customize).pack(side="right")
            else:
                self.button(header, "Done", self.save_layout, True).pack(side="right")
                self.button(header, "Reset", self.reset_layout).pack(side="right", padx=7)
            self.overview()
        if view == "Browser Extension":
            self.extension_page()
        elif view == "Settings":
            self.settings_page()
        else:
            self.queue_page()
        self.update_live()

    def overview(self):
        strip = tk.Frame(self.main, bg=BG)
        strip.pack(fill="x", pady=(0, 14))
        for column, (title, accent) in enumerate((
            ("Active transfers", "#6a38bc"),
            ("Download speed", "#2656ab"),
            ("Completed", "#187454"),
        )):
            strip.columnconfigure(column, weight=1, uniform="metrics")
            card = self.panel(strip)
            card.grid(row=0, column=column, sticky="ew", padx=(0, 10) if column < 2 else 0)
            self.label(card, title, size=10, bold=True).pack(anchor="w")
            value = self.label(card, fg=accent, size=22, bold=True)
            value.pack(anchor="w", pady=(3, 0))
            caption = self.label(card, fg=MUTED, size=9)
            caption.pack(anchor="w")
            self.metrics.append((value, caption))

    def focus_search(self):
        if self.search is None:
            self.show("Downloads")
        self.search.focus_set()

    def new_download(self, scheduled):
        dialog = tk.Toplevel(self.root, bg=BG)
        dialog.title("Schedule a download" if scheduled else "New download")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        card = self.panel(dialog)
        card.pack(fill="both", expand=True, padx=15, pady=15)
        self.heading(card, dialog.title())
        self.label(card, "Direct HTTP or HTTPS links · one per line", fg=MUTED).pack(anchor="w")
        links = tk.Text(card, width=63, height=5, bg=INPUT, fg=INK, relief="flat",
                        insertbackground=INK, highlightthickness=1, highlightbackground=LINE,
                        font=(FONT, 10), wrap="none", padx=6, pady=6)
        links.pack(fill="x", pady=(5, 12))
        self.label(card, "Save to", bold=True).pack(anchor="w")
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", pady=(5, 8))
        self.entry(row, self.destination, width=42).pack(side="left", fill="x", expand=True, ipady=7)

        def browse():
            folder = filedialog.askdirectory(initialdir=self.destination.get(), parent=dialog)
            if folder:
                self.destination.set(folder)

        self.button(row, "Browse…", browse).pack(side="right", padx=(7, 0))
        timing = None
        if scheduled:
            self.label(card, "Start at (YYYY-MM-DD HH:MM)", bold=True).pack(anchor="w")
            timing = self.entry(card)
            timing.pack(anchor="w", ipady=5, pady=(5, 8))
        error_label = self.label(card, fg="#a1284c", wraplength=475, justify="left")
        error_label.pack(anchor="w", pady=4)
        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill="x")

        def submit(*_):
            try:
                starts = datetime.strptime(timing.get(), "%Y-%m-%d %H:%M").timestamp() if timing else 0
                if timing and starts <= datetime.now().timestamp():
                    raise ValueError("Choose a future start time.")
                urls = list(dict.fromkeys(line.strip() for line in links.get("1.0", "end").splitlines() if line.strip()))
                if not urls:
                    raise ValueError("Paste at least one download link.")
                jobs = app.enqueue_many(urls, self.destination.get(), starts)
            except (OSError, ValueError) as error:
                error_label.configure(text=str(error))
                return
            dialog.destroy()
            self.query.set("")
            self.filter = "All"
            self.selected = jobs[0]["id"]
            if self.view != "Scheduler" or not scheduled:
                self.show("Downloads")
            else:
                self.update_live()

        self.button(controls, "Schedule" if scheduled else "Add to queue", submit, True).pack(side="right")
        self.button(controls, "Cancel", dialog.destroy).pack(side="right", padx=7)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.bind("<Control-Return>", submit)
        dialog.update_idletasks()
        dialog.geometry(f"+{self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2)}"
                        f"+{self.root.winfo_rooty() + 95}")
        links.focus_set()

    def queue_page(self):
        workspace = tk.Frame(self.main, bg=BG)
        workspace.pack(fill="both", expand=True)
        layout = self.draft if self.draft is not None else app.snapshot()["panels"]
        if self.view == "Downloads" and (layout or self.draft is not None):
            self.right = tk.Frame(workspace, bg=BG, width=265)
            self.right.pack(side="right", fill="y", padx=(12, 0))
            self.right.pack_propagate(False)
            for key in layout:
                if key in PANELS:
                    self.create_card(key)
            if self.draft is not None:
                self.hidden_cards()
        queue = self.panel(workspace)
        queue.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(queue, bg=PANEL)
        bar.pack(fill="x", pady=(0, 9))
        self.label(bar, {"History": "Completed downloads", "Scheduler": "Upcoming downloads"}.get(
            self.view, "Download queue"), size=13, bold=True).pack(side="left")
        self.search = self.entry(bar, self.query, width=20)
        self.search.pack(side="right", ipady=5)
        self.label(bar, "Search", fg=MUTED, size=9).pack(side="right", padx=6)
        toolbar = tk.Frame(queue, bg=PANEL)
        toolbar.pack(fill="x", pady=(0, 10))
        self.filter_buttons = {}
        if self.view == "Downloads":
            for name in ("All", "Active", "Completed", "Failed"):
                button = self.button(toolbar, name, lambda name=name: self.set_filter(name))
                button.pack(side="left", padx=(0, 4))
                self.filter_buttons[name] = button
            self.hold = self.button(toolbar, "Pause queue", lambda: app.set_hold(not app.snapshot()["hold"]))
            self.hold.pack(side="right")
        self.row_action = self.button(toolbar, "Actions", self.context_menu)
        self.row_action.pack(side="right", padx=(0, 5))
        columns = ("name", "progress", "speed", "eta", "status")
        self.tree = ttk.Treeview(queue, columns=columns, show="headings", selectmode="browse")
        for name, heading, width in zip(columns, ("File name", "Progress", "Speed",
                                                 "Starts" if self.view == "Scheduler" else "ETA", "Status"),
                                        (182, 112, 81, 122 if self.view == "Scheduler" else 58, 105)):
            self.tree.heading(name, text=heading, anchor="w", command=lambda name=name: self.sort_by(name))
            self.tree.column(name, width=width, minwidth=40, stretch=name == "name", anchor="w")
        self.tree.tag_configure("alternate", background="#faf9fd")
        self.tree.tag_configure("Completed", foreground="#126749")
        self.tree.tag_configure("Failed", foreground="#a1284c")
        self.tree.tag_configure("Downloading", foreground=PURPLE)
        self.tree.bind("<<TreeviewSelect>>", self.select_row)
        self.tree.bind("<Double-1>", lambda _: self.act_on_selection())
        self.tree.bind("<Return>", lambda _: self.act_on_selection())
        self.tree.bind("<Button-3>", self.context_menu)
        self.tree.bind("<Shift-F10>", self.context_menu)
        self.tree.bind("<Delete>", lambda _: self.remove_selected())
        scrollbar = ttk.Scrollbar(queue, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.empty_state = self.label(self.tree, fg=MUTED, bg=INPUT, size=10, padx=12, pady=9)

    def sort_by(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else column in {"speed", "progress"}
        self.sort_column = column
        self.update_live()

    def selected_job(self):
        if self.view in {"Settings", "Browser Extension"}:
            return None
        selection = self.tree.selection()
        return next((job for job in app.snapshot()["jobs"] if selection and job["id"] == selection[0]), None)

    def context_menu(self, event=None):
        if event and event.num == 3:
            identity = self.tree.identify_row(event.y)
            if not identity:
                return
            self.tree.selection_set(identity)
        job = self.selected_job()
        if not job:
            return
        if self.menu is not None:
            self.menu.destroy()
        menu = self.menu = tk.Menu(self.root, tearoff=False)
        action = ACTIONS.get(job["status"])
        if action:
            menu.add_command(label=action, command=self.act_on_selection)
        if job["status"] == "Completed":
            menu.add_command(label="Open file", command=lambda: self.open_location(job, True))
        else:
            menu.add_command(label="Set normal priority" if job.get("priority") else "Set high priority",
                             command=lambda: app.prioritize(job["id"]))
        menu.add_command(label="Open folder", command=lambda: self.open_location(job, False))
        menu.add_command(label="Copy download link", command=lambda: self.copy_text(job["url"]))
        menu.add_command(label="Transfer details…", command=lambda: self.show_details(job))
        menu.add_separator()
        menu.add_command(label="Remove from list…", command=self.remove_selected,
                         state="disabled" if job["status"] in {"Downloading", "Pausing"} else "normal")
        x, y = (event.x_root, event.y_root) if event and event.num == 3 else self.root.winfo_pointerxy()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def copy_text(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def show_details(self, job):
        parts = [f"Status: {job['status']}", f"Transferred: {file_size(job['received'])}",
                 f"Folder: {job['destination']}", f"Source: {job['source']}",
                 f"Priority: {'High' if job.get('priority') else 'Normal'}"]
        if job.get("completed"):
            parts.append(f"Completed: {date(job['completed'])}")
        if job["error"]:
            parts.append(f"Error: {job['error']}")
        messagebox.showinfo(job["name"], "\n".join(parts), parent=self.root)

    def open_location(self, job, open_file):
        target = Path(job["destination"])
        if open_file:
            target /= job["name"]
        try:
            if not target.exists():
                raise OSError(f"Could not find {target}")
            if sys.platform == "win32":
                os.startfile(target)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(target)])
        except OSError as error:
            messagebox.showerror(TITLE, str(error), parent=self.root)

    def remove_selected(self):
        job = self.selected_job()
        if not job:
            return
        if job["status"] in {"Downloading", "Pausing"}:
            messagebox.showinfo(TITLE, "Pause the transfer before removing it.", parent=self.root)
            return
        detail = "The downloaded file will stay on disk." if job["status"] == "Completed" else "Any partial data will be deleted."
        if messagebox.askyesno("Remove download", f"Remove {job['name']} from the list?\n\n{detail}", parent=self.root):
            try:
                app.remove_job(job["id"])
                self.selected = None
                self.update_live()
            except (OSError, ValueError) as error:
                messagebox.showerror(TITLE, str(error), parent=self.root)

    def select_row(self, _):
        selection = self.tree.selection()
        self.selected = selection[0] if selection else None
        self.row_action.configure(state="normal" if selection else "disabled")

    def act_on_selection(self):
        job = self.selected_job()
        if job is None:
            return
        if job["status"] == "Completed":
            self.open_location(job, True)
        elif job["status"] in ACTIONS:
            app.job_action(job["id"])
            self.update_live()

    def set_filter(self, name):
        self.filter = name
        self.selected = None
        self.update_live()

    def customize(self):
        self.draft = app.snapshot()["panels"][:]
        self.show("Downloads")

    def reset_layout(self):
        self.draft = app.DEFAULT_PANELS[:]
        self.show("Downloads")

    def save_layout(self):
        with app.lock:
            app.state["panels"] = self.draft[:]
            app.save()
        self.draft = None
        self.show("Downloads")

    def change_layout(self, key, operation):
        if operation == "hide":
            self.draft.remove(key)
        elif operation == "add":
            self.draft.append(key)
        elif self.draft.index(key) > 0:
            index = self.draft.index(key)
            self.draft[index - 1], self.draft[index] = key, self.draft[index - 1]
        self.show("Downloads")

    def drag_panel(self, key, event):
        target = next((name for name, (card, _) in self.cards.items()
                       if card.winfo_rooty() <= event.y_root < card.winfo_rooty() + card.winfo_height()), None)
        if target and target != key:
            index = self.draft.index(target)
            self.draft.remove(key)
            self.draft.insert(index, key)
            self.show("Downloads")

    def create_card(self, key):
        card = self.panel(self.right)
        card.pack(fill="x", pady=(0, 10))
        header = tk.Frame(card, bg=PANEL)
        header.pack(fill="x", pady=(0, 6))
        if self.draft is not None:
            grip = self.label(header, "⠿", fg=LILAC, cursor="fleur")
            grip.pack(side="left", padx=(0, 6))
            grip.bind("<ButtonRelease-1>", lambda event: self.drag_panel(key, event))
            self.button(header, "×", lambda: self.change_layout(key, "hide")).pack(side="right")
            self.button(header, "↑", lambda: self.change_layout(key, "up")).pack(side="right", padx=4)
        self.label(header, PANELS[key].upper(), bold=True).pack(side="left")
        value = self.label(card, justify="left", anchor="w", wraplength=229)
        value.pack(fill="x")
        self.cards[key] = (card, value)
        if key == "speed":
            self.graph = tk.Canvas(card, height=112, bg=INPUT, highlightthickness=0)
            self.graph.pack(fill="x", pady=(6, 0))
            axis = tk.Frame(card, bg=PANEL)
            axis.pack(fill="x", pady=(5, 0))
            self.label(axis, "60 sec ago", fg=MUTED, size=8).pack(side="left")
            self.label(axis, "Now", fg=MUTED, size=8).pack(side="right")
        if key == "browser":
            self.button(card, "Manage…", lambda: self.show("Browser Extension")).pack(anchor="e", pady=(7, 0))

    def hidden_cards(self):
        card = self.panel(self.right)
        card.pack(fill="x")
        self.heading(card, "Hidden panels")
        for key in PANELS:
            if key not in self.draft:
                line = tk.Frame(card, bg=PANEL)
                line.pack(fill="x", pady=2)
                self.label(line, PANELS[key]).pack(side="left")
                self.button(line, "+ Add", lambda key=key: self.change_layout(key, "add")).pack(side="right")

    def extension_page(self):
        card = self.panel(self.main)
        card.pack(fill="x")
        self.heading(card, "Connect Chrome or Edge")
        instructions = ("1. Open chrome://extensions or edge://extensions and enable Developer mode.\n"
                        "2. Choose Load unpacked and select the extracted extension folder.\n"
                        "3. Copy the connection key, paste it into the extension popup, and choose Connect.")
        self.label(card, instructions, justify="left", anchor="w").pack(fill="x", pady=(0, 12))
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x")
        self.key = app.snapshot()["key"]
        field = self.entry(row, tk.StringVar(value=self.key), width=36)
        field.configure(state="readonly", readonlybackground=INPUT)
        field.pack(side="left", ipady=6)
        self.button(row, "Copy key", self.copy_key).pack(side="left", padx=7)
        self.connection = self.label(card, fg=MUTED)
        self.connection.pack(anchor="w", pady=(10, 0))

    def copy_key(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.key)
        messagebox.showinfo(TITLE, "Connection key copied.", parent=self.root)

    def settings_page(self):
        card = self.panel(self.main)
        card.pack(fill="x")
        self.heading(card, "Transfer settings")
        state = app.snapshot()
        fields = [("Default destination", "destination"), ("Simultaneous downloads (1–8)", "parallel"),
                  ("Speed limit (KiB/s, 0 for off)", "limit")]
        entries = {}
        for label, key in fields:
            self.label(card, label).pack(anchor="w", pady=(4, 2))
            entry = self.entry(card, tk.StringVar(value=state[key]), width=44)
            entry.pack(anchor="w", ipady=5)
            entries[key] = entry
        self.button(card, "Save settings", lambda: self.save_settings(entries), True).pack(anchor="w", pady=(12, 0))

    def save_settings(self, entries):
        try:
            destination = Path(entries["destination"].get()).expanduser()
            parallel, limit = int(entries["parallel"].get()), int(entries["limit"].get())
            if not destination.is_absolute() or not 1 <= parallel <= 8 or limit < 0:
                raise ValueError("Enter an absolute folder, 1–8 simultaneous downloads, and a nonnegative speed limit.")
            with app.lock:
                app.state.update(destination=str(destination), parallel=parallel, limit=limit)
                app.save()
            self.destination.set(str(destination))
            messagebox.showinfo(TITLE, "Settings saved.", parent=self.root)
        except (OSError, ValueError) as error:
            messagebox.showerror(TITLE, str(error), parent=self.root)

    def update_live(self):
        state = app.snapshot()
        jobs = state["jobs"]
        active = [job for job in jobs if job["status"] in {"Downloading", "Pausing"}]
        completed = [job for job in jobs if job["status"] == "Completed"]
        speed = sum(job["speed"] for job in active)
        self.status.set(f"Queue: {len(jobs)} items · {len(active)} downloading · {len(completed)} completed")
        self.footer_speed.configure(text=f"Total speed: {rate(speed)}     |     Speed limit: "
                                         + (rate(state["limit"] * 1024) if state["limit"] else "Off"))
        if self.view == "Browser Extension":
            self.connection.configure(text="● Connected" if state["connected"] else "○ Waiting for browser extension")
            return
        if self.view == "Settings":
            return
        if self.metrics:
            values = (
                (str(len(active)), f"{state['parallel']} concurrent slots"),
                (rate(speed), "Bandwidth limit: " + (rate(state["limit"] * 1024) if state["limit"] else "Off")),
                (str(len(completed)), file_size(sum(job["size"] for job in completed)) + " downloaded"),
            )
            for (metric, caption), (value, detail) in zip(self.metrics, values):
                metric.configure(text=value)
                caption.configure(text=detail)
        candidates = {"All": jobs, "Active": active, "Completed": completed,
                      "Failed": [job for job in jobs if job["status"] == "Failed"]}
        shown = candidates[self.filter]
        if self.view == "Scheduler":
            shown = [job for job in jobs if job["status"] == "Scheduled"]
        elif self.view == "History":
            shown = completed
        for name, button in self.filter_buttons.items():
            button.configure(text=f"{name} ({len(candidates[name])})", bg=PURPLE if name == self.filter else "#ede8f7",
                             fg="white" if name == self.filter else INK)
        if self.view == "Downloads":
            self.hold.configure(text="Resume queue" if state["hold"] else "Pause queue")
        query = self.query.get().strip().casefold()
        columns = {
            "added": lambda job: job.get("added", 0),
            "name": lambda job: job["name"].casefold(),
            "progress": lambda job: job["received"] / job["size"] if job["size"] else 0,
            "speed": lambda job: job["speed"],
            "eta": lambda job: job["scheduled"] if self.view == "Scheduler"
                else (job["size"] - job["received"]) / job["speed"] if job["size"] and job["speed"] else float("inf"),
            "status": lambda job: job["status"],
        }
        shown = sorted((job for job in shown if query in job["name"].casefold() or query in job["url"].casefold()),
                       key=columns[self.sort_column], reverse=self.sort_reverse)
        self.update_table(shown)
        if shown:
            self.empty_state.place_forget()
        else:
            self.empty_state.configure(text="No downloads match your search." if query else
                                       "No downloads in this view.")
            self.empty_state.place(relx=.5, rely=.39, anchor="center")
        selection = self.tree.selection()
        selected_job = next((job for job in shown if selection and job["id"] == selection[0]), None)
        self.row_action.configure(state="normal" if selected_job else "disabled")
        self.update_cards(state, speed, completed, selected_job)

    def update_table(self, shown):
        existing = set(self.tree.get_children())
        for index, job in enumerate(shown):
            identity = job["id"]
            status = job["status"]
            progress = 100 if status == "Completed" else min(100, int(job["received"] * 100 / job["size"])) if job["size"] else None
            if self.view == "Scheduler":
                eta = date(job["scheduled"])
            elif job["speed"] and job["size"]:
                seconds = max(0, int((job["size"] - job["received"]) / job["speed"]))
                eta = f"{seconds // 60}m {seconds % 60:02d}s"
            else:
                eta = "—"
            label = ("↑  " if job.get("priority") else "") + job["name"]
            segments = int(progress / 20) if progress is not None else 0
            meter = f"{'▰' * segments}{'▱' * (5 - segments)} {progress}%" if progress is not None else "—"
            values = (label, meter,
                      rate(job["speed"]) if job["speed"] else "—", eta, status)
            tags = (status, "alternate") if index % 2 else (status,)
            if identity in existing:
                self.tree.item(identity, values=values, tags=tags)
                self.tree.move(identity, "", index)
                existing.remove(identity)
            else:
                self.tree.insert("", index, iid=identity, values=values, tags=tags)
        if existing:
            self.tree.delete(*existing)
        if self.selected and self.tree.exists(self.selected) and not self.tree.selection():
            self.tree.selection_set(self.selected)

    def update_cards(self, state, speed, completed, job):
        for key, (_, label) in self.cards.items():
            if key == "speed":
                label.configure(text=rate(speed), fg=LILAC, font=(FONT, 18, "bold"))
                self.draw_speed(state["history"])
            elif key == "browser":
                connected = "● Connected" if state["connected"] else "○ Disconnected"
                last = state["last"]
                label.configure(text=f"{connected}\n\nLast link: {last['name']}\n{date(last['time'])}" if last else connected,
                                fg="#126749" if state["connected"] else MUTED)
            elif key == "recent":
                label.configure(text="\n".join(item["name"] for item in completed[-5:][::-1]) or "No completed downloads.")
            elif key == "details":
                label.configure(text=(f"{job['name']}\n{job['destination']}\n{job['received']:,} bytes · {job['status']}"
                                      + (f"\n{job['error']}" if job["error"] else "")) if job else "Select a download to see its details.")

    def draw_speed(self, samples):
        graph = self.graph
        graph.delete("all")
        width, height = max(2, graph.winfo_width()), max(2, graph.winfo_height())
        samples = samples[-120:]
        for step in range(1, 5):
            y = step * (height - 2) / 5
            graph.create_line(0, y, width, y, fill=LINE)
        if len(samples) < 2:
            return
        top = max(1024, *samples) * 1.15
        points = []
        for index, speed in enumerate(samples):
            points.extend((width - 1 - (len(samples) - 1 - index) * width / 119,
                           height - 2 - speed * (height - 4) / top))
        graph.create_polygon(points[0], height - 2, *points, width - 1, height - 2,
                             fill="#eee5fb", outline="")
        graph.create_line(*points, fill=LILAC, width=2)

    def refresh(self):
        self.update_live()
        self.root.after(500, self.refresh)
