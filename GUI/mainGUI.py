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
        self.title("AutoTool - Tự động hoá Premiere")
        self.geometry("720x520")
        self.resizable(False, False)

        self.parent_folder_var = tk.StringVar()
        self.project_file_var = tk.StringVar()
        self.version_var = tk.StringVar(value="2024")
        self.download_type_var = tk.StringVar(value="mp4")
        self.mode_var = tk.StringVar(value="both")  # both | video | image
        self.regen_links_var = tk.BooleanVar(value=False)
        self.videos_per_keyword_var = tk.StringVar(value="10")
        self.images_per_keyword_var = tk.StringVar(value="10")
        self.max_duration_var = tk.StringVar(value="20")  # mặc định tối đa 20 phút
        self.min_duration_var = tk.StringVar(value="4")   # mặc định tối thiểu 4 phút

        self._build_ui()
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
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        row = 0
        # Đưa chọn file .prproj lên đầu
        ttk.Label(frm, text="File Premiere (.prproj):").grid(row=row, column=0, sticky="w", padx=pad, pady=(pad, 2))
        ttk.Entry(frm, textvariable=self.project_file_var, width=54).grid(row=row, column=1, sticky="w", padx=pad, pady=(pad, 2))
        ttk.Button(frm, text="Chọn", command=self.browse_project).grid(row=row, column=2, padx=pad, pady=(pad, 2))
        row += 1
        ttk.Label(frm, text="Thư mục chứa nội dung (video/ảnh):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.parent_folder_var, width=54).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        ttk.Button(frm, text="Chọn", command=self.browse_parent).grid(row=row, column=2, padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Phiên bản Premiere:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Combobox(frm, textvariable=self.version_var, values=["2022", "2023", "2024", "2025"], width=12, state="readonly").grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Chế độ chạy:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Combobox(frm, textvariable=self.mode_var, values=["both", "video", "image"], width=12, state="readonly").grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Số video / từ khoá:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.videos_per_keyword_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Số ảnh / từ khoá:").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.images_per_keyword_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Thời lượng tối đa (phút):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.max_duration_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        ttk.Label(frm, text="Thời lượng tối thiểu (phút):").grid(row=row, column=0, sticky="w", padx=pad, pady=2)
        ttk.Entry(frm, textvariable=self.min_duration_var, width=12).grid(row=row, column=1, sticky="w", padx=pad, pady=2)
        row += 1
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=pad, pady=(12, 4))
        ttk.Button(btn_frame, text="Kiểm tra", command=self.validate_inputs).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Chạy tự động", command=self.run_automation).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Download Image", command=self.run_download_images).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Trạng thái link", command=self.open_links_status_window).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Xoá log", command=self.clear_log).pack(side="left", padx=6)
        row += 1
        ttk.Label(frm, text="Nhật ký:").grid(row=row, column=0, sticky="nw", padx=pad, pady=(12, 2))
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
            # Đặt mặc định thư mục chứa nội dung = <thư mục .prproj>/resource nếu người dùng chưa chọn
            proj_dir = os.path.dirname(os.path.abspath(f))
            resource_dir = os.path.join(proj_dir, 'resource')
            try:
                os.makedirs(resource_dir, exist_ok=True)
                self.log(f"Đảm bảo thư mục resource: {resource_dir}")
            except Exception as e:
                self.log(f"CẢNH BÁO: Không tạo được thư mục resource mặc định ({e})")
            self.parent_folder_var.set(resource_dir)

    # (Đã loại bỏ input 'Thư mục lưu link')

    # ------------------------------------------------------------------
    # Validation & folder ops
    # ------------------------------------------------------------------
    def validate_inputs(self):
        parent = self.parent_folder_var.get().strip()
        proj = self.project_file_var.get().strip()
        version = self.version_var.get().strip()
        dtype = self.download_type_var.get()
        mode = (self.mode_var.get().strip() if hasattr(self, 'mode_var') else 'both')

        ok = True
        if not parent:
            self.log("LỖI: Chưa nhập thư mục chứa video.")
            ok = False
        elif not os.path.isdir(parent):
            self.log("CẢNH BÁO: Thư mục chứa video chưa tồn tại (sẽ tạo nếu cần).")

        if not proj:
            self.log("LỖI: Chưa nhập đường dẫn file project.")
            ok = False
        elif not os.path.isfile(proj):
            self.log("LỖI: Không tìm thấy file project.")
            ok = False
        elif not proj.lower().endswith(".prproj"):
            self.log("CẢNH BÁO: File không có đuôi .prproj.")

        self.log(f"Phiên bản Premiere: {version}; Kiểu tải: {dtype}; Chế độ: {mode}")
        if ok:
            self.log("Kiểm tra hợp lệ.")
            messagebox.showinfo("Kiểm tra", "Thông tin hợp lệ (có thể tạo).")
        else:
            messagebox.showerror("Kiểm tra", "Không hợp lệ. Xem log.")

    # (Đã loại bỏ input 'Thư mục con' và nút tạo thư mục)

    # ------------------------------------------------------------------
    # Automation placeholder
    # ------------------------------------------------------------------
    def run_automation(self):
        parent = self.parent_folder_var.get().strip()
        proj = self.project_file_var.get().strip()
        version = self.version_var.get().strip()
        dtype = self.download_type_var.get()
        mode = (self.mode_var.get().strip() if hasattr(self, 'mode_var') else 'both')
        self.log("=== BẮT ĐẦU TỰ ĐỘNG ===")
        # Nếu chưa có parent, mặc định = <thư mục .prproj>/resource và tạo mới nếu cần
        if not parent:
            if not proj:
                self.log("LỖI: Chưa nhập thư mục chứa nội dung và chưa chọn file project.")
                return
            proj_dir = os.path.dirname(os.path.abspath(proj))
            parent = os.path.join(proj_dir, 'resource')
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Dùng mặc định thư mục nội dung: {parent}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục mặc định: {e}")
                return
            self.parent_folder_var.set(parent)
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục cha: {e}")
                return
        if not os.path.isfile(proj):
            self.log("LỖI: Thiếu file project. Dừng.")
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
        base_dir = getattr(sys, "_MEIPASS", _ROOT_DIR)  # noqa: F841 (reserved for future use)
        # Xây dựng thư mục data riêng cho mỗi project (.prproj) dựa trên tên file
        safe_project = self._derive_project_slug(proj)
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
            get_name_list.extract_instance_names(proj, save_txt=names_txt, project_name=safe_project)
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
                mpk = int(getattr(self, 'videos_per_keyword_var', tk.StringVar(value='10')).get().strip() or '10')
            except Exception:
                mpk = 10
            try:
                mx_max = int(getattr(self, 'max_duration_var', tk.StringVar(value='20')).get().strip() or '20')
            except Exception:
                mx_max = 20
            try:
                mn_min = int(getattr(self, 'min_duration_var', tk.StringVar(value='4')).get().strip() or '4')
            except Exception:
                mn_min = 4
            max_minutes = mx_max if mx_max > 0 else None
            min_minutes = mn_min if mn_min > 0 else None
            try:
                ipk = int(getattr(self, 'images_per_keyword_var', tk.StringVar(value='10')).get().strip() or '10')
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
        mode_l = (mode.lower() if isinstance(mode, str) else 'both')
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
        self.log(f"Project: {proj}")
        self.log(f"Phiên bản Premiere: {version}")
        self.log(f"Định dạng tải: {dtype}")
        self.log("Hoàn tất quy trình.")
        self.log("=== KẾT THÚC TỰ ĐỘNG ===")

    def run_download_images(self):
        parent = self.parent_folder_var.get().strip()
        proj = self.project_file_var.get().strip()
        if not parent:
            self.log("LỖI: Chưa nhập thư mục chứa nội dung.")
            return
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                self.log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                self.log(f"LỖI: Không tạo được thư mục cha: {e}")
                return
        if not proj:
            self.log("LỖI: Chưa chọn file .prproj để xác định thư mục project trong data.")
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
        regen_cb = ttk.Checkbutton(info_frame, text='Ép tạo lại link lần chạy sau', variable=self.regen_links_var)
        regen_cb.grid(row=8, column=0, sticky='w')
        ttk.Label(info_frame, text='(Bỏ chọn = dùng lại nếu có)').grid(row=9, column=0, sticky='w', pady=(0,4))

        btns = ttk.Frame(info_frame)
        btns.grid(row=10, column=0, sticky='e', pady=(10,0))
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
        regen_cb = ttk.Checkbutton(info_frame, text='Ép tạo lại link lần chạy sau', variable=self.regen_links_var)
        regen_cb.grid(row=8, column=0, sticky='w')
        ttk.Label(info_frame, text='(Bỏ chọn = dùng lại nếu có)').grid(row=9, column=0, sticky='w', pady=(0,4))
        btns = ttk.Frame(info_frame)
        btns.grid(row=10, column=0, sticky='e', pady=(10,0))
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

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():  # pragma: no cover - manual GUI run
    app = AutoToolGUI()
    app.mainloop()

if __name__ == "__main__":  # pragma: no cover
    main()
