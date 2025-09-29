import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------------------------------------------------------------------------
# Ensure project root (where 'core' lives) is on sys.path
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, '..'))  # project root
DATA_DIR = os.path.join(_ROOT_DIR, 'data')
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

# NOTE: Heavy modules (pywinauto / selenium / yt-dlp helpers) are now lazily imported
# to avoid UI lag when opening simple dialogs like Browse. They will be imported only
# when Run Automation is pressed.

# ---------------------------------------------------------------------------
# Helper: import create_folder (single definitive path). Provide fallback if import fails.
# ---------------------------------------------------------------------------
try:
    from core.downloadTool.folder_handle import create_folder  # type: ignore
except Exception:  # fallback simple implementation
    def create_folder(parent: str, name: str):
        os.makedirs(os.path.join(parent, name), exist_ok=True)

# ---------------------------------------------------------------------------
# Main GUI Class
# ---------------------------------------------------------------------------

class AutoToolGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoTool - Premiere Automation")
        self.geometry("680x470")
        self.resizable(False, False)

        # State variables
        self.parent_folder_var = tk.StringVar()
        self.project_file_var = tk.StringVar()
        self.version_var = tk.StringVar(value="2024")
        self.subfolder_var = tk.StringVar()
        self.download_type_var = tk.StringVar(value="mp4")  # mp4 or mp3
        self.links_folder_var = tk.StringVar()  # optional custom folder for links list
        self.regen_links_var = tk.BooleanVar(value=False)  # user override regen option (False = reuse if exists)

        self._build_ui()
        # Register global logging bridge so all prints from any module stream here
        try:
            from core import logging_bridge as _lb  # type: ignore
            _lb.register_gui_logger(self.log)
            if not _lb.is_active():  # activate once
                _lb.activate(mirror_to_console=True)
            self.log("[Logging] Global capture active.")
        except Exception as e:
            self.log(f"WARNING: Cannot activate logging bridge: {e}")
        self.log("Ready.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = 8
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        row = 0
        # Parent folder
        ttk.Label(frm, text="Parent Folder:").grid(row=row, column=0, sticky="w", padx=pad, pady=(pad, 2))
        ttk.Entry(frm, textvariable=self.parent_folder_var, width=52).grid(row=row, column=1, sticky="w", padx=pad, pady=(pad, 2))
        ttk.Button(frm, text="Browse", command=self.browse_parent).grid(row=row, column=2, padx=pad, pady=(pad, 2))

        row += 1
        # Project file
        ttk.Label(frm, text="Premiere Project (.prproj):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.project_file_var, width=52).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        ttk.Button(frm, text="Browse", command=self.browse_project).grid(row=row, column=2, padx=pad, pady=2)

        row += 1
        # Premiere version
        ttk.Label(frm, text="Premiere Version:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Combobox(frm, textvariable=self.version_var, values=["2022", "2023", "2024", "2025"], width=12, state="readonly").grid(row=row, column=1, sticky="w", padx=pad, pady=2)

        row += 1
        # Download type (radio buttons) – only one selectable
        ttk.Label(frm, text="Download Type:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        type_frame = ttk.Frame(frm)
        type_frame.grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        ttk.Radiobutton(type_frame, text="MP4", value="mp4", variable=self.download_type_var).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(type_frame, text="MP3", value="mp3", variable=self.download_type_var).pack(side="left")

        row += 1
        # Optional new subfolder
        ttk.Label(frm, text="New Subfolder (optional):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.subfolder_var, width=30).grid(row=row, column=1, sticky="w", padx=pad, pady=2)

        row += 1
        # Optional links output folder
        ttk.Label(frm, text="Links Output Folder (optional):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.links_folder_var, width=52).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        ttk.Button(frm, text="Browse", command=self.browse_links_folder).grid(row=row, column=2, padx=pad, pady=2)

        row += 1
        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=pad, pady=(12, 4))
        ttk.Button(btn_frame, text="Validate", command=self.validate_inputs).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Create Folder", command=self.create_subfolder).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Run Automation", command=self.run_automation).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Links Status", command=self.open_links_status_window).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Clear Log", command=self.clear_log).pack(side="left", padx=6)

        row += 1
        # Log area
        ttk.Label(frm, text="Log:").grid(row=row, column=0, sticky="nw", padx=pad, pady=(12, 2))
        self.log_text = tk.Text(frm, height=13, wrap="word")
        self.log_text.grid(row=row, column=1, columnspan=2, sticky="nsew", padx=pad, pady=(12, 2))
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=row, column=3, sticky="ns", pady=(12, 2))
        self.log_text.configure(yscrollcommand=scroll.set)

        frm.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Browse handlers
    # ------------------------------------------------------------------
    def browse_parent(self):
        start = time.time()
        path = filedialog.askdirectory(title="Select Parent Folder")
        elapsed = (time.time() - start) * 1000
        if path:
            self.parent_folder_var.set(path)
            self.log(f"Selected parent folder: {path} (dialog {elapsed:.1f} ms)")
        else:
            self.log(f"Browse cancelled (dialog {elapsed:.1f} ms)")

    def browse_project(self):
        f = filedialog.askopenfilename(title="Select Premiere Project", filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")])
        if f:
            self.project_file_var.set(f)
            self.log(f"Selected project file: {f}")

    def browse_links_folder(self):
        path = filedialog.askdirectory(title="Select Links Output Folder")
        if path:
            self.links_folder_var.set(path)
            self.log(f"Selected links output folder: {path}")

    # ------------------------------------------------------------------
    # Validation & folder ops
    # ------------------------------------------------------------------
    def validate_inputs(self):
        parent = self.parent_folder_var.get().strip()
        proj = self.project_file_var.get().strip()
        version = self.version_var.get().strip()
        dtype = self.download_type_var.get()

        ok = True
        if not parent:
            self.log("ERROR: Parent folder is empty.")
            ok = False
        elif not os.path.isdir(parent):
            self.log("WARNING: Parent folder does not exist (will be created if needed).")

        if not proj:
            self.log("ERROR: Project file path is empty.")
            ok = False
        elif not os.path.isfile(proj):
            self.log("ERROR: Project file not found.")
            ok = False
        elif not proj.lower().endswith(".prproj"):
            self.log("WARNING: File does not have .prproj extension.")

        self.log(f"Premiere version: {version}; Download type: {dtype}")
        if ok:
            self.log("Validation PASSED.")
            messagebox.showinfo("Validation", "Inputs are valid (or creatable).")
        else:
            messagebox.showerror("Validation", "Validation failed. See log.")

    def create_subfolder(self):
        parent = self.parent_folder_var.get().strip()
        sub = self.subfolder_var.get().strip()
        if not parent:
            self.log("ERROR: Parent folder empty.")
            return
        if not sub:
            self.log("ERROR: Subfolder name empty.")
            return
        try:
            if not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
                self.log(f"Created parent folder: {parent}")
            create_folder(parent, sub)
            self.log(f"Subfolder ensured: {os.path.join(parent, sub)}")
        except Exception as e:
            self.log(f"ERROR creating subfolder: {e}")

    # ------------------------------------------------------------------
    # Automation placeholder
    # ------------------------------------------------------------------
    def run_automation(self):
        parent = self.parent_folder_var.get().strip()
        proj = self.project_file_var.get().strip()
        version = self.version_var.get().strip()
        dtype = self.download_type_var.get()

        self.log("=== Automation Start ===")
        if not parent:
            self.log("ERROR: Parent folder empty.")
            return
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Created parent folder: {parent}")
            except Exception as e:
                self.log(f"ERROR: cannot create parent folder: {e}")
                return
        if not os.path.isfile(proj):
            self.log("ERROR: Project file missing. Abort.")
            return
        
        # Lazy import heavy modules only now to avoid initial GUI lag.
        # Try normal package path first, then fallback relative to root.
        try:
            # Prefer absolute import (root path already injected above)
            from ..core.downloadTool import get_name_list, down_by_yt, get_link  # type: ignore
        except Exception:
            # Fallback: import modules individually via importlib (helps in some packaged contexts)
            try:
                import importlib
                get_name_list = importlib.import_module("core.downloadTool.get_name_list")  # type: ignore
                down_by_yt = importlib.import_module("core.downloadTool.down_by_yt")  # type: ignore
                get_link = importlib.import_module("core.downloadTool.get_link")  # type: ignore
            except Exception as e:
                self.log(f"ERROR: Cannot import modules (core.downloadTool.*): {e}")
                return

        # Build absolute paths (PyInstaller aware: use _MEIPASS if present)
        # Base directory holding runtime resources (list_name, etc.)
        base_dir = getattr(sys, "_MEIPASS", _ROOT_DIR)
        # Xây dựng thư mục data riêng cho mỗi project (.prproj) dựa trên tên file
        safe_project = self._derive_project_slug(proj)
        data_project_dir = os.path.join(DATA_DIR, safe_project)
        if not os.path.isdir(data_project_dir):
            try:
                os.makedirs(data_project_dir, exist_ok=True)
                self.log(f"Created project data folder: {data_project_dir}")
            except Exception as e:
                self.log(f"ERROR: Cannot create project data folder ({e})")
                return
        names_txt = os.path.join(data_project_dir, "list_name.txt")
        # đảm bảo thư mục data gốc tồn tại (fallback)
        if not os.path.isdir(DATA_DIR):
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
            except Exception:
                self.log(f"WARNING: Cannot create base data folder: {DATA_DIR}")

        # Determine links output directory
        custom_links_dir = self.links_folder_var.get().strip()
        if custom_links_dir:
            links_dir = os.path.abspath(custom_links_dir.replace('/', os.sep))
            if not os.path.isdir(links_dir):
                try:
                    os.makedirs(links_dir, exist_ok=True)
                    self.log(f"Created links output folder: {links_dir}")
                except Exception as e:
                    self.log(f"WARNING: Cannot create links output folder ({e}); using default.")
                    links_dir = DATA_DIR
            else:
                self.log(f"Using custom links output folder: {links_dir}")
        else:
            links_dir = DATA_DIR
            self.log("Using default data folder for links output.")
        # Nếu người dùng không chọn custom links dir, ta dùng thư mục project trong data
        if links_dir == DATA_DIR:
            links_dir = data_project_dir
        links_txt = os.path.join(links_dir, "dl_links.txt")       # list of grouped links generated

        # 1. Extract names
        try:
            # Ghi marker cho ExtendScript (getTimeline / cutAndPush) biết subfolder đang dùng
            try:
                from core.project_data import write_current_project_marker  # type: ignore
                write_current_project_marker(safe_project)
                self.log(f"Set current project marker: {safe_project}")
            except Exception as _pmErr:
                self.log(f"WARNING: Cannot write project marker ({_pmErr})")
            get_name_list.extract_instance_names(proj, save_txt=names_txt, project_name=safe_project)
            self.log(f"Extracted instance names -> {names_txt}")
        except Exception as e:
            self.log(f"ERROR extracting names: {e}")
            return

        # 2. Generate links file if missing or stale (> 1h old)
        # Quyết định regen dựa trên override + tuổi file
        regen = True  # default if file missing
        force_flag = self.regen_links_var.get()
        if os.path.isfile(links_txt):
            if force_flag:  # người dùng ép regenerate
                self.log("User override: force regenerate links file.")
                regen = True
            elif force_flag is False:  # reuse nếu tồn tại
                self.log("User override: reuse existing links file (no regenerate).")
                regen = False
            else:
                # fallback logic theo tuổi
                mtime = os.path.getmtime(links_txt)
                age = time.time() - mtime
                if age < 3600:
                    regen = False
                    self.log(f"Links file exists and is recent ({age/60:.1f} min); skipping regeneration (auto logic).")
                else:
                    regen = True
                    self.log(f"Links file is stale ({age/60:.1f} min); regenerating (auto logic).")
        if regen:
            try:
                self.log("Generating YouTube links (may take a while)...")
                get_link.get_links_main(names_txt, links_txt, project_name=safe_project)
                self.log(f"Generated links -> {links_txt}")
            except Exception as e:
                self.log(f"WARNING: Could not generate links automatically ({e}). Using names file only.")
                links_txt = names_txt  # fallback (parse will create empty groups)
        else:
            self.log(f"Reusing existing links file -> {links_txt}")

        # 3. Run download logic (IMPORTANT: pass links file, not names file)
        try:
            down_by_yt.download_main(parent, links_txt, _type=dtype, project_name=safe_project)
            self.log("Download task completed.")
        except Exception as e:
            self.log(f"ERROR during download: {e}")
            return

        # Placeholder – integrate your real logic here (parse .prproj, download, etc.)
        self.log(f"Project: {proj}")
        self.log(f"Premiere version: {version}")
        self.log(f"Download type selected: {dtype}")
        # e.g. call: process_project(proj, download_type=dtype)
        self.log("Automation placeholder completed.")
        self.log("=== Automation End ===")

    # --------------------------------------------------------------
    # Helper: derive project slug (shared between main & status window)
    # --------------------------------------------------------------
    def _derive_project_slug(self, proj_path: str) -> str:
        project_filename = os.path.basename(proj_path)
        stem, _ = os.path.splitext(project_filename)
        return ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in stem)

    # --------------------------------------------------------------
    # Links status window
    # --------------------------------------------------------------
    def open_links_status_window(self):
        proj = self.project_file_var.get().strip()
        if not proj:
            self.log("ERROR: Select a .prproj first to inspect links.")
            return
        slug = self._derive_project_slug(proj)
        project_dir = os.path.join(DATA_DIR, slug)
        links_path = os.path.join(project_dir, 'dl_links.txt')
        names_path = os.path.join(project_dir, 'list_name.txt')
        groups, links = self._compute_links_stats(links_path)
        win = tk.Toplevel(self)
        win.title(f"Links Status - {slug}")
        win.geometry('420x260')
        win.resizable(False, False)

        pad = 8
        info_frame = ttk.Frame(win, padding=pad)
        info_frame.pack(fill='both', expand=True)

        ttk.Label(info_frame, text=f"Project slug: {slug}").grid(row=0, column=0, sticky='w', pady=(0,4))
        ttk.Label(info_frame, text=f"Project data dir:").grid(row=1, column=0, sticky='w')
        ttk.Label(info_frame, text=project_dir, foreground='#444').grid(row=2, column=0, sticky='w', pady=(0,6))

        if os.path.isfile(names_path):
            try:
                with open(names_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_names = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                raw_names = []
        else:
            raw_names = []

        ttk.Label(info_frame, text=f"Instance names file: {len(raw_names)} entries").grid(row=3, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Links file: {'FOUND' if os.path.isfile(links_path) else 'MISSING'}").grid(row=4, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Groups detected: {groups}").grid(row=5, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Total links: {links}").grid(row=6, column=0, sticky='w')

        ttk.Separator(info_frame, orient='horizontal').grid(row=7, column=0, sticky='ew', pady=6)

        regen_cb = ttk.Checkbutton(info_frame, text='Force regenerate links on next run', variable=self.regen_links_var)
        regen_cb.grid(row=8, column=0, sticky='w')
        ttk.Label(info_frame, text='(Unchecked = reuse if exists)').grid(row=9, column=0, sticky='w', pady=(0,4))

        btns = ttk.Frame(info_frame)
        btns.grid(row=10, column=0, sticky='e', pady=(10,0))
        ttk.Button(btns, text='Refresh', command=lambda: self._refresh_links_window(win, project_dir, links_path, names_path)).pack(side='left', padx=(0,6))
        ttk.Button(btns, text='Close', command=win.destroy).pack(side='left')

    def _refresh_links_window(self, win, project_dir, links_path, names_path):
        # Destroy and rebuild window content
        try:
            for child in win.winfo_children():
                child.destroy()
        except Exception:
            return
        groups, links = self._compute_links_stats(links_path)
        try:
            with open(names_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_names = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            raw_names = []
        pad=8
        info_frame = ttk.Frame(win, padding=pad)
        info_frame.pack(fill='both', expand=True)
        slug = os.path.basename(project_dir)
        ttk.Label(info_frame, text=f"Project slug: {slug}").grid(row=0, column=0, sticky='w', pady=(0,4))
        ttk.Label(info_frame, text=f"Project data dir:").grid(row=1, column=0, sticky='w')
        ttk.Label(info_frame, text=project_dir, foreground='#444').grid(row=2, column=0, sticky='w', pady=(0,6))
        ttk.Label(info_frame, text=f"Instance names file: {len(raw_names)} entries").grid(row=3, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Links file: {'FOUND' if os.path.isfile(links_path) else 'MISSING'}").grid(row=4, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Groups detected: {groups}").grid(row=5, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Total links: {links}").grid(row=6, column=0, sticky='w')
        ttk.Separator(info_frame, orient='horizontal').grid(row=7, column=0, sticky='ew', pady=6)
        regen_cb = ttk.Checkbutton(info_frame, text='Force regenerate links on next run', variable=self.regen_links_var)
        regen_cb.grid(row=8, column=0, sticky='w')
        ttk.Label(info_frame, text='(Unchecked = reuse if exists)').grid(row=9, column=0, sticky='w', pady=(0,4))
        btns = ttk.Frame(info_frame)
        btns.grid(row=10, column=0, sticky='e', pady=(10,0))
        ttk.Button(btns, text='Refresh', command=lambda: self._refresh_links_window(win, project_dir, links_path, names_path)).pack(side='left', padx=(0,6))
        ttk.Button(btns, text='Close', command=win.destroy).pack(side='left')

    def _compute_links_stats(self, links_path: str):
        groups = 0
        total_links = 0
        if not os.path.isfile(links_path):
            return groups, total_links
        try:
            with open(links_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    if s.startswith('http://') or s.startswith('https://'):
                        total_links += 1
                    else:
                        groups += 1
        except Exception:
            pass
        return groups, total_links

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():  # pragma: no cover - manual GUI run
    app = AutoToolGUI()
    app.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
