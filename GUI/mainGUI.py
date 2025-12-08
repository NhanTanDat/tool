import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

from autotool_logic import (
    DATA_DIR,
    CONFIG_PATH,
    AutoToolLogic,
    derive_project_slug,
    compute_links_stats,
)

# =====================================================================
# CONSTANTS: THEME 2025
# =====================================================================

DARK_BG = "#121212"
DARK_BG_ELEVATED = "#1E1E1E"
DARK_BG_CARD = "#252525"
DARK_BORDER = "#333333"
TEXT_PRIMARY = "#F5F5F5"
TEXT_SECONDARY = "#B0B0B0"
ACCENT = "#00B894"      # teal / green
ACCENT_SOFT = "#145A5A"


# =====================================================================
# KEYWORD EDITOR (Toplevel)
# =====================================================================

class KeywordEditor(tk.Toplevel):
    def __init__(self, parent, proj_path: str | None = None):
        super().__init__(parent)
        self.title("Keyword Editor - AutoCut Tool")
        self.geometry("780x520")
        self.configure(bg=DARK_BG)
        self.transient(parent)
        self.grab_set()

        self.proj_path_var = tk.StringVar()
        self.slug_var = tk.StringVar()
        self.file_path_var = tk.StringVar()

        self._build_ui()

        # Nếu gọi với sẵn 1 project path -> load luôn
        if proj_path:
            self.set_project(proj_path)

    # ---------------------------
    def _build_ui(self):
        pad = 10

        frm = ttk.Frame(self, padding=10, style="Card.TFrame")
        frm.pack(fill="both", expand=True)

        row = 0
        ttk.Label(
            frm,
            text="Chọn file Premiere (.prproj):",
            style="Title.TLabel",
        ).grid(row=row, column=0, sticky="w", padx=pad, pady=(pad, 4), columnspan=3)
        row += 1

        entry = ttk.Entry(frm, textvariable=self.proj_path_var, width=60)
        entry.grid(row=row, column=0, sticky="we", padx=(pad, 4), pady=2, columnspan=2)
        ttk.Button(frm, text="Browse...", style="Accent.TButton", command=self.choose_project).grid(
            row=row, column=2, sticky="w", padx=(0, pad), pady=2
        )
        row += 1

        ttk.Label(frm, text="Project slug:", style="LabelMuted.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=(4, 2)
        )
        ttk.Label(frm, textvariable=self.slug_var, style="LabelSub.TLabel").grid(
            row=row, column=1, sticky="w", padx=pad, pady=(4, 2), columnspan=2
        )
        row += 1

        ttk.Label(frm, text="File keyword (list_name.txt):", style="LabelMuted.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=(2, 2)
        )
        ttk.Label(frm, textvariable=self.file_path_var, style="LabelSub.TLabel").grid(
            row=row, column=1, sticky="w", padx=pad, pady=(2, 2), columnspan=2
        )
        row += 1

        ttk.Label(
            frm,
            text="Nhập mỗi dòng 1 KEYWORD (không cần đánh số).\nTool sẽ tự sinh '1 keyword', '2 keyword', ...",
            style="LabelHint.TLabel",
            wraplength=680,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=pad, pady=(8, 4))
        row += 1

        # Text box
        text_frame = ttk.Frame(frm, style="CardInner.TFrame")
        text_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=pad, pady=(2, 4))
        self.text = tk.Text(
            text_frame,
            height=15,
            wrap="word",
            bg=DARK_BG_CARD,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT,
            relief="flat",
            bd=0,
        )
        self.text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        scroll.pack(side="right", fill="y", pady=4)
        self.text.configure(yscrollcommand=scroll.set)

        frm.rowconfigure(row, weight=1)
        row += 1

        # Buttons
        btn_frame = ttk.Frame(frm, style="Card.TFrame")
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="e", padx=pad, pady=(8, pad))

        ttk.Button(btn_frame, text="Load từ file", command=self.load_keywords).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Lưu keyword", style="Accent.TButton", command=self.save_keywords).pack(
            side="left", padx=6
        )
        ttk.Button(btn_frame, text="Đóng", command=self.destroy).pack(
            side="left", padx=(6, 0)
        )

        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

    # ---------------------------
    def set_project(self, path: str):
        """Gán project path + slug + list_name.txt rồi load sẵn keyword."""
        self.proj_path_var.set(path)
        slug = derive_project_slug(path)
        self.slug_var.set(slug)

        proj_data_dir = os.path.join(DATA_DIR, slug)
        os.makedirs(proj_data_dir, exist_ok=True)
        names_path = os.path.join(proj_data_dir, "list_name.txt")
        self.file_path_var.set(names_path)

        self.load_keywords()

    def choose_project(self):
        path = filedialog.askopenfilename(
            title="Chọn file Premiere",
            filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")],
        )
        if not path:
            return
        self.set_project(path)

    # ---------------------------
    def load_keywords(self):
        path = self.file_path_var.get().strip()
        if not path:
            messagebox.showerror("Lỗi", "Chưa xác định được file list_name.txt.\nHãy chọn .prproj trước.")
            return

        self.text.delete("1.0", "end")

        if not os.path.isfile(path):
            # chưa có, coi như rỗng
            return

        try:
            keywords: list[str] = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    # Bỏ qua dòng là link (https)
                    if line.startswith("http://") or line.startswith("https://"):
                        continue
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2 and parts[0].isdigit():
                        kw = parts[1].strip()
                    else:
                        kw = line
                    if kw:
                        keywords.append(kw)

            if keywords:
                self.text.insert("1.0", "\n".join(keywords))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được file keyword:\n{e}")

    # ---------------------------
    def save_keywords(self):
        path = self.file_path_var.get().strip()
        if not path:
            messagebox.showerror("Lỗi", "Chưa xác định được file list_name.txt.\nHãy chọn .prproj trước.")
            return

        raw = self.text.get("1.0", "end")
        lines = [ln.strip() for ln in raw.splitlines()]
        keywords = [ln for ln in lines if ln]

        if not keywords:
            if not messagebox.askyesno(
                "Xác nhận",
                "Danh sách keyword đang trống.\nBạn có chắc muốn ghi file trống (sẽ xoá nội dung cũ)?",
            ):
                return

        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                for idx, kw in enumerate(keywords, start=1):
                    f.write(f"{idx} {kw}\n")
            messagebox.showinfo(
                "Đã lưu",
                f"Đã lưu {len(keywords)} keyword vào:\n{path}",
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không ghi được file keyword:\n{e}")


# =====================================================================
# MAIN GUI
# =====================================================================

class AutoToolGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoTool - Tự động hoá Premiere")
        self.geometry("1040x700")
        self.minsize(960, 640)
        self.configure(bg=DARK_BG)

        # Core logic tách riêng, không phụ thuộc Tkinter
        self.logic = AutoToolLogic(DATA_DIR)

        self.version_var = tk.StringVar(value="2023")
        self.download_type_var = tk.StringVar(value="mp4")  # mp4 | mp3
        self.mode_var = tk.StringVar(value="both")  # both | video | image
        self.regen_links_var = tk.BooleanVar(value=False)
        self.videos_per_keyword_var = tk.StringVar(value="10")
        self.images_per_keyword_var = tk.StringVar(value="10")
        self.max_duration_var = tk.StringVar(value="20")  # mặc định tối đa 20 phút
        self.min_duration_var = tk.StringVar(value="4")   # mặc định tối thiểu 4 phút
        # Batch projects list
        self.batch_projects: list[str] = []
        self.premier_projects: list[str] = []

        # progress bar
        self.progress_var: tk.DoubleVar | None = None
        self.progress_label_var: tk.StringVar | None = None

        # trạng thái current tab (0: download, 1: premier)
        self.active_tab = tk.IntVar(value=0)

        # Prevent saving while loading initial config
        self._loading_config = True

        # style
        self._init_style()

        # Load previous config
        try:
            self._load_config()
        except Exception:
            pass

        self._build_layout()

        # Populate batch list UI if loaded from config
        try:
            self._refresh_batch_listbox()
            self._refresh_premier_listbox()
        except Exception:
            pass

        # Save config on close
        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

        # Now that UI is ready, bind variable change traces for auto-save
        self._loading_config = False
        try:
            self._bind_config_traces()
        except Exception:
            pass

        # Logging bridge (nếu có)
        try:
            from core import logging_bridge as _lb  # type: ignore
            _lb.register_gui_logger(self.log)
            if not _lb.is_active():
                _lb.activate(mirror_to_console=True)
            self.log("[Logging] Bắt đầu ghi log toàn cục.")
        except Exception as e:
            self.log(f"CẢNH BÁO: Không kích hoạt được logging bridge: {e}")
        self.log("Sẵn sàng.")

    # ------------------------------------------------------------------
    def _init_style(self):
        style = ttk.Style()
        # theme
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "TFrame",
            background=DARK_BG,
        )
        style.configure(
            "Card.TFrame",
            background=DARK_BG_ELEVATED,
            relief="flat",
        )
        style.configure(
            "CardInner.TFrame",
            background=DARK_BG_CARD,
            relief="flat",
            borderwidth=1,
        )
        style.configure(
            "Sidebar.TFrame",
            background="#0D0D0D",
        )
        style.configure(
            "TLabel",
            background=DARK_BG,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "Title.TLabel",
            background=DARK_BG_ELEVATED,
            foreground=TEXT_PRIMARY,
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "HeaderTitle.TLabel",
            background="#0D0D0D",
            foreground=TEXT_PRIMARY,
            font=("Segoe UI Semibold", 14),
        )
        style.configure(
            "HeaderSub.TLabel",
            background="#0D0D0D",
            foreground=TEXT_SECONDARY,
            font=("Segoe UI", 9),
        )
        style.configure(
            "LabelMuted.TLabel",
            foreground=TEXT_SECONDARY,
            background=DARK_BG_ELEVATED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "LabelSub.TLabel",
            foreground=TEXT_SECONDARY,
            background=DARK_BG_ELEVATED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "LabelHint.TLabel",
            foreground=TEXT_SECONDARY,
            background=DARK_BG_ELEVATED,
            font=("Segoe UI", 9, "italic"),
        )
        style.configure(
            "SidebarButton.TButton",
            background="#0D0D0D",
            foreground=TEXT_SECONDARY,
            padding=8,
            relief="flat",
            borderwidth=0,
            anchor="w",
        )
        style.map(
            "SidebarButton.TButton",
            background=[("active", "#151515"), ("selected", "#1F1F1F")],
            foreground=[("active", TEXT_PRIMARY)],
        )
        style.configure(
            "SidebarButtonActive.TButton",
            background=ACCENT_SOFT,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 4),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#00CFA2")],
        )
        style.configure(
            "TButton",
            background=DARK_BG_CARD,
            foreground=TEXT_PRIMARY,
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[("active", "#2C2C2C")],
        )
        style.configure(
            "TEntry",
            fieldbackground=DARK_BG_CARD,
            foreground=TEXT_PRIMARY,
            insertcolor=ACCENT,
            borderwidth=0,
        )
        style.configure(
            "TCombobox",
            fieldbackground=DARK_BG_CARD,
            foreground=TEXT_PRIMARY,
            background=DARK_BG_CARD,
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=DARK_BG_CARD,
            background=ACCENT,
            bordercolor=DARK_BG_CARD,
            lightcolor=ACCENT,
            darkcolor=ACCENT_SOFT,
        )

    # ------------------------------------------------------------------
    def _build_layout(self):
        # root grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # HEADER
        header = ttk.Frame(self, padding=(16, 10), style="Sidebar.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_columnconfigure(0, weight=1)

        title_wrap = ttk.Frame(header, style="Sidebar.TFrame")
        title_wrap.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_wrap,
            text="AutoTool",
            style="HeaderTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_wrap,
            text="Tự động hoá tải video/ảnh + dựng timeline cho Premiere",
            style="HeaderSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        tag = ttk.Label(
            header,
            text="2025 • Dark UI",
            background=ACCENT_SOFT,
            foreground=TEXT_PRIMARY,
            padding=(10, 2),
            font=("Segoe UI", 9),
        )
        tag.grid(row=0, column=1, sticky="e", padx=(0, 4))

        # SIDEBAR (pseudo tabs)
        sidebar = ttk.Frame(self, padding=(10, 10, 6, 10), style="Sidebar.TFrame")
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(3, weight=1)

        ttk.Label(
            sidebar,
            text="Chế độ",
            style="HeaderSub.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.btn_tab_download = ttk.Button(
            sidebar,
            text="  ⬇  Auto Download",
            style="SidebarButtonActive.TButton",
            command=lambda: self._switch_tab(0),
        )
        self.btn_tab_download.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        self.btn_tab_premier = ttk.Button(
            sidebar,
            text="  🎬  Auto Premier",
            style="SidebarButton.TButton",
            command=lambda: self._switch_tab(1),
        )
        self.btn_tab_premier.grid(row=2, column=0, sticky="ew")

        # small info
        sep = ttk.Separator(sidebar, orient="horizontal")
        sep.grid(row=3, column=0, sticky="ew", pady=(16, 8))
        ttk.Label(
            sidebar,
            text="Cấu hình chung",
            style="HeaderSub.TLabel",
        ).grid(row=4, column=0, sticky="w", pady=(0, 4))

        info_box = ttk.Frame(sidebar, padding=8, style="CardInner.TFrame")
        info_box.grid(row=5, column=0, sticky="ew")
        ttk.Label(
            info_box,
            text="• Chọn file .prproj\n• Nhập keyword trong Keyword Editor\n• Chạy Auto Download",
            style="LabelHint.TLabel",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        sidebar.grid_rowconfigure(6, weight=1)
        footer = ttk.Label(
            sidebar,
            text="© AutoTool 2025",
            style="HeaderSub.TLabel",
        )
        footer.grid(row=7, column=0, sticky="w", pady=(12, 0))

        # MAIN CONTENT AREA (stacked frames)
        content = ttk.Frame(self, padding=(4, 10, 10, 10), style="TFrame")
        content.grid(row=1, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.frame_download = ttk.Frame(content, padding=10, style="Card.TFrame")
        self.frame_premier = ttk.Frame(content, padding=10, style="Card.TFrame")

        self.frame_download.grid(row=0, column=0, sticky="nsew")
        self.frame_premier.grid(row=0, column=0, sticky="nsew")

        # Build content for each "tab"
        self._build_download_tab(self.frame_download)
        self._build_premier_tab(self.frame_premier)

        # Status bar
        status = ttk.Frame(self, padding=(10, 4), style="Sidebar.TFrame")
        status.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_label = ttk.Label(
            status,
            text="Sẵn sàng.",
            style="HeaderSub.TLabel",
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        self._switch_tab(0)

    # ------------------------------------------------------------------
    def _build_download_tab(self, parent: ttk.Frame):
        pad = 8
        parent.grid_rowconfigure(3, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # TOP: chọn project + config
        header = ttk.Frame(parent, style="Card.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ttk.Label(header, text="Auto Download", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", padx=pad, pady=(pad, 2)
        )
        ttk.Label(
            header,
            text="Tải video/ảnh theo keyword và sinh timeline cho Premiere",
            style="LabelHint.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=pad, pady=(0, 8))

        # LEFT: list project + buttons
        proj_card = ttk.Frame(parent, padding=10, style="CardInner.TFrame")
        proj_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        proj_card.grid_rowconfigure(2, weight=1)

        ttk.Label(proj_card, text="Danh sách project (.prproj)", style="LabelMuted.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        btn_row = ttk.Frame(proj_card, style="CardInner.TFrame")
        btn_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Button(btn_row, text="➕  Thêm file", command=self.add_batch_projects).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="🗑  Xoá đã chọn", command=self.remove_selected_batch).pack(
            side="left", padx=(0, 4)
        )

        list_frame = ttk.Frame(proj_card, style="CardInner.TFrame")
        list_frame.grid(row=2, column=0, columnspan=3, sticky="nsew")
        self.batch_list = tk.Listbox(
            list_frame,
            height=8,
            selectmode="extended",
            bg=DARK_BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        self.batch_list.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=(2, 2))
        bscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.batch_list.yview)
        bscroll.pack(side="right", fill="y", pady=(2, 2))
        self.batch_list.configure(yscrollcommand=bscroll.set)

        # RIGHT: config
        cfg_card = ttk.Frame(parent, padding=10, style="CardInner.TFrame")
        cfg_card.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        cfg_card.grid_columnconfigure(1, weight=1)

        row = 0
        ttk.Label(cfg_card, text="Cấu hình tải & AI", style="LabelMuted.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        row += 1

        ttk.Label(cfg_card, text="Phiên bản Premiere:", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Combobox(
            cfg_card,
            textvariable=self.version_var,
            values=["2022", "2023", "2024", "2025"],
            width=12,
            state="readonly",
        ).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1

        ttk.Label(cfg_card, text="Định dạng tải:", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Combobox(
            cfg_card,
            textvariable=self.download_type_var,
            values=["mp4", "mp3"],
            width=12,
            state="readonly",
        ).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1

        ttk.Label(cfg_card, text="Số video / keyword:", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Entry(cfg_card, textvariable=self.videos_per_keyword_var, width=8).grid(
            row=row, column=1, sticky="w", padx=pad, pady=2
        )
        row += 1

        ttk.Label(cfg_card, text="Thời lượng tối đa (phút):", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Entry(cfg_card, textvariable=self.max_duration_var, width=8).grid(
            row=row, column=1, sticky="w", padx=pad, pady=2
        )
        row += 1

        ttk.Label(cfg_card, text="Thời lượng tối thiểu (phút):", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Entry(cfg_card, textvariable=self.min_duration_var, width=8).grid(
            row=row, column=1, sticky="w", padx=pad, pady=2
        )
        row += 1

        ttk.Label(cfg_card, text="Số ảnh / keyword:", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Entry(cfg_card, textvariable=self.images_per_keyword_var, width=8).grid(
            row=row, column=1, sticky="w", padx=pad, pady=2
        )
        row += 1

        ttk.Label(cfg_card, text="Chế độ chạy:", style="LabelSub.TLabel").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Combobox(
            cfg_card,
            textvariable=self.mode_var,
            values=["both", "video", "image"],
            width=10,
            state="readonly",
        ).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1

        ttk.Checkbutton(
            cfg_card,
            text='Ép tạo lại link ở lần chạy sau',
            variable=self.regen_links_var,
            style="TCheckbutton",
        ).grid(row=row, column=0, columnspan=2, sticky='w', padx=pad, pady=(4, 2))
        row += 1

        # ACTION BUTTONS
        btn_frame = ttk.Frame(cfg_card, style="CardInner.TFrame")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=pad, pady=(10, 2))
        ttk.Button(btn_frame, text="✔  Kiểm tra", command=self.validate_inputs).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(
            btn_frame,
            text="▶  Chạy Auto download",
            style="Accent.TButton",
            command=self.run_batch_automation,
        ).pack(side="left", padx=6)
        ttk.Button(
            btn_frame,
            text="🔗  Trạng thái link",
            command=self.open_links_status_window,
        ).pack(side="left", padx=6)
        ttk.Button(
            btn_frame,
            text="✏  Keyword Editor",
            command=self.open_keyword_editor,
        ).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="🧹  Xoá log", command=self.clear_log).pack(
            side="left", padx=6
        )

        # PROGRESS + LOG
        # Progress
        progress_card = ttk.Frame(parent, padding=10, style="CardInner.TFrame")
        progress_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        progress_card.grid_columnconfigure(1, weight=1)

        ttk.Label(progress_card, text="Tiến độ", style="LabelMuted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.progress_var = tk.DoubleVar(value=0.0)
        progress_bar = ttk.Progressbar(
            progress_card,
            maximum=100,
            variable=self.progress_var,
            mode="determinate",
            length=300,
            style="Horizontal.TProgressbar",
        )
        progress_bar.grid(row=0, column=1, sticky="we", padx=(8, 0))

        self.progress_label_var = tk.StringVar(value="")
        ttk.Label(
            progress_card,
            textvariable=self.progress_label_var,
            style="LabelHint.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Log
        log_card = ttk.Frame(parent, padding=10, style="CardInner.TFrame")
        log_card.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        ttk.Label(log_card, text="Nhật ký Auto Download", style="LabelMuted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.log_text = tk.Text(
            log_card,
            height=10,
            wrap="word",
            bg=DARK_BG_CARD,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT,
            relief="flat",
            bd=0,
        )
        self.log_text.grid(
            row=1, column=0, sticky="nsew", pady=(2, 2)
        )
        scroll = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(2, 2))
        self.log_text.configure(yscrollcommand=scroll.set)

    # ------------------------------------------------------------------
    def _build_premier_tab(self, parent: ttk.Frame):
        pad = 8
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        ttk.Label(parent, text="Auto Premier", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", padx=pad, pady=(pad, 2)
        )
        ttk.Label(
            parent,
            text="Chạy script Premiere automation cho danh sách project.",
            style="LabelHint.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=pad, pady=(0, 6))

        main = ttk.Frame(parent, padding=8, style="CardInner.TFrame")
        main.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Project list
        ttk.Label(main, text="Danh sách project (.prproj)", style="LabelMuted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        btn_row = ttk.Frame(main, style="CardInner.TFrame")
        btn_row.grid(row=1, column=0, sticky="w", pady=(0, 4))
        ttk.Button(btn_row, text="➕  Thêm file", command=self.add_premier_projects).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(
            btn_row, text="🗑  Xoá đã chọn", command=self.remove_selected_premier
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            btn_row, text="⇄  Lấy từ tab Download", command=self.copy_from_automation
        ).pack(side="left", padx=(0, 4))

        list_frame = ttk.Frame(main, style="CardInner.TFrame")
        list_frame.grid(row=2, column=0, sticky="nsew")
        self.premier_list = tk.Listbox(
            list_frame,
            height=8,
            selectmode="extended",
            bg=DARK_BG_CARD,
            fg=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        self.premier_list.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=(2, 2))
        pscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.premier_list.yview)
        pscroll.pack(side="right", fill="y", pady=(2, 2))
        self.premier_list.configure(yscrollcommand=pscroll.set)

        # Buttons + log
        action_row = ttk.Frame(main, style="CardInner.TFrame")
        action_row.grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            action_row,
            text="▶  Chạy Auto Premier",
            style="Accent.TButton",
            command=self.run_premier_automation,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(action_row, text="🧹  Xoá log", command=self.clear_log2).pack(
            side="left", padx=4
        )

        log_card = ttk.Frame(main, style="CardInner.TFrame")
        log_card.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        ttk.Label(log_card, text="Nhật ký Auto Premier", style="LabelMuted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.log_text2 = tk.Text(
            log_card,
            height=10,
            wrap="word",
            bg=DARK_BG_CARD,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT,
            relief="flat",
            bd=0,
        )
        self.log_text2.grid(
            row=1, column=0, sticky="nsew", pady=(2, 2)
        )
        scroll2 = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text2.yview)
        scroll2.grid(row=1, column=1, sticky="ns", pady=(2, 2))
        self.log_text2.configure(yscrollcommand=scroll2.set)

    # ------------------------------------------------------------------
    def _switch_tab(self, idx: int):
        self.active_tab.set(idx)
        if idx == 0:
            self.frame_download.tkraise()
            self.btn_tab_download.configure(style="SidebarButtonActive.TButton")
            self.btn_tab_premier.configure(style="SidebarButton.TButton")
        else:
            self.frame_premier.tkraise()
            self.btn_tab_download.configure(style="SidebarButton.TButton")
            self.btn_tab_premier.configure(style="SidebarButtonActive.TButton")

    # =================================================================
    # Utility methods
    # =================================================================
    def log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.status_label.config(text=msg)

    def log2(self, msg: str):
        self.log_text2.insert("end", msg + "\n")
        self.log_text2.see("end")
        self.status_label.config(text=msg)

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def clear_log2(self):
        self.log_text2.delete("1.0", "end")

    # Progress helpers
    def reset_progress(self):
        try:
            if self.progress_var is not None:
                self.progress_var.set(0.0)
            if self.progress_label_var is not None:
                self.progress_label_var.set("")
            self.update_idletasks()
        except Exception:
            pass

    def update_progress(self, value: float, message: str | None = None):
        """Cập nhật thanh tiến độ tổng hợp (0–100)."""
        try:
            v = max(0.0, min(100.0, float(value)))
            if self.progress_var is not None:
                self.progress_var.set(v)
            if message is not None and self.progress_label_var is not None:
                self.progress_label_var.set(str(message))
            self.update_idletasks()
        except Exception:
            pass

    # =================================================================
    # Keyword editor opener
    # =================================================================
    def open_keyword_editor(self):
        """Mở cửa sổ sửa keyword cho project đang chọn trong tab Download."""
        proj_path = None

        # Ưu tiên: project đang được chọn trong list
        try:
            sel = self.batch_list.curselection()
            if sel:
                proj_path = self.batch_list.get(sel[0])
        except Exception:
            proj_path = None

        # Nếu chưa chọn gì mà vẫn có project -> lấy phần tử đầu
        if proj_path is None and self.batch_projects:
            proj_path = self.batch_projects[0]

        if not proj_path:
            messagebox.showwarning(
                "Keyword Editor",
                "Chưa có project nào trong tab Download.\n"
                "Hãy thêm ít nhất 1 file .prproj.",
            )
            return

        KeywordEditor(self, proj_path)

    # =================================================================
    # Validation
    # =================================================================
    def validate_inputs(self):
        version = self.version_var.get().strip()
        mode = self.mode_var.get().strip()

        ok = True
        if not self.batch_projects:
            self.log("LỖI: Chưa chọn file .prproj nào.")
            ok = False
        else:
            invalid_projects = []
            for proj in self.batch_projects:
                if not os.path.isfile(proj):
                    invalid_projects.append(proj)
                elif not proj.lower().endswith(".prproj"):
                    self.log(f"CẢNH BÁO: File không có đuôi .prproj: {proj}")

            if invalid_projects:
                self.log(f"LỖI: Không tìm thấy file project: {', '.join(invalid_projects)}")
                ok = False

        self.log(
            f"Phiên bản Premiere: {version}; "
            f"Chế độ: {mode}; "
            f"Số project: {len(self.batch_projects) if self.batch_projects else 0}"
        )
        if ok:
            self.log("Kiểm tra hợp lệ.")
            messagebox.showinfo("Kiểm tra", "Thông tin hợp lệ (có thể chạy).")
        else:
            messagebox.showerror("Kiểm tra", "Không hợp lệ. Xem log.")

    # =================================================================
    # Batch helpers
    # =================================================================
    def add_batch_projects(self):
        files = filedialog.askopenfilenames(
            title="Chọn nhiều file .prproj",
            filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")],
        )
        if not files:
            return
        added = 0
        for f in files:
            if f not in self.batch_projects:
                self.batch_projects.append(f)
                self.batch_list.insert("end", f)
                added += 1
        self.log(f"Đã thêm {added} project vào danh sách batch.")

    def remove_selected_batch(self):
        sel = list(self.batch_list.curselection())
        if not sel:
            return
        sel.reverse()
        for idx in sel:
            try:
                path = self.batch_list.get(idx)
            except Exception:
                path = None
            try:
                self.batch_list.delete(idx)
            except Exception:
                pass
            if path and path in self.batch_projects:
                try:
                    self.batch_projects.remove(path)
                except Exception:
                    pass
        self.log("Đã xoá mục đã chọn khỏi danh sách batch.")

    def run_batch_automation(self):
        if not self.batch_projects:
            messagebox.showwarning("Batch", "Chưa có file .prproj nào trong danh sách.")
            return

        self.log(f"=== BẮT ĐẦU CHẠY HÀNG LOẠT ({len(self.batch_projects)} project) ===")
        for i, proj_path in enumerate(self.batch_projects, start=1):
            try:
                self.log(f"-- ({i}/{len(self.batch_projects)}) {proj_path}")
                self.reset_progress()

                # Gọi core logic
                self.logic.run_automation_for_project(
                    proj_path,
                    version=self.version_var.get().strip(),
                    download_type=self.download_type_var.get().strip(),
                    mode=self.mode_var.get().strip(),
                    videos_per_keyword=self.videos_per_keyword_var.get().strip(),
                    images_per_keyword=self.images_per_keyword_var.get().strip(),
                    max_duration=self.max_duration_var.get().strip(),
                    min_duration=self.min_duration_var.get().strip(),
                    regen_links=bool(self.regen_links_var.get()),
                    log=self.log,
                    update_progress=self.update_progress,
                )

                self.update()
            except Exception as e:
                self.log(f"LỖI batch item: {e}")
        self.log("=== KẾT THÚC CHẠY HÀNG LOẠT ===")
        try:
            self._save_config()
        except Exception:
            pass

    # =================================================================
    # Premier helpers
    # =================================================================
    def add_premier_projects(self):
        files = filedialog.askopenfilenames(
            title="Chọn nhiều file .prproj",
            filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")],
        )
        if not files:
            return
        added = 0
        for f in files:
            if f not in self.premier_projects:
                self.premier_projects.append(f)
                self.premier_list.insert("end", f)
                added += 1
        self.log2(f"Đã thêm {added} project vào danh sách premier.")

    def remove_selected_premier(self):
        sel = list(self.premier_list.curselection())
        if not sel:
            return
        sel.reverse()
        for idx in sel:
            try:
                path = self.premier_list.get(idx)
            except Exception:
                path = None
            try:
                self.premier_list.delete(idx)
            except Exception:
                pass
            if path and path in self.premier_projects:
                try:
                    self.premier_projects.remove(path)
                except Exception:
                    pass
        self.log2("Đã xoá mục đã chọn khỏi danh sách premier.")

    def copy_from_automation(self):
        self.premier_projects = list(self.batch_projects)
        self._refresh_premier_listbox()
        self.log2(f"Đã sao chép {len(self.premier_projects)} project từ tab Download.")

    def run_premier_automation(self):
        try:
            from core.premierCore.control import run_premier_script  # type: ignore
        except Exception:
            try:
                import importlib
                run_premier_script = importlib.import_module(
                    "core.premierCore.control"
                ).run_premier_script  # type: ignore
            except Exception as e:
                self.log2(f"LỖI: Không thể import run_premier_script: {e}")
                run_premier_script = None
        if not self.premier_projects:
            messagebox.showwarning("Premier", "Chưa có file .prproj nào trong danh sách.")
            return
        if run_premier_script is None:
            self.log2("LỖI: Không thể import run_premier_script từ control.py")
            return
        self.log2(
            f"=== BẮT ĐẦU CHẠY PREMIER AUTOMATION ({len(self.premier_projects)} project) ==="
        )
        num = 0
        for i, proj_path in enumerate(self.premier_projects, start=1):
            try:
                self.log2(f"-- ({i}/{len(self.premier_projects)}) {proj_path}")
                project_slug = self._derive_project_slug(proj_path)
                data_folder = os.path.join(DATA_DIR, project_slug).replace('\\', '/')
                project_path_unix = proj_path.replace('\\', '/')
                resource_dir = os.path.join(
                    os.path.dirname(proj_path), 'resource'
                ).replace('\\', '/')
                path_txt_content = (
                    f"project_slug={project_slug}\n"
                    f"data_folder={data_folder}\n"
                    f"project_path={project_path_unix}\n"
                    f"resource_dir={resource_dir}\n"
                )
                path_txt_path = os.path.join(DATA_DIR, 'path.txt')
                try:
                    with open(path_txt_path, 'w', encoding='utf-8') as f:
                        f.write(path_txt_content)
                    self.log2(f"Đã cập nhật path.txt cho {project_slug}")
                except Exception as e:
                    self.log2(f"LỖI khi ghi path.txt: {e}")
                    continue

                proj_path_win = '"' + proj_path.replace('/', '\\') + '"'  # for Windows
                num += 1
                run_premier_script(None, proj_path_win, num)
                self.update()
            except Exception as e:
                self.log2(f"LỖI premier item: {e}")
        self.log2("=== KẾT THÚC PREMIER AUTOMATION ===")
        try:
            self._save_config()
        except Exception:
            pass

    def _refresh_premier_listbox(self):
        try:
            self.premier_list.delete(0, 'end')
            for item in self.premier_projects:
                self.premier_list.insert('end', item)
        except Exception:
            pass

    # =================================================================
    # Download images (nếu chỉ muốn tải ảnh)
    # =================================================================
    def run_download_images(self):
        if not self.batch_projects:
            self.log("LỖI: Chưa chọn file .prproj nào.")
            return

        proj = self.batch_projects[0]

        # Gọi core logic (không dính Tkinter)
        self.logic.run_download_images(proj, log=self.log)

        try:
            self._save_config()
        except Exception:
            pass

    # =================================================================
    # Helper slug
    # =================================================================
    def _derive_project_slug(self, proj_path: str) -> str:
        return derive_project_slug(proj_path)

    # =================================================================
    # Links status window
    # =================================================================
    def open_links_status_window(self):
        proj_path = None
        try:
            sel = self.batch_list.curselection()
            if sel:
                proj_path = self.batch_list.get(sel[0])
        except Exception:
            proj_path = None

        if proj_path is None and self.batch_projects:
            proj_path = self.batch_projects[0]

        if not proj_path:
            self.log("LỖI: Chưa có project nào trong tab Download.")
            messagebox.showwarning("Trạng thái link", "Chưa có project nào trong tab Download.")
            return

        slug = self._derive_project_slug(proj_path)
        project_dir = os.path.join(DATA_DIR, slug)
        links_path = os.path.join(project_dir, 'dl_links.txt')
        names_path = os.path.join(project_dir, 'list_name.txt')
        groups, links = compute_links_stats(links_path)

        win = tk.Toplevel(self)
        win.title(f"Trạng thái Link - {slug}")
        win.geometry('430x280')
        win.configure(bg=DARK_BG)
        win.transient(self)
        win.grab_set()

        pad = 10
        info_frame = ttk.Frame(win, padding=pad, style="Card.TFrame")
        info_frame.pack(fill='both', expand=True)

        ttk.Label(info_frame, text=f"Project: {proj_path}", style="LabelSub.TLabel").grid(
            row=0, column=0, sticky='w', pady=(0, 4)
        )
        ttk.Label(info_frame, text="Thư mục dữ liệu project:", style="LabelMuted.TLabel").grid(
            row=1, column=0, sticky='w'
        )
        ttk.Label(info_frame, text=project_dir, style="LabelSub.TLabel").grid(
            row=2, column=0, sticky='w', pady=(0, 6)
        )

        if os.path.isfile(names_path):
            try:
                with open(names_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_names = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                raw_names = []
        else:
            raw_names = []

        ttk.Label(info_frame, text=f"File tên instance: {len(raw_names)} dòng", style="LabelSub.TLabel").grid(
            row=3, column=0, sticky='w'
        )
        ttk.Label(
            info_frame,
            text=f"File link: {'TÌM THẤY ✅' if os.path.isfile(links_path) else 'THIẾU ⚠'}",
            style="LabelSub.TLabel",
        ).grid(row=4, column=0, sticky='w', pady=(2, 2))
        ttk.Label(info_frame, text=f"Số nhóm keyword: {groups}", style="LabelSub.TLabel").grid(
            row=5, column=0, sticky='w'
        )
        ttk.Label(info_frame, text=f"Tổng số link: {links}", style="LabelSub.TLabel").grid(
            row=6, column=0, sticky='w'
        )

        ttk.Separator(info_frame, orient='horizontal').grid(
            row=7, column=0, sticky='ew', pady=8
        )

        btns = ttk.Frame(info_frame, style="Card.TFrame")
        btns.grid(row=8, column=0, sticky='e', pady=(4, 0))
        ttk.Button(btns, text='Đóng', command=win.destroy).pack(side='left')

    # =================================================================
    # Config persistence
    # =================================================================
    def _save_config(self):
        try:
            cfg = {
                'version': self.version_var.get().strip(),
                'mode': self.mode_var.get().strip(),
                'download_type': self.download_type_var.get().strip(),
                'videos_per_keyword': self.videos_per_keyword_var.get().strip(),
                'images_per_keyword': self.images_per_keyword_var.get().strip(),
                'max_duration': self.max_duration_var.get().strip(),
                'min_duration': self.min_duration_var.get().strip(),
                'regen_links': bool(self.regen_links_var.get()),
                'batch_projects': list(self.batch_projects)
                if isinstance(self.batch_projects, list)
                else [],
                'premier_projects': list(self.premier_projects)
                if isinstance(self.premier_projects, list)
                else [],
            }
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            try:
                self.log("CẢNH BÁO: Không ghi được config.")
            except Exception:
                pass

    def _load_config(self):
        if not os.path.isfile(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception as e:
            try:
                self.log(f"CẢNH BÁO: Không đọc được config: {e}")
            except Exception:
                pass
            return
        try:
            if 'version' in cfg:
                self.version_var.set(str(cfg['version']))
            if 'mode' in cfg:
                self.mode_var.set(str(cfg['mode']))
            if 'download_type' in cfg:
                self.download_type_var.set(str(cfg['download_type']))
            if 'videos_per_keyword' in cfg:
                self.videos_per_keyword_var.set(str(cfg['videos_per_keyword']))
            if 'images_per_keyword' in cfg:
                self.images_per_keyword_var.set(str(cfg['images_per_keyword']))
            if 'max_duration' in cfg:
                self.max_duration_var.set(str(cfg['max_duration']))
            if 'min_duration' in cfg:
                self.min_duration_var.set(str(cfg['min_duration']))
            if 'regen_links' in cfg:
                try:
                    self.regen_links_var.set(bool(cfg['regen_links']))
                except Exception:
                    pass
            if 'batch_projects' in cfg and isinstance(cfg['batch_projects'], list):
                self.batch_projects = [str(x) for x in cfg['batch_projects']]
            if 'premier_projects' in cfg and isinstance(cfg['premier_projects'], list):
                self.premier_projects = [str(x) for x in cfg['premier_projects']]
        except Exception as e:
            try:
                self.log(f"CẢNH BÁO: Không áp dụng được config: {e}")
            except Exception:
                pass

    def _refresh_batch_listbox(self):
        try:
            self.batch_list.delete(0, 'end')
            for item in self.batch_projects:
                self.batch_list.insert('end', item)
        except Exception:
            pass

    def _on_close(self):
        try:
            self._save_config()
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def _on_var_change(self, *args):
        if getattr(self, '_loading_config', False):
            return
        try:
            self._save_config()
        except Exception:
            pass

    def _bind_config_traces(self):
        vars_to_bind = [
            self.version_var,
            self.mode_var,
            self.download_type_var,
            self.videos_per_keyword_var,
            self.images_per_keyword_var,
            self.max_duration_var,
            self.min_duration_var,
            self.regen_links_var,
        ]
        for v in vars_to_bind:
            try:
                v.trace_add('write', self._on_var_change)
            except Exception:
                try:
                    v.trace('w', self._on_var_change)
                except Exception:
                    pass


# =====================================================================
# Entrypoint
# =====================================================================

def main():
    app = AutoToolGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
