"""Native desktop window for Z's Download Manager."""
from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import app

BG, SIDE, PANEL, INPUT = "#0d131e", "#101827", "#151f30", "#1c293d"
LINE, INK, MUTED = "#2b3b52", "#eef4ff", "#a6b6cd"
ACCENT, ACTIVE, SELECTION = "#8bb7ff", "#223755", "#233b60"
HERO, HERO_TEXT, LIME = "#152b49", "#c3d5ed", "#d5fa83"
GOOD, BAD = "#76dfae", "#ff9eaf"
SCROLL_THUMB = "#4d637e"
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


def use_dark_title_bar(window):
    if sys.platform != "win32":
        return

    def on_map(event):
        if event.widget is not window:
            return
        from ctypes import WinDLL, byref, c_int, sizeof
        from ctypes.wintypes import DWORD, HWND, LPVOID, UINT

        get_ancestor = WinDLL("user32").GetAncestor
        get_ancestor.argtypes = (HWND, UINT)
        get_ancestor.restype = HWND
        hwnd = get_ancestor(window.winfo_id(), 2)
        if not hwnd:
            return
        set_attribute = WinDLL("dwmapi").DwmSetWindowAttribute
        set_attribute.argtypes = (HWND, DWORD, LPVOID, DWORD)
        set_attribute.restype = c_int
        enabled = c_int(1)
        if set_attribute(hwnd, 20, byref(enabled), sizeof(enabled)):
            set_attribute(hwnd, 19, byref(enabled), sizeof(enabled))

    window.bind("<Map>", on_map, add="+")


class DownloadManager:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.geometry("1350x850")
        root.minsize(1060, 700)
        root.configure(bg=BG)
        use_dark_title_bar(root)
        self.view = "Downloads"
        self.filter = "All"
        self.draft = None
        self.selected = None
        self.destination = tk.StringVar(value=app.snapshot()["destination"])
        self.status = tk.StringVar()
        self.quick_url = tk.StringVar()
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
        sidebar = tk.Frame(shell, bg=SIDE, width=188)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(shell, bg=LINE, width=1).pack(side="left", fill="y")
        brand = tk.Frame(sidebar, bg=SIDE)
        brand.pack(fill="x", padx=14, pady=(28, 35))
        logo = tk.Canvas(brand, width=37, height=37, bg=SIDE, highlightthickness=0)
        logo.pack(side="left", padx=(0, 10))
        logo.create_oval(0, 0, 37, 37, fill=HERO, outline="")
        self.draw_arrow(logo, 18, 17, LIME, 11)
        wordmark = tk.Frame(brand, bg=SIDE)
        wordmark.pack(side="left")
        self.label(wordmark, "Z’s Download", size=10, bold=True).pack(anchor="w")
        self.label(wordmark, "Manager", fg=MUTED, size=9).pack(anchor="w")
        for section, links in (
            ("WORKSPACE", (("Downloads", "download"), ("Scheduler", "clock"), ("History", "history"))),
            ("PREFERENCES", (("Browser Extension", "browser"), ("Settings", "settings"))),
        ):
            self.label(sidebar, section, fg=MUTED, size=8, bold=True).pack(anchor="w", padx=21, pady=(0, 8))
            for name, symbol in links:
                row = tk.Frame(sidebar, bg=SIDE)
                row.pack(fill="x", padx=11, pady=(0, 4))
                icon = tk.Canvas(row, width=16, height=18, bg=SIDE, highlightthickness=0, cursor="hand2")
                icon.pack(side="left", padx=(10, 1))
                self.draw_nav_icon(icon, symbol)
                icon.bind("<Button-1>", lambda _, name=name: self.show(name))
                button = self.button(row, name, lambda name=name: self.show(name), anchor="w", sidebar=True)
                button.pack(side="left", fill="x", expand=True)
                self.nav[name] = row, icon, button
            tk.Frame(sidebar, height=21, bg=SIDE).pack()
        local = tk.Frame(sidebar, bg=INPUT, padx=10, pady=8)
        local.pack(side="bottom", fill="x", padx=13, pady=17)
        dot = tk.Canvas(local, width=11, height=11, bg=INPUT, highlightthickness=0)
        dot.pack(side="left", padx=(0, 5))
        dot.create_oval(2, 2, 9, 9, fill=GOOD, outline="")
        self.label(local, "Local engine", bg=INPUT, fg=MUTED, size=9, bold=True).pack(side="left")
        content = tk.Frame(shell, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        footer = tk.Frame(content, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        footer.pack(side="bottom", fill="x")
        self.label(footer, fg=MUTED, textvariable=self.status, size=9).pack(side="left", padx=16, pady=7)
        self.footer_speed = self.label(footer, fg=MUTED, size=9)
        self.footer_speed.pack(side="right", padx=16)
        self.main = tk.Frame(content, bg=BG)
        self.main.pack(fill="both", expand=True, padx=26, pady=(21, 15))
        root.bind("<Control-n>", lambda _: self.new_download(False))
        root.bind("<Control-f>", lambda _: self.focus_search())
        self.show(self.view)
        self.refresh()

    @staticmethod
    def draw_arrow(canvas, x, y, color, size):
        canvas.create_line(x, y - size * .62, x, y + size * .37, width=2, fill=color, capstyle="round")
        canvas.create_line(x - size * .43, y, x, y + size * .4, x + size * .43, y,
                           width=2, fill=color, joinstyle="round", capstyle="round")
        canvas.create_line(x - size * .59, y + size * .78, x + size * .59, y + size * .78,
                           width=2, fill=color, capstyle="round")

    def draw_nav_icon(self, canvas, icon):
        if icon == "download":
            self.draw_arrow(canvas, 8, 8, MUTED, 9)
        elif icon == "clock":
            canvas.create_oval(2, 3, 14, 15, outline=MUTED, width=1.5)
            canvas.create_line(8, 5, 8, 9, 11, 10, fill=MUTED, width=1.5)
        elif icon == "history":
            canvas.create_arc(2, 3, 14, 15, start=155, extent=300, outline=MUTED, width=1.5, style="arc")
            canvas.create_line(2, 4, 2, 8, 6, 8, fill=MUTED, width=1.5)
            canvas.create_line(8, 6, 8, 10, 11, 10, fill=MUTED, width=1.5)
        elif icon == "browser":
            canvas.create_rectangle(1, 4, 15, 14, outline=MUTED, width=1.5)
            canvas.create_line(2, 7, 14, 7, fill=MUTED, width=1.5)
        else:
            for y, x in ((5, 5), (9, 11), (13, 7)):
                canvas.create_line(1, y, 15, y, fill=MUTED, width=1.5)
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, outline=MUTED, fill=SIDE)

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                        rowheight=45, borderwidth=0, highlightthickness=0, relief="flat", font=(FONT, 10))
        style.configure("Treeview.Heading", background=INPUT, foreground=MUTED, borderwidth=0,
                        relief="flat", font=(FONT, 9, "bold"), padding=(8, 10))
        style.map("Treeview", background=[("selected", SELECTION)], foreground=[("selected", INK)])
        style.map("Treeview.Heading", background=[("active", ACTIVE)])
        style.layout("Queue.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
            ]})
        ])
        style.configure("Queue.Vertical.TScrollbar", background=SCROLL_THUMB, troughcolor=INPUT,
                        lightcolor=SCROLL_THUMB, darkcolor=SCROLL_THUMB, bordercolor=INPUT, gripcount=0,
                        arrowsize=9, borderwidth=0)
        style.map("Queue.Vertical.TScrollbar", background=[("active", "#6784a5")])

    def label(self, parent, text="", bg=PANEL, fg=INK, size=10, bold=False, **options):
        return tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, size, "bold" if bold else "normal"), **options)

    def button(self, parent, text, command, primary=False, sidebar=False, lime=False, **options):
        bg = LIME if lime else ACCENT if primary else SIDE if sidebar else INPUT
        fg = BG if primary or lime else MUTED if sidebar else INK
        hover = "#e7ffb2" if lime else "#afd0ff" if primary else ACTIVE
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                         activeforeground=fg, disabledforeground="#8796ad", relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=bg, highlightcolor=ACCENT,
                         cursor="hand2", font=(FONT, 9, "bold"), padx=11, pady=7, **options)

    def entry(self, parent, variable=None, width=22):
        field = tk.Entry(parent, textvariable=variable, width=width, background=INPUT, foreground=INK,
                         insertbackground=INK, selectbackground=ACCENT, selectforeground=BG,
                         relief="flat", highlightthickness=1,
                         highlightbackground=LINE, highlightcolor=ACCENT, font=(FONT, 10))
        field.variable = variable
        return field

    def panel(self, parent):
        return tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightthickness=1, highlightbackground=LINE)

    def heading(self, parent, title):
        self.label(parent, title, size=11, bold=True).pack(anchor="w", pady=(0, 8))

    def show(self, view):
        self.view = view
        self.cards.clear()
        self.search = None
        for child in self.main.winfo_children():
            child.destroy()
        for name, (row, icon, button) in self.nav.items():
            color = ACTIVE if name == view else SIDE
            row.configure(bg=color)
            icon.configure(bg=color)
            button.configure(bg=color, fg=ACCENT if name == view else MUTED, highlightbackground=color)
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x", pady=(0, 15))
        self.label(header, view, bg=BG, size=27, bold=True).pack(side="left")
        if view == "Downloads":
            self.button(header, "Batch add", lambda: self.new_download(False)).pack(side="right", padx=(8, 0))
            if self.draft is None:
                self.button(header, "Customize", self.customize).pack(side="right")
            else:
                self.button(header, "Done", self.save_layout, True).pack(side="right")
                self.button(header, "Reset", self.reset_layout).pack(side="right", padx=7)
            self.quick_add_panel()
        elif view == "Scheduler":
            self.button(header, "+  Schedule download", lambda: self.new_download(True), True).pack(side="right")
        if view == "Browser Extension":
            self.extension_page()
        elif view == "Settings":
            self.settings_page()
        else:
            self.queue_page()
        self.update_live()

    def quick_add_panel(self):
        hero = tk.Frame(self.main, bg=HERO, height=166)
        hero.pack(fill="x", pady=(0, 16))
        hero.pack_propagate(False)
        art = tk.Canvas(hero, width=237, height=166, bg=HERO, highlightthickness=0)
        art.pack(side="right")
        x, y = 115, 82
        for radius in (44, 61, 78, 97, 119):
            art.create_oval(x - radius, y - radius, x + radius, y + radius,
                            outline="#315078", width=1)
        for px, py, fill in ((47, 43, "#82a8dc"), (183, 119, LIME), (211, 87, "#82a8dc"),
                             (76, 132, "#5b81b4"), (147, 15, "#5b81b4")):
            art.create_oval(px - 3, py - 3, px + 3, py + 3, fill=fill, outline="")
        art.create_oval(x - 39, y - 39, x + 39, y + 39, fill="#1d3658", outline="#6d95ca")
        self.draw_arrow(art, x, y, LIME, 27)
        content = tk.Frame(hero, bg=HERO)
        content.pack(side="left", fill="both", expand=True, padx=(21, 4), pady=13)
        self.label(content, "Add a download", bg=HERO, fg="white", size=20, bold=True).pack(anchor="w")
        self.label(content, "Paste a direct HTTP or HTTPS file link.", bg=HERO, fg=HERO_TEXT).pack(anchor="w", pady=(1, 7))
        row = tk.Frame(content, bg=HERO)
        row.pack(fill="x")
        self.quick_entry = self.entry(row, self.quick_url)
        self.quick_entry.configure(background="#203958", foreground="white", insertbackground="white",
                                   highlightbackground="#4b6687", highlightcolor=LIME)
        self.quick_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.quick_entry.bind("<Return>", self.quick_add)
        self.button(row, "Add to queue", self.quick_add, lime=True).pack(side="left", padx=(7, 0))
        self.quick_message = self.label(content, bg=HERO, fg=HERO_TEXT, size=8, anchor="w")
        self.quick_message.pack(fill="x", pady=(4, 0))
        self.quick_message.configure(text="Save to: " + self.destination.get())

    def quick_add(self, _=None):
        try:
            job, = app.enqueue_many([self.quick_url.get().strip()], self.destination.get(), 0)
        except (OSError, ValueError) as error:
            self.quick_message.configure(text=str(error), fg="#ffafbd")
            self.quick_entry.focus_set()
            return
        self.quick_url.set("")
        self.quick_message.configure(text="Added to queue", fg=LIME)
        self.filter = "All"
        self.selected = job["id"]
        self.query.set("")
        self.update_live()

    def focus_search(self):
        if self.search is None:
            self.show("Downloads")
        self.search.focus_set()

    def new_download(self, scheduled):
        dialog = tk.Toplevel(self.root, bg=BG)
        use_dark_title_bar(dialog)
        dialog.title("Schedule a download" if scheduled else "New download")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        card = self.panel(dialog)
        card.pack(fill="both", expand=True, padx=15, pady=15)
        self.heading(card, dialog.title())
        self.label(card, "Direct HTTP or HTTPS links · one per line", fg=MUTED).pack(anchor="w")
        links = tk.Text(card, width=63, height=5, bg=INPUT, fg=INK, relief="flat",
                        insertbackground=INK, selectbackground=ACCENT, selectforeground=BG,
                        highlightthickness=1, highlightbackground=LINE,
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
        error_label = self.label(card, fg=BAD, wraplength=475, justify="left")
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
            self.right = tk.Frame(workspace, bg=BG, width=254)
            self.right.pack(side="right", fill="y", padx=(14, 0))
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
            self.view, "Queue"), size=15, bold=True).pack(side="left")
        self.search = self.entry(bar, self.query, width=18)
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
        table = tk.Frame(queue, bg=PANEL)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for name, heading, width in zip(columns, ("File name", "Progress", "Speed",
                                                 "Starts" if self.view == "Scheduler" else "ETA", "Status"),
                                        (172, 127, 81, 122 if self.view == "Scheduler" else 58, 105)):
            self.tree.heading(name, text=heading, anchor="w", command=lambda name=name: self.sort_by(name))
            self.tree.column(name, width=width, minwidth=40, stretch=name == "name", anchor="w")
        self.tree.tag_configure("alternate", background="#182438")
        self.tree.tag_configure("Completed", foreground=GOOD)
        self.tree.tag_configure("Failed", foreground=BAD)
        self.tree.tag_configure("Downloading", foreground=ACCENT)
        self.tree.bind("<<TreeviewSelect>>", self.select_row)
        self.tree.bind("<Double-1>", lambda _: self.act_on_selection())
        self.tree.bind("<Return>", lambda _: self.act_on_selection())
        self.tree.bind("<Button-3>", self.context_menu)
        self.tree.bind("<Shift-F10>", self.context_menu)
        self.tree.bind("<Delete>", lambda _: self.remove_selected())
        self.scrollbar = ttk.Scrollbar(table, style="Queue.Vertical.TScrollbar",
                                       orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scroll_queue)
        self.tree.pack(fill="both", expand=True, side="left")
        self.empty_mode = None
        self.empty_state = tk.Frame(table, bg=PANEL)
        icon = tk.Canvas(self.empty_state, width=52, height=52, bg=PANEL, highlightthickness=0)
        icon.pack(pady=(0, 9))
        icon.create_oval(0, 0, 52, 52, fill=ACTIVE, outline="")
        self.draw_arrow(icon, 26, 24, ACCENT, 16)
        self.empty_title = self.label(self.empty_state, size=14, bold=True)
        self.empty_title.pack()
        self.empty_hint = self.label(self.empty_state, fg=MUTED, size=9)
        self.empty_hint.pack(pady=(3, 9))
        self.empty_action = self.button(self.empty_state, "", lambda: None)

    def scroll_queue(self, first, last):
        self.scrollbar.set(first, last)
        if float(first) == 0 and float(last) == 1:
            self.scrollbar.pack_forget()
        elif not self.scrollbar.winfo_manager():
            self.scrollbar.pack(side="right", fill="y", before=self.tree)

    def show_empty_queue(self, query):
        mode = (bool(query), self.view, self.filter)
        if self.empty_mode == mode:
            self.empty_state.place(relx=.5, rely=.55, anchor="center")
            return
        self.empty_mode = mode
        self.empty_action.pack_forget()
        if query:
            title, hint = "No matching downloads", "Try another file name or link."
            self.empty_action.configure(text="Clear search", command=lambda: self.query.set(""))
            self.empty_action.pack()
        elif self.view == "Downloads" and self.filter == "All":
            title, hint = "Your queue is empty", "Add a file link above or import several at once."
            self.empty_action.configure(text="Add multiple links", command=lambda: self.new_download(False))
            self.empty_action.pack()
        elif self.view == "Scheduler":
            title, hint = "No scheduled downloads", "Choose a date and time to start a transfer."
        elif self.view == "History":
            title, hint = "No completed downloads", "Finished transfers will appear here."
        else:
            title, hint = f"No {self.filter.lower()} downloads", "Switch to All to see the full queue."
        self.empty_title.configure(text=title)
        self.empty_hint.configure(text=hint)
        self.empty_state.place(relx=.5, rely=.55, anchor="center")

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
        menu = self.menu = tk.Menu(self.root, tearoff=False, bg=PANEL, fg=INK,
                                   activebackground=ACTIVE, activeforeground=INK,
                                   disabledforeground=MUTED, relief="flat")
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
            grip = self.label(header, "⠿", fg=ACCENT, cursor="fleur")
            grip.pack(side="left", padx=(0, 6))
            grip.bind("<ButtonRelease-1>", lambda event: self.drag_panel(key, event))
            self.button(header, "×", lambda: self.change_layout(key, "hide")).pack(side="right")
            self.button(header, "↑", lambda: self.change_layout(key, "up")).pack(side="right", padx=4)
        self.label(header, PANELS[key], bold=True).pack(side="left")
        value = self.label(card, justify="left", anchor="w", wraplength=216)
        value.pack(fill="x")
        self.cards[key] = (card, value)
        if key == "speed":
            self.graph = tk.Canvas(card, height=105, bg=PANEL, highlightthickness=0)
            self.graph.pack(fill="x", pady=(6, 0))
            axis = tk.Frame(card, bg=PANEL)
            axis.pack(fill="x", pady=(5, 0))
            self.label(axis, "60 sec ago", fg=MUTED, size=8).pack(side="left")
            self.label(axis, "Now", fg=MUTED, size=8).pack(side="right")
        if key == "browser":
            self.button(card, "Extension setup", lambda: self.show("Browser Extension")).pack(anchor="w", pady=(9, 0))

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
        self.status.set(f"{len(jobs)} total   /   {len(active)} active   /   {len(completed)} complete")
        limit = rate(state["limit"] * 1024) if state["limit"] else "Off"
        self.footer_speed.configure(text=f"{len(active)} of {state['parallel']} slots in use   /   Speed limit: {limit}")
        if self.view == "Browser Extension":
            self.connection.configure(text="● Connected" if state["connected"] else "○ Waiting for browser extension")
            return
        if self.view == "Settings":
            return
        candidates = {"All": jobs, "Active": active, "Completed": completed,
                      "Failed": [job for job in jobs if job["status"] == "Failed"]}
        shown = candidates[self.filter]
        if self.view == "Scheduler":
            shown = [job for job in jobs if job["status"] == "Scheduled"]
        elif self.view == "History":
            shown = completed
        for name, button in self.filter_buttons.items():
            button.configure(text=f"{name} ({len(candidates[name])})", bg=ACTIVE if name == self.filter else PANEL,
                             fg=ACCENT if name == self.filter else MUTED, highlightbackground=PANEL)
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
            self.show_empty_queue(query)
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
            meter = f"{progress}%  ·  {file_size(job['received'])}" if progress is not None else file_size(job["received"])
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
                label.configure(text=rate(speed), fg=ACCENT, font=(FONT, 18, "bold"))
                self.draw_speed(state["history"])
            elif key == "browser":
                connected = "● Connected" if state["connected"] else "○ Disconnected"
                last = state["last"]
                label.configure(text=f"{connected}\n\nLast link: {last['name']}\n{date(last['time'])}" if last else connected,
                                fg=GOOD if state["connected"] else MUTED)
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
                             fill=ACTIVE, outline="")
        graph.create_line(*points, fill=ACCENT, width=2)

    def refresh(self):
        self.update_live()
        self.root.after(500, self.refresh)
