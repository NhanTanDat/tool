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
        tool_dir = os.path.join(base_dir, "core", "downloadTool")
        names_txt = os.path.join(tool_dir, "list_name.txt")      # list of names extracted from prproj
        # Ensure tool_dir exists (PyInstaller may bundle differently)
        if not os.path.isdir(tool_dir):
            try:
                os.makedirs(tool_dir, exist_ok=True)
            except Exception:
                pass

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
                    links_dir = tool_dir
            else:
                self.log(f"Using custom links output folder: {links_dir}")
        else:
            links_dir = tool_dir
            self.log("Using default internal folder for links output.")
        links_txt = os.path.join(links_dir, "dl_links.txt")       # list of grouped links generated

        # 1. Extract names
        try:
            get_name_list.extract_instance_names(proj, save_txt=names_txt)
            self.log(f"Extracted instance names -> {names_txt}")
        except Exception as e:
            self.log(f"ERROR extracting names: {e}")
            return

        # 2. Generate links file if missing or stale (> 1h old)
        regen = False
        if not os.path.isfile(links_txt):
            regen = True
        else:
            age = time.time() - os.path.getmtime(links_txt)
            if age > 3600:  # older than 1 hour
                regen = True
        if regen:
            try:
                self.log("Generating YouTube links (may take a while)...")
                get_link.get_links_main(names_txt, links_txt)
                self.log(f"Generated links -> {links_txt}")
            except Exception as e:
                self.log(f"WARNING: Could not generate links automatically ({e}). Using names file only.")
                links_txt = names_txt  # fallback (parse will create empty groups)
        else:
            self.log(f"Reusing existing links file -> {links_txt}")

        # 3. Run download logic (IMPORTANT: pass links file, not names file)
        try:
            down_by_yt.download_main(parent, links_txt, _type=dtype)
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

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():  # pragma: no cover - manual GUI run
    app = AutoToolGUI()
    app.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
