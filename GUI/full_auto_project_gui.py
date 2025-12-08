# GUI/full_auto_project_gui.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Đảm bảo import được core.project_creator
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
DATA_DIR = os.path.join(_ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

try:
    from core import project_creator  # type: ignore
except Exception:
    import sys
    sys.path.append(_ROOT_DIR)
    from core import project_creator  # type: ignore


class FullAutoProjectGUI(tk.Tk):
    """
    GUI cho user cuối:
    - Chọn template .prproj
    - Chọn folder lưu project mới
    - Nhập chủ đề (topic)
    - Nhập list keyword
    - Bấm nút => tool tự:
        + Copy template -> project mới (.prproj)
        + Tạo data/<slug>/list_name.txt
        + Ghi _current_project.txt
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Tạo project Premiere + Keyword (Full Auto)")
        self.geometry("800x520")

        self.template_var = tk.StringVar()
        self.out_root_var = tk.StringVar()
        self.topic_var = tk.StringVar()
        self.slug_var = tk.StringVar()
        self.keyword_file_var = tk.StringVar()
        self.project_path_var = tk.StringVar()

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = 8
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        row = 0
        # Template
        ttk.Label(frm, text="Template .prproj:", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w", padx=pad, pady=(pad, 2)
        )
        ttk.Entry(frm, textvariable=self.template_var, width=60).grid(
            row=row, column=1, sticky="we", padx=(pad, 4), pady=(pad, 2)
        )
        ttk.Button(frm, text="Chọn...", command=self._choose_template).grid(
            row=row, column=2, sticky="w", padx=(0, pad), pady=(pad, 2)
        )
        row += 1

        # Output root
        ttk.Label(frm, text="Thư mục lưu project mới:").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Entry(frm, textvariable=self.out_root_var, width=60).grid(
            row=row, column=1, sticky="we", padx=(pad, 4), pady=2
        )
        ttk.Button(frm, text="Chọn...", command=self._choose_out_root).grid(
            row=row, column=2, sticky="w", padx=(0, pad), pady=2
        )
        row += 1

        # Topic
        ttk.Label(frm, text="Chủ đề / tên project:", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w", padx=pad, pady=(10, 2)
        )
        ttk.Entry(frm, textvariable=self.topic_var).grid(
            row=row, column=1, columnspan=2, sticky="we", padx=pad, pady=(10, 2)
        )
        row += 1

        # Slug
        ttk.Label(frm, text="Slug (folder + tên file):").grid(
            row=row, column=0, sticky="w", padx=pad, pady=2
        )
        ttk.Label(frm, textvariable=self.slug_var, foreground="#444").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=pad, pady=2
        )
        row += 1

        # Label keywords
        ttk.Label(
            frm,
            text="Nhập KEYWORD (mỗi dòng 1 keyword):",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=pad, pady=(12, 4))
        row += 1

        # Text box keywords
        self.txt_keywords = tk.Text(frm, height=12, wrap="word")
        self.txt_keywords.grid(
            row=row, column=0, columnspan=3, sticky="nsew", padx=pad, pady=(0, 4)
        )
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.txt_keywords.yview)
        scroll.grid(row=row, column=3, sticky="ns", pady=(0, 4))
        self.txt_keywords.configure(yscrollcommand=scroll.set)
        text_row_index = row
        row += 1

        # Info keyword file
        ttk.Label(frm, text="File keyword sẽ lưu tại:").grid(
            row=row, column=0, sticky="w", padx=pad, pady=(4, 2)
        )
        ttk.Label(frm, textvariable=self.keyword_file_var, foreground="#444").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=pad, pady=(4, 2)
        )
        row += 1

        # Info project path
        ttk.Label(frm, text="Project .prproj mới:").grid(
            row=row, column=0, sticky="w", padx=pad, pady=(2, 2)
        )
        ttk.Label(frm, textvariable=self.project_path_var, foreground="#444").grid(
            row=row, column=1, columnspan=2, sticky="w", padx=pad, pady=(2, 2)
        )
        row += 1

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="e", padx=pad, pady=(10, pad))
        ttk.Button(
            btn_frame,
            text="Tạo project + lưu keyword",
            command=self._create_project,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Thoát", command=self.destroy).pack(
            side="left", padx=(0, 0)
        )

        # Cho phép entry / textbox co giãn
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(text_row_index, weight=1)

    # ------------------------------------------------------------------
    def _choose_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn template Premiere project",
            filetypes=[("Premiere Project", "*.prproj"), ("All files", "*.*")],
        )
        if path:
            self.template_var.set(path)

    def _choose_out_root(self) -> None:
        path = filedialog.askdirectory(
            title="Chọn thư mục gốc để lưu các project mới",
        )
        if path:
            self.out_root_var.set(path)

    # ------------------------------------------------------------------
    def _create_project(self) -> None:
        template = self.template_var.get().strip()
        out_root = self.out_root_var.get().strip()
        topic = self.topic_var.get().strip()

        if not template:
            messagebox.showerror("Lỗi", "Chưa chọn template .prproj.")
            return
        if not out_root:
            messagebox.showerror("Lỗi", "Chưa chọn thư mục lưu project.")
            return
        if not topic:
            messagebox.showerror("Lỗi", "Chưa nhập chủ đề / tên project.")
            return

        raw_keywords = self.txt_keywords.get("1.0", "end")
        lines = [ln.strip() for ln in raw_keywords.splitlines()]
        keywords = [ln for ln in lines if ln]

        if not keywords:
            if not messagebox.askyesno(
                "Không có keyword",
                "Danh sách keyword đang trống.\nBạn vẫn muốn tạo project (keyword sẽ rỗng)?",
            ):
                return

        # Tạo project từ template
        try:
            info = project_creator.create_project_from_template(
                template_prproj=template,
                output_root=out_root,
                topic=topic,
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không tạo được project mới:\n{e}")
            return

        slug = info["slug"]
        project_dir = info["project_dir"]
        project_path = info["project_path"]
        data_dir = info["data_dir"]

        # Ghi list_name.txt
        names_txt = os.path.join(data_dir, "list_name.txt")
        try:
            with open(names_txt, "w", encoding="utf-8") as f:
                for idx, kw in enumerate(keywords, start=1):
                    f.write(f"{idx} {kw}\n")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không ghi được file keyword:\n{e}")
            return

        # Update UI info
        self.slug_var.set(slug)
        self.keyword_file_var.set(names_txt)
        self.project_path_var.set(project_path)

        messagebox.showinfo(
            "Hoàn tất",
            "Đã tạo project mới và lưu keyword.\n\n"
            f"- Project: {project_path}\n"
            f"- Dữ liệu: {data_dir}\n"
            f"- Keyword: {names_txt}\n\n"
            "Giờ bạn có thể mở AutoTool chính, thêm file .prproj này vào batch,\n"
            "rồi chạy quy trình tự động như bình thường.",
        )

        # Mở folder chứa project cho tiện kiểm tra
        try:
            folder = os.path.dirname(project_path)
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass


def main() -> None:
    app = FullAutoProjectGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
