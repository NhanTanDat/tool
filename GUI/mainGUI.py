import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

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

# Path to persisted config file
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')

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
        self.title("AutoTool - Tự động hoá Premiere")
        self.geometry("900x650")
        self.resizable(False, False)

        self.version_var = tk.StringVar(value="2022")
        self.download_type_var = tk.StringVar(value="mp4")
        self.mode_var = tk.StringVar(value="both")  # both | video | image
        self.regen_links_var = tk.BooleanVar(value=False)
        self.videos_per_keyword_var = tk.StringVar(value="10")
        self.images_per_keyword_var = tk.StringVar(value="10")
        self.max_duration_var = tk.StringVar(value="20")  # mặc định tối đa 20 phút
        self.min_duration_var = tk.StringVar(value="4")   # mặc định tối thiểu 4 phút
        # Batch projects list
        self.batch_projects: list[str] = []
        self.premier_projects: list[str] = []

        # Prevent saving while loading initial config
        self._loading_config = True

        # Load previous config (if any) before building UI so variables are pre-populated
        try:
            self._load_config()
        except Exception:
            pass

        self._build_ui()

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
        try:
            from core import logging_bridge as _lb  # type: ignore
            _lb.register_gui_logger(self.log)
            if not _lb.is_active():
                _lb.activate(mirror_to_console=True)
            self.log("[Logging] Bắt đầu ghi log toàn cục.")
        except Exception as e:
            self.log(f"CẢNH BÁO: Không kích hoạt được logging bridge: {e}")
        self.log("Sẵn sàng.")

    def _build_ui(self):
        pad = 8

        # Create notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Tab 1: Automation (current content)
        tab1 = ttk.Frame(notebook, padding=10)
        notebook.add(tab1, text="Auto Download")

        main_frame = ttk.Frame(tab1, padding=10)
        main_frame.pack(fill="both", expand=True)

        # ------------------------------------------------------------------
        style = ttk.Style()
        style.configure(
            "Custom.TButton",
            font=("Segoe UI", 10, "bold")
        )

        # Main content - Project selection and configuration
        frm = ttk.Frame(main_frame, padding=10, relief="groove")
        frm.pack(fill="both", expand=True)
        row = 0
        # Project selection section
        ttk.Label(frm, text="Chọn file (.prproj):", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=pad, pady=(pad, 2))
        row += 1
        ttk.Button(frm, text="Thêm file...", command=self.add_batch_projects).grid(row=row, column=0, sticky="w", padx=pad, pady=(2, 2))
        ttk.Button(frm, text="Xoá đã chọn", command=self.remove_selected_batch).grid(row=row, column=1, sticky="w", padx=pad, pady=(2, 2))
        row += 1
        self.batch_list = tk.Listbox(frm, height=8, selectmode="extended")
        self.batch_list.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=pad, pady=(2, 6))
        bscroll = ttk.Scrollbar(frm, orient="vertical", command=self.batch_list.yview)
        bscroll.grid(row=row, column=2, sticky="ns", pady=(2, 6))
        self.batch_list.configure(yscrollcommand=bscroll.set)
        frm.columnconfigure(0, weight=1)
        row += 1

        # Configuration section
        ttk.Label(frm, text="Cấu hình:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=pad, pady=(8, 4))
        row += 1
        ttk.Label(frm, text="Phiên bản Premiere:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Combobox(frm, textvariable=self.version_var, values=["2022", "2023", "2024", "2025"], width=12, state="readonly").grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Số video / từ khoá:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.videos_per_keyword_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Thời lượng tối đa (phút):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.max_duration_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Thời lượng tối thiểu (phút):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.min_duration_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        row += 1
        ttk.Label(frm, text="Số ảnh / từ khoá:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.images_per_keyword_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Chế độ chạy:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Combobox(frm, textvariable=self.mode_var, values=["both", "video", "image"], width=12, state="readonly").grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        # Regen links checkbox
        ttk.Checkbutton(frm, text='Ép tạo lại link lần chạy sau', variable=self.regen_links_var).grid(row=row, column=0, sticky='w', padx=pad, pady=(2,0))
        row += 1

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=pad, pady=(12, 4))
        ttk.Button(btn_frame, text="Kiểm tra", command=self.validate_inputs).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Chạy Auto download", style="Custom.TButton", command=self.run_batch_automation).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Trạng thái link", command=self.open_links_status_window).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Xoá log", command=self.clear_log).pack(side="left", padx=6)
        row += 1

        # Log section
        ttk.Label(frm, text="Nhật ký:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="nw", padx=pad, pady=(12, 2))
        self.log_text = tk.Text(frm, height=10, wrap="word")
        self.log_text.grid(row=row, column=1, columnspan=2, sticky="nsew", padx=pad, pady=(12, 2))
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=row, column=3, sticky="ns", pady=(12, 2))
        self.log_text.configure(yscrollcommand=scroll.set)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(row, weight=1)

        # Tab 2: Auto Premier
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab2, text="Auto Premier")

        main_frame2 = ttk.Frame(tab2, padding=10)
        main_frame2.pack(fill="both", expand=True)

        frm2 = ttk.Frame(main_frame2, padding=10, relief="groove")
        frm2.pack(fill="both", expand=True)
        row2 = 0
        # Project selection section
        ttk.Label(frm2, text="Chọn file (.prproj) để auto:", font=("Segoe UI", 10, "bold")).grid(row=row2, column=0, sticky="w", padx=pad, pady=(pad, 2))
        row2 += 1
        ttk.Button(frm2, text="Thêm file...", command=self.add_premier_projects).grid(row=row2, column=0, sticky="w", padx=pad, pady=(2, 2))
        ttk.Button(frm2, text="Xoá đã chọn", command=self.remove_selected_premier).grid(row=row2, column=1, sticky="w", padx=pad, pady=(2, 2))
        row2 += 1
        self.premier_list = tk.Listbox(frm2, height=8, selectmode="extended")
        self.premier_list.grid(row=row2, column=0, columnspan=2, sticky="nsew", padx=pad, pady=(2, 6))
        pscroll = ttk.Scrollbar(frm2, orient="vertical", command=self.premier_list.yview)
        pscroll.grid(row=row2, column=2, sticky="ns", pady=(2, 6))
        self.premier_list.configure(yscrollcommand=pscroll.set)
        frm2.columnconfigure(0, weight=1)
        row2 += 1

        # Buttons
        btn_frame2 = ttk.Frame(frm2)
        btn_frame2.grid(row=row2, column=0, columnspan=3, sticky="w", padx=pad, pady=(12, 4))
        ttk.Button(btn_frame2, text="Lấy từ tab Download", command=self.copy_from_automation).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame2, text="Chạy Auto Premier", style="Custom.TButton", command=self.run_premier_automation).pack(side="left", padx=6)
        ttk.Button(btn_frame2, text="Xoá log", command=self.clear_log2).pack(side="left", padx=6)
        row2 += 1

        # Log section (shared with tab1)
        ttk.Label(frm2, text="Nhật ký:", font=("Segoe UI", 10, "bold")).grid(row=row2, column=0, sticky="nw", padx=pad, pady=(12, 2))
        self.log_text2 = tk.Text(frm2, height=10, wrap="word")
        self.log_text2.grid(row=row2, column=1, columnspan=2, sticky="nsew", padx=pad, pady=(12, 2))
        scroll2 = ttk.Scrollbar(frm2, orient="vertical", command=self.log_text2.yview)
        scroll2.grid(row=row2, column=3, sticky="ns", pady=(12, 2))
        self.log_text2.configure(yscrollcommand=scroll2.set)
        frm2.columnconfigure(1, weight=1)
        frm2.rowconfigure(row2, weight=1)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def log2(self, msg: str):
        self.log_text2.insert("end", msg + "\n")
        self.log_text2.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def clear_log2(self):
        self.log_text2.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Validation & folder ops
    # ------------------------------------------------------------------
    def validate_inputs(self):
        version = self.version_var.get().strip()
        mode = self.mode_var.get().strip()

        ok = True
        if not self.batch_projects:
            self.log("LỖI: Chưa chọn file .prproj nào.")
            ok = False
        else:
            # Validate each project file
            invalid_projects = []
            for proj in self.batch_projects:
                if not os.path.isfile(proj):
                    invalid_projects.append(proj)
                elif not proj.lower().endswith(".prproj"):
                    self.log(f"CẢNH BÁO: File không có đuôi .prproj: {proj}")
            
            if invalid_projects:
                self.log(f"LỖI: Không tìm thấy file project: {', '.join(invalid_projects)}")
                ok = False

        self.log(f"Phiên bản Premiere: {version}; Chế độ: {mode}; Số project: {len(self.batch_projects) if self.batch_projects else 0}")
        if ok:
            self.log("Kiểm tra hợp lệ.")
            messagebox.showinfo("Kiểm tra", "Thông tin hợp lệ (có thể tạo).")
        else:
            messagebox.showerror("Kiểm tra", "Không hợp lệ. Xem log.")

    # (Đã loại bỏ input 'Thư mục con' và nút tạo thư mục)

    # ------------------------------------------------------------------
    # Automation placeholder
    # ------------------------------------------------------------------
    def run_automation_for_project(self, proj_path: str):
        # Set up resource folder for this project
        proj_dir = os.path.dirname(os.path.abspath(proj_path))
        parent = os.path.join(proj_dir, 'resource')
        
        version = self.version_var.get().strip()
        dtype = self.download_type_var.get()
        mode = self.mode_var.get().strip()
        
        self.log("=== BẮT ĐẦU TỰ ĐỘNG ===")
        
        # Create resource directory if it doesn't exist
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục cha: {e}")
                return
        
        if not os.path.isfile(proj_path):
            self.log("LỖI: Thiếu file project. Dừng.")
            return
        
        # Lazy import heavy modules only now to avoid initial GUI lag.
        try:
            from ..core.downloadTool import get_name_list, down_by_yt, get_link  # type: ignore
        except Exception:
            try:
                import importlib
                get_name_list = importlib.import_module("core.downloadTool.get_name_list")  # type: ignore
                down_by_yt = importlib.import_module("core.downloadTool.down_by_yt")  # type: ignore
                get_link = importlib.import_module("core.downloadTool.get_link")  # type: ignore
            except Exception as e:
                self.log(f"ERROR: Cannot import modules (core.downloadTool.*): {e}")
                return

        # Build absolute paths (PyInstaller aware: use _MEIPASS if present)
        base_dir = getattr(sys, "_MEIPASS", _ROOT_DIR)  # noqa: F841 (reserved for future use)
        # Xây dựng thư mục data riêng cho mỗi project (.prproj) dựa trên tên file
        safe_project = self._derive_project_slug(proj_path)
        data_project_dir = os.path.join(DATA_DIR, safe_project)
        if not os.path.isdir(data_project_dir):
            try:
                os.makedirs(data_project_dir, exist_ok=True)
                self.log(f"Đã tạo thư mục dữ liệu project: {data_project_dir}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục dữ liệu project ({e})")
                return
        names_txt = os.path.join(data_project_dir, "list_name.txt")
        # đảm bảo thư mục data gốc tồn tại (fallback)
        if not os.path.isdir(DATA_DIR):
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
            except Exception:
                self.log(f"CẢNH BÁO: Không tạo được thư mục data gốc: {DATA_DIR}")

        # Thư mục lưu link: luôn dùng thư mục project trong data
        links_dir = data_project_dir
        self.log(f"Thư mục lưu link: {links_dir}")
        links_txt = os.path.join(links_dir, "dl_links.txt")       # list of grouped video links
        links_img_txt = os.path.join(links_dir, "dl_links_image.txt")  # list of grouped image links

        # 1. Extract names
        try:
            # Ghi marker cho ExtendScript (getTimeline / cutAndPush) biết subfolder đang dùng
            try:
                from core.project_data import write_current_project_marker  # type: ignore
                write_current_project_marker(safe_project)
                self.log(f"Đánh dấu project hiện tại: {safe_project}")
            except Exception as _pmErr:
                self.log(f"CẢNH BÁO: Không ghi được marker project ({_pmErr})")
            get_name_list.extract_instance_names(proj_path, save_txt=names_txt, project_name=safe_project)
            self.log(f"Đã trích tên instance -> {names_txt}")
        except Exception as e:
            self.log(f"LỖI khi trích tên: {e}")
            return

        # 2. Generate links file if missing or stale (> 1h old)
        # Quyết định regen dựa trên override + tuổi file
        # Tạo link theo chế độ đã chọn
        try:
            # Read parameters
            try:
                mpk = int(self.videos_per_keyword_var.get().strip() or '10')
            except Exception:
                mpk = 10
            try:
                mx_max = int(self.max_duration_var.get().strip() or '20')
            except Exception:
                mx_max = 20
            try:
                mn_min = int(self.min_duration_var.get().strip() or '4')
            except Exception:
                mn_min = 4
            max_minutes = mx_max if mx_max > 0 else None
            min_minutes = mn_min if mn_min > 0 else None
            try:
                ipk = int(self.images_per_keyword_var.get().strip() or '10')
            except Exception:
                ipk = 10

            force_flag = self.regen_links_var.get()
            mode_l = mode.lower()
            if mode_l == 'both':
                self.log("Đang tạo link (cả VIDEO và ẢNH)...")
                get_link.get_links_main(
                    names_txt,
                    links_txt,
                    project_name=safe_project,
                    max_per_keyword=mpk,
                    max_minutes=max_minutes,
                    min_minutes=min_minutes,
                    images_per_keyword=ipk,
                )
                self.log(f"Đã tạo link VIDEO -> {links_txt}")
                self.log(f"Đã tạo link ẢNH -> {links_img_txt}")
            elif mode_l == 'video':
                do_regen = True
                if os.path.isfile(links_txt) and force_flag is False:
                    do_regen = False
                    self.log("Giữ lại link VIDEO hiện có (user chọn)")
                if do_regen:
                    self.log("Đang tạo link VIDEO...")
                    get_link.get_links_main_video(
                        names_txt,
                        links_txt,
                        project_name=safe_project,
                        max_per_keyword=mpk,
                        max_minutes=max_minutes,
                        min_minutes=min_minutes,
                    )
            elif mode_l == 'image':
                do_regen = True
                if os.path.isfile(links_img_txt) and force_flag is False:
                    do_regen = False
                    self.log("Giữ lại link ẢNH hiện có (user chọn)")
                if do_regen:
                    self.log("Đang tạo link ẢNH...")
                    get_link.get_links_main_image(
                        names_txt,
                        links_img_txt,
                        project_name=safe_project,
                        images_per_keyword=ipk,
                    )
        except Exception as e:
            self.log(f"CẢNH BÁO: Không tạo được link ({e}).")

        # 3. Run download logic theo chế độ
        mode_l = mode.lower()
        if mode_l in ('both', 'video'):
            try:
                down_by_yt.download_main(parent, links_txt, _type=dtype)
                self.log("Tải VIDEO xong.")
            except Exception as e:
                self.log(f"LỖI khi tải VIDEO: {e}")
                return
        if mode_l in ('both', 'image'):
            # Import downImage lazily to download images
            try:
                import importlib
                down_image = importlib.import_module("core.downloadTool.downImage")
            except Exception as e:
                self.log(f"LỖI: Không thể import downImage: {e}")
                return
            try:
                attempted = down_image.download_images_main(parent, links_img_txt)
                self.log(f"Đã gửi tải {attempted} ảnh. Xem kết quả trong các thư mục *_img tại: {parent}")
            except Exception as e:
                self.log(f"LỖI khi tải ẢNH: {e}")
                return

        # Nhật ký tổng kết
        self.log(f"Project: {proj_path}")
        self.log(f"Phiên bản Premiere: {version}")
        self.log(f"Định dạng tải: {dtype}")
        self.log("Hoàn tất quy trình.")
        self.log("=== KẾT THÚC TỰ ĐỘNG ===")

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------
    def add_batch_projects(self):
        files = filedialog.askopenfilenames(title="Chọn nhiều file .prproj", filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")])
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
                # Run automation for each project with its own resource folder
                self.run_automation_for_project(proj_path)
                self.update()
            except Exception as e:
                self.log(f"LỖI batch item: {e}")
        self.log("=== KẾT THÚC CHẠY HÀNG LOẠT ===")
        try:
            self._save_config()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Premier helpers
    # ------------------------------------------------------------------
    def add_premier_projects(self):
        files = filedialog.askopenfilenames(title="Chọn nhiều file .prproj", filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")])
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
        self.log2(f"Đã sao chép {len(self.premier_projects)} project từ tab Automation.")

    def run_premier_automation(self):
        try:
            import importlib
            from core.premierCore.control import run_premier_script  # type: ignore
        except Exception:
            try:
                import importlib
                run_premier_script = importlib.import_module("core.premierCore.control").run_premier_script  # type: ignore
            except Exception as e:
                self.log2(f"LỖI: Không thể import run_premier_script: {e}")
                run_premier_script = None
        if not self.premier_projects:
            messagebox.showwarning("Premier", "Chưa có file .prproj nào trong danh sách.")
            return
        if run_premier_script is None:
            self.log2("LỖI: Không thể import run_premier_script từ control.py")
            return
        self.log2(f"=== BẮT ĐẦU CHẠY PREMIER AUTOMATION ({len(self.premier_projects)} project) ===")
        num = 0
        for i, proj_path in enumerate(self.premier_projects, start=1):
            try:
                self.log2(f"-- ({i}/{len(self.premier_projects)}) {proj_path}")
                # Update path.txt
                project_slug = self._derive_project_slug(proj_path)
                data_folder = os.path.join(DATA_DIR, project_slug).replace('\\', '/')
                project_path_unix = proj_path.replace('\\', '/')
                resource_dir = os.path.join(os.path.dirname(proj_path), 'resource').replace('\\', '/')
                path_txt_content = f"project_slug={project_slug}\ndata_folder={data_folder}\nproject_path={project_path_unix}\nresource_dir={resource_dir}\n"
                path_txt_path = os.path.join(DATA_DIR, 'path.txt')
                try:
                    with open(path_txt_path, 'w', encoding='utf-8') as f:
                        f.write(path_txt_content)
                    self.log2(f"Đã cập nhật path.txt cho {project_slug}")
                except Exception as e:
                    self.log2(f"LỖI khi ghi path.txt: {e}")
                    continue
                # Run premier script
                proj_path = '\"' + proj_path.replace('/', '\\') + '\"'  # ensure backslashes for Windows paths
                num += 1
                run_premier_script(None, proj_path, num)
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

    def run_download_images(self):
        if not self.batch_projects:
            self.log("LỖI: Chưa chọn file .prproj nào.")
            return
        
        # Use the first project in the batch list
        proj = self.batch_projects[0]
        proj_dir = os.path.dirname(os.path.abspath(proj))
        parent = os.path.join(proj_dir, 'resource')
        
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục cha: {e}")
                return
        
        safe_project = self._derive_project_slug(proj)
        links_dir = os.path.join(DATA_DIR, safe_project)
        links_img_txt = os.path.join(links_dir, "dl_links_image.txt")
        if not os.path.isfile(links_img_txt):
            self.log(f"LỖI: Không tìm thấy file link ảnh: {links_img_txt}")
            self.log("Hãy chạy 'Chạy tự động' để tạo link trước hoặc kiểm tra thư mục link tuỳ chọn.")
            return
        # Import downImage lazily
        try:
            import importlib
            down_image = importlib.import_module("core.downloadTool.downImage")
        except Exception as e:
            self.log(f"LỖI: Không thể import downImage: {e}")
            return
        try:
            attempted = down_image.download_images_main(parent, links_img_txt)
            self.log(f"Đã gửi tải {attempted} ảnh. Xem kết quả trong các thư mục *_img tại: {parent}")
        except Exception as e:
            self.log(f"LỖI khi tải ảnh: {e}")
        # Save config after operation
        try:
            self._save_config()
        except Exception:
            pass

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
            self.log("LỖI: Chọn file .prproj trước khi xem link.")
            return
        slug = self._derive_project_slug(proj)
        project_dir = os.path.join(DATA_DIR, slug)
        links_path = os.path.join(project_dir, 'dl_links.txt')
        names_path = os.path.join(project_dir, 'list_name.txt')
        groups, links = self._compute_links_stats(links_path)

        win = tk.Toplevel(self)
        win.title(f"Trạng thái Link - {slug}")
        win.geometry('420x260')
        win.resizable(False, False)

        pad = 8
        info_frame = ttk.Frame(win, padding=pad)
        info_frame.pack(fill='both', expand=True)

        ttk.Label(info_frame, text=f"Mã project: {slug}").grid(row=0, column=0, sticky='w', pady=(0,4))
        ttk.Label(info_frame, text="Thư mục dữ liệu project:").grid(row=1, column=0, sticky='w')
        ttk.Label(info_frame, text=project_dir, foreground='#444').grid(row=2, column=0, sticky='w', pady=(0,6))

        if os.path.isfile(names_path):
            try:
                with open(names_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_names = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                raw_names = []
        else:
            raw_names = []

        ttk.Label(info_frame, text=f"File tên instance: {len(raw_names)} dòng").grid(row=3, column=0, sticky='w')
        ttk.Label(info_frame, text=f"File link: {'TÌM THẤY' if os.path.isfile(links_path) else 'THIẾU'}").grid(row=4, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Số nhóm: {groups}").grid(row=5, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Tổng link: {links}").grid(row=6, column=0, sticky='w')

        ttk.Separator(info_frame, orient='horizontal').grid(row=7, column=0, sticky='ew', pady=6)

        btns = ttk.Frame(info_frame)
        btns.grid(row=8, column=0, sticky='e', pady=(10,0))
        ttk.Button(btns, text='Làm mới', command=lambda: self._refresh_links_window(win, project_dir, links_path, names_path)).pack(side='left', padx=(0,6))
        ttk.Button(btns, text='Đóng', command=win.destroy).pack(side='left')

    def _refresh_links_window(self, win, project_dir, links_path, names_path):
        # Làm mới nội dung cửa sổ trạng thái link
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
        pad = 8
        info_frame = ttk.Frame(win, padding=pad)
        info_frame.pack(fill='both', expand=True)
        slug = os.path.basename(project_dir)
        ttk.Label(info_frame, text=f"Mã project: {slug}").grid(row=0, column=0, sticky='w', pady=(0,4))
        ttk.Label(info_frame, text="Thư mục dữ liệu project:").grid(row=1, column=0, sticky='w')
        ttk.Label(info_frame, text=project_dir, foreground='#444').grid(row=2, column=0, sticky='w', pady=(0,6))
        ttk.Label(info_frame, text=f"File tên instance: {len(raw_names)} dòng").grid(row=3, column=0, sticky='w')
        ttk.Label(info_frame, text=f"File link: {'TÌM THẤY' if os.path.isfile(links_path) else 'THIẾU'}").grid(row=4, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Số nhóm: {groups}").grid(row=5, column=0, sticky='w')
        ttk.Label(info_frame, text=f"Tổng link: {links}").grid(row=6, column=0, sticky='w')
        ttk.Separator(info_frame, orient='horizontal').grid(row=7, column=0, sticky='ew', pady=6)
        btns = ttk.Frame(info_frame)
        btns.grid(row=8, column=0, sticky='e', pady=(10,0))
        ttk.Button(btns, text='Làm mới', command=lambda: self._refresh_links_window(win, project_dir, links_path, names_path)).pack(side='left', padx=(0,6))
        ttk.Button(btns, text='Đóng', command=win.destroy).pack(side='left')

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

    # --------------------------------------------------------------
    # Config persistence helpers
    # --------------------------------------------------------------
    def _save_config(self):
        try:
            cfg = {
                'version': self.version_var.get().strip(),
                'mode': self.mode_var.get().strip(),
                'videos_per_keyword': self.videos_per_keyword_var.get().strip(),
                'images_per_keyword': self.images_per_keyword_var.get().strip(),
                'max_duration': self.max_duration_var.get().strip(),
                'min_duration': self.min_duration_var.get().strip(),
                'regen_links': bool(self.regen_links_var.get()),
                'batch_projects': list(self.batch_projects) if isinstance(self.batch_projects, list) else [],
                'premier_projects': list(self.premier_projects) if isinstance(self.premier_projects, list) else [],
            }
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            # Non-fatal: ignore write errors, optionally log
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
        # Apply values to variables (ignore missing keys)
        try:
            if 'version' in cfg:
                self.version_var.set(str(cfg['version']))
            if 'mode' in cfg:
                self.mode_var.set(str(cfg['mode']))
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
        # Skip saving while loading initial config
        if getattr(self, '_loading_config', False):
            return
        try:
            self._save_config()
        except Exception:
            pass

    def _bind_config_traces(self):
        # Bind variable write events to auto-save config
        vars_to_bind = [
            self.version_var,
            self.mode_var,
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
                    v.trace('w', self._on_var_change)  # Tk < 8.6 fallback
                except Exception:
                    pass

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():  # pragma: no cover - manual GUI run
    app = AutoToolGUI()
    app.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
