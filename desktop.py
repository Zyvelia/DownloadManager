"""Native desktop window for Z's Download Manager."""
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import app

BG, SIDE, PANEL, INPUT = "#11101c", "#151122", "#20182e", "#171523"
LINE, INK, MUTED = "#554266", "#f7f0ff", "#c1b3d0"
PURPLE, LILAC = "#7936ae", "#c780fa"
TITLE = "Z’s Download Manager"
PANELS = {"speed": "Transfer speed", "browser": "Browser extension",
          "recent": "Recent downloads", "details": "Transfer details"}
ACTIONS = {"Downloading": "Pause", "Queued": "Pause", "Paused": "Resume",
           "Scheduled": "Start now", "Failed": "Retry"}


def rate(speed):
    return f"{speed / 1048576:.1f} MiB/s" if speed >= 1048576 else f"{speed / 1024:.0f} KiB/s"


def date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class DownloadManager:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.geometry("1320x800")
        root.minsize(970, 620)
        root.configure(bg=BG)
        self.view = "Downloads"
        self.filter = "All"
        self.draft = None
        self.selected = None
        self.destination = tk.StringVar(value=app.snapshot()["destination"])
        self.status = tk.StringVar()
        self.nav = {}
        self.cards = {}
        self.configure_style()
        shell = tk.Frame(root, bg=BG)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=SIDE, width=204, highlightthickness=1, highlightbackground=LINE)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.label(sidebar, TITLE, bg=SIDE, size=12, bold=True).pack(anchor="w", padx=13, pady=(24, 4))
        self.label(sidebar, "File downloads & queues", bg=SIDE, fg=MUTED).pack(anchor="w", padx=13, pady=(0, 24))
        for name, symbol in (("Downloads", "↓"), ("Scheduler", "▦"), ("History", "◷"),
                             ("Browser Extension", "↗"), ("Settings", "⚙")):
            button = self.button(sidebar, f"{symbol}   {name}", lambda name=name: self.show(name), anchor="w")
            button.pack(fill="x", padx=10, pady=3)
            self.nav[name] = button
        self.main = tk.Frame(shell, bg=BG)
        self.main.pack(side="left", fill="both", expand=True, padx=15, pady=14)
        footer = tk.Frame(root, bg=SIDE, highlightthickness=1, highlightbackground=LINE)
        footer.pack(fill="x")
        self.label(footer, bg=SIDE, fg=MUTED, textvariable=self.status).pack(side="left", padx=12, pady=8)
        self.footer_speed = self.label(footer, bg=SIDE, fg=MUTED)
        self.footer_speed.pack(side="right", padx=12)
        self.show(self.view)
        self.refresh()

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=INPUT, fieldbackground=INPUT, foreground=INK,
                        rowheight=31, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#362749", foreground=INK,
                        relief="flat", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Treeview", background=[("selected", "#5a3279")], foreground=[("selected", "white")])
        style.map("Treeview.Heading", background=[("active", "#48325c")])

    def label(self, parent, text="", bg=PANEL, fg=INK, size=10, bold=False, **options):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=("Segoe UI", size, "bold" if bold else "normal"), **options)

    def button(self, parent, text, command, primary=False, **options):
        return tk.Button(parent, text=text, command=command, bg=PURPLE if primary else "#2e263d",
                         fg=INK, activebackground="#954cc3", activeforeground=INK,
                         disabledforeground="#9d90aa", relief="flat", cursor="hand2",
                         font=("Segoe UI", 10), padx=9, pady=5, **options)

    def entry(self, parent, variable=None, width=22):
        field = tk.Entry(parent, textvariable=variable, width=width, background=INPUT, foreground=INK,
                         insertbackground=INK, relief="flat", highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=LILAC, font=("Segoe UI", 10))
        field.variable = variable
        return field

    def panel(self, parent):
        return tk.Frame(parent, bg=PANEL, padx=11, pady=9, highlightthickness=1, highlightbackground=LINE)

    def heading(self, parent, title):
        self.label(parent, title.upper(), size=11, bold=True).pack(anchor="w", pady=(0, 8))

    def show(self, view):
        self.view = view
        self.cards.clear()
        for child in self.main.winfo_children():
            child.destroy()
        for name, button in self.nav.items():
            button.configure(bg=PURPLE if name == view else "#272035")
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x", pady=(0, 11))
        self.label(header, TITLE if view == "Downloads" else view, bg=BG, size=20, bold=True).pack(side="left")
        if view == "Downloads":
            if self.draft is None:
                self.button(header, "Customize layout", self.customize).pack(side="right")
            else:
                self.button(header, "✓  Done", self.save_layout, True).pack(side="right")
                self.button(header, "Reset layout", self.reset_layout).pack(side="right", padx=7)
        if view == "Browser Extension":
            self.extension_page()
        elif view == "Settings":
            self.settings_page()
        else:
            if view != "History":
                self.add_form()
            self.queue_page()
        self.update_live()

    def add_form(self):
        card = self.panel(self.main)
        card.pack(fill="x", pady=(0, 12))
        scheduled = self.view == "Scheduler"
        self.heading(card, "Schedule a download" if scheduled else "Add download")
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x")
        self.label(row, "Direct URL").pack(side="left", padx=(0, 7))
        link = self.entry(row)
        link.pack(side="left", fill="x", expand=True, ipady=6)
        self.label(row, "Destination").pack(side="left", padx=(12, 7))
        self.entry(row, self.destination, width=22).pack(side="left", ipady=6)
        self.button(row, "Browse…", self.choose_folder).pack(side="left", padx=6)
        when = None
        if scheduled:
            timing = tk.Frame(card, bg=PANEL)
            timing.pack(fill="x", pady=(8, 0))
            self.label(timing, "Start at (YYYY-MM-DD HH:MM)").pack(side="left", padx=(0, 8))
            when = self.entry(timing)
            when.pack(side="left", ipady=5)
        submit = lambda *_: self.add_download(link, when)
        self.button(row, "Schedule" if scheduled else "Add to queue", submit, True).pack(side="left")
        link.bind("<Return>", submit)

    def choose_folder(self):
        destination = filedialog.askdirectory(initialdir=self.destination.get(), parent=self.root)
        if destination:
            self.destination.set(destination)

    def add_download(self, link, when):
        try:
            scheduled = datetime.strptime(when.get(), "%Y-%m-%d %H:%M").timestamp() if when else 0
            if when and scheduled <= datetime.now().timestamp():
                raise ValueError("Choose a future start time.")
            with app.lock:
                job = app.enqueue({"url": link.get(), "destination": self.destination.get(),
                                   "scheduled": scheduled}, "Desktop")
            link.delete(0, "end")
            if when:
                when.delete(0, "end")
            self.filter = "All"
            self.selected = job["id"]
            self.update_live()
        except (OSError, ValueError) as error:
            messagebox.showerror(TITLE, str(error), parent=self.root)

    def queue_page(self):
        workspace = tk.Frame(self.main, bg=BG)
        workspace.pack(fill="both", expand=True)
        layout = self.draft if self.draft is not None else app.snapshot()["panels"]
        if self.view == "Downloads" and (layout or self.draft is not None):
            self.right = tk.Frame(workspace, bg=BG, width=315)
            self.right.pack(side="right", fill="y", padx=(12, 0))
            self.right.pack_propagate(False)
            for key in layout:
                if key in PANELS:
                    self.create_card(key)
            if self.draft is not None:
                self.hidden_cards()
        queue = self.panel(workspace)
        queue.pack(side="left", fill="both", expand=True)
        self.heading(queue, {"History": "Completed downloads", "Scheduler": "Scheduled downloads"}.get(self.view, "Download queue"))
        toolbar = tk.Frame(queue, bg=PANEL)
        toolbar.pack(fill="x", pady=(0, 8))
        self.filter_buttons = {}
        if self.view == "Downloads":
            for name in ("All", "Active", "Completed"):
                button = self.button(toolbar, name, lambda name=name: self.set_filter(name))
                button.pack(side="left", padx=(0, 5))
                self.filter_buttons[name] = button
            self.hold = self.button(toolbar, "Pause all", lambda: app.set_hold(not app.snapshot()["hold"]))
            self.hold.pack(side="right")
        self.row_action = self.button(toolbar, "Pause / resume", self.act_on_selection)
        self.row_action.pack(side="right", padx=5)
        columns = ("name", "progress", "speed", "eta", "status")
        self.tree = ttk.Treeview(queue, columns=columns, show="headings", selectmode="browse")
        for name, heading, width in zip(columns, ("File", "Progress", "Speed", "Starts" if self.view == "Scheduler" else "ETA", "Status"),
                                        (204, 106, 80, 112 if self.view == "Scheduler" else 55, 104)):
            self.tree.heading(name, text=heading)
            self.tree.column(name, width=width, minwidth=42, stretch=name == "name", anchor="w")
        self.tree.tag_configure("alternate", background="#211a30")
        self.tree.tag_configure("Completed", foreground="#bde9a5")
        self.tree.tag_configure("Failed", foreground="#ffc0cf")
        self.tree.tag_configure("Downloading", foreground="#efd1ff")
        self.tree.bind("<<TreeviewSelect>>", self.select_row)
        self.tree.bind("<Double-1>", lambda _: self.act_on_selection())
        self.tree.bind("<Return>", lambda _: self.act_on_selection())
        scrollbar = ttk.Scrollbar(queue, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    def select_row(self, _):
        selection = self.tree.selection()
        if selection:
            self.selected = selection[0]

    def act_on_selection(self):
        if self.selected:
            app.job_action(self.selected)
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
        value = self.label(card, justify="left", anchor="w", wraplength=275)
        value.pack(fill="x")
        self.cards[key] = (card, value)
        if key == "speed":
            self.graph = tk.Canvas(card, height=82, bg=INPUT, highlightthickness=0)
            self.graph.pack(fill="x", pady=(6, 0))
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
        candidates = {"All": jobs, "Active": active, "Completed": completed}
        shown = candidates[self.filter]
        if self.view == "Scheduler":
            shown = [job for job in jobs if job["status"] == "Scheduled"]
        elif self.view == "History":
            shown = completed
        for name, button in self.filter_buttons.items():
            button.configure(text=f"{name} ({len(candidates[name])})", bg=PURPLE if name == self.filter else "#2e263d")
        if self.view == "Downloads":
            self.hold.configure(text="Resume queue" if state["hold"] else "Pause all",
                                state="disabled" if any(job["status"] == "Pausing" for job in active) else "normal")
        self.update_table(shown)
        selection = self.tree.selection()
        selected_job = next((job for job in shown if selection and job["id"] == selection[0]), None)
        action = ACTIONS.get(selected_job["status"]) if selected_job else None
        self.row_action.configure(text=action or "Pause / resume", state="normal" if action else "disabled")
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
            label = job["name"] + ("  ·  Sent from browser" if job["source"] == "Browser" else "")
            segments = int(progress / 20) if progress is not None else 0
            meter = f"{'▰' * segments}{'▱' * (5 - segments)} {progress}%" if progress is not None else "—"
            values = (label, meter,
                      rate(job["speed"]) if job["speed"] else "—", eta, status)
            tags = (status, "alternate") if index % 2 else (status,)
            if identity in existing:
                self.tree.item(identity, values=values, tags=tags)
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
                label.configure(text=rate(speed), fg=LILAC, font=("Segoe UI", 18, "bold"))
                self.draw_speed(state["history"])
            elif key == "browser":
                connected = "● Connected" if state["connected"] else "○ Disconnected"
                last = state["last"]
                label.configure(text=f"{connected}\n\nLast link: {last['name']}\n{date(last['time'])}" if last else connected,
                                fg="#bde9a5" if state["connected"] else MUTED)
            elif key == "recent":
                label.configure(text="\n".join(item["name"] for item in completed[-5:][::-1]) or "No completed downloads.")
            elif key == "details":
                label.configure(text=(f"{job['name']}\n{job['destination']}\n{job['received']:,} bytes · {job['status']}"
                                      + (f"\n{job['error']}" if job["error"] else "")) if job else "Select a download to see its details.")

    def draw_speed(self, samples):
        graph = self.graph
        graph.delete("all")
        width, height = max(2, graph.winfo_width()), max(2, graph.winfo_height())
        for step in range(1, 5):
            y = step * (height - 2) / 5
            graph.create_line(0, y, width, y, fill="#392b49")
        if len(samples) < 2:
            return
        top = max(1024, *samples) * 1.15
        points = []
        for index, speed in enumerate(samples):
            points.extend((width - 1 - (len(samples) - 1 - index) * width / 599,
                           height - 2 - speed * (height - 4) / top))
        graph.create_line(*points, fill=LILAC, width=2)

    def refresh(self):
        self.update_live()
        self.root.after(500, self.refresh)
