import os
import sys
from typing import Callable

# =====================================================================
# ĐỊNH NGHĨA ĐƯỜNG DẪN GỐC & DATA (DÙNG CHUNG CHO CẢ GUI & LOGIC)
# =====================================================================

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, '..'))  # project root

DATA_DIR = os.path.join(_ROOT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Đảm bảo project root (nơi chứa thư mục 'core') nằm trong sys.path
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

# File config lưu cấu hình GUI
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')


# =====================================================================
# HÀM DÙNG CHUNG: sinh slug từ đường dẫn .prproj
# =====================================================================

def derive_project_slug(proj_path: str) -> str:
    """
    Lấy tên file .prproj (bỏ đuôi), chỉ giữ a-zA-Z0-9, '-', '_'
    ví dụ: 'Hán_đế phần 1.prproj' -> 'Han__e_phan_1'
    """
    base = os.path.basename(proj_path)
    stem, _ = os.path.splitext(base)
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)


# =====================================================================
# THỐNG KÊ LINK (DL_LINKS.TXT)
# =====================================================================

def compute_links_stats(links_path: str) -> tuple[int, int]:
    """
    Đếm số nhóm (dòng không phải link) và tổng số link (http/https) trong file link.
    """
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


# =====================================================================
# CORE LOGIC: TẢI VIDEO/ẢNH + GỌI AI TIMELINE
# =====================================================================

class AutoToolLogic:
    """
    Class thuần logic, KHÔNG phụ thuộc Tkinter.
    Mọi UI (log ra Text, cập nhật progress bar...) đều thông qua callback.
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    # -----------------------------------------------------------------
    def run_automation_for_project(
        self,
        proj_path: str,
        *,
        version: str,
        download_type: str,
        mode: str,
        videos_per_keyword: str,
        images_per_keyword: str,
        max_duration: str,
        min_duration: str,
        regen_links: bool,
        log: Callable[[str], None],
        update_progress: Callable[[float, str | None], None],
    ) -> None:
        """
        Toàn bộ logic cũ trong AutoToolGUI.run_automation_for_project()
        được chuyển sang đây.

        - log(msg): dùng để ghi log (GUI sẽ truyền self.log)
        - update_progress(value, message): cập nhật progress bar (0–100)
        """

        # Set up resource folder for this project
        proj_dir = os.path.dirname(os.path.abspath(proj_path))
        parent = os.path.join(proj_dir, 'resource')

        dtype = download_type
        mode_l = (mode or "").lower().strip()

        log("=== BẮT ĐẦU TỰ ĐỘNG ===")
        update_progress(0, "Bắt đầu xử lý project...")

        # Create resource directory if it doesn't exist
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                log(f"LỖI: Không tạo được thư mục cha: {e}")
                update_progress(100, "Lỗi tạo thư mục resource.")
                return

        if not os.path.isfile(proj_path):
            log("LỖI: Thiếu file project. Dừng.")
            update_progress(100, "Lỗi: Thiếu file project.")
            return

        # Lazy import heavy modules only now to avoid initial GUI lag.
        try:
            from core.downloadTool import down_by_yt, get_link  # type: ignore
        except Exception:
            try:
                import importlib
                down_by_yt = importlib.import_module("core.downloadTool.down_by_yt")  # type: ignore
                get_link = importlib.import_module("core.downloadTool.get_link")      # type: ignore
            except Exception as e:  # pragma: no cover - chỉ log lỗi runtime
                log(f"ERROR: Cannot import modules (core.downloadTool.*): {e}")
                update_progress(100, "Lỗi import core.downloadTool.")
                return

        # Build absolute paths (PyInstaller aware: use _MEIPASS if present)
        _ = getattr(sys, "_MEIPASS", _ROOT_DIR)  # reserved for future use

        # Thư mục data riêng cho mỗi project (.prproj) dựa trên tên file
        safe_project = derive_project_slug(proj_path)
        data_project_dir = os.path.join(self.data_dir, safe_project)
        if not os.path.isdir(data_project_dir):
            try:
                os.makedirs(data_project_dir, exist_ok=True)
                log(f"Đã tạo thư mục dữ liệu project: {data_project_dir}")
            except Exception as e:
                log(f"LỖI: Không tạo được thư mục dữ liệu project ({e})")
                update_progress(100, "Lỗi tạo thư mục dữ liệu project.")
                return

        names_txt = os.path.join(data_project_dir, "list_name.txt")

        # đảm bảo thư mục data gốc tồn tại (fallback)
        if not os.path.isdir(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except Exception:
                log(f"CẢNH BÁO: Không tạo được thư mục data gốc: {self.data_dir}")

        # Thư mục lưu link: luôn dùng thư mục project trong data
        links_dir = data_project_dir
        log(f"Thư mục lưu link: {links_dir}")
        links_txt = os.path.join(links_dir, "dl_links.txt")            # list of grouped video links
        links_img_txt = os.path.join(links_dir, "dl_links_image.txt")  # list of grouped image links

        # 1. CHUẨN BỊ DANH SÁCH KEYWORD – KHÔNG TỰ GEN NỮA
        try:
            # (tuỳ) vẫn ghi marker cho ExtendScript nếu bạn còn dùng
            try:
                from core.project_data import write_current_project_marker  # type: ignore
                write_current_project_marker(safe_project)
                log(f"Đánh dấu project hiện tại: {safe_project}")
            except Exception as _pmErr:
                log(f"CẢNH BÁO: Không ghi được marker project ({_pmErr})")

            # BẮT BUỘC phải có list_name.txt do bạn tự tạo
            if not os.path.isfile(names_txt):
                log(f"LỖI: Không tìm thấy file keyword: {names_txt}")
                log("→ Hãy tạo file list_name.txt (mỗi dòng 1 keyword) rồi chạy lại.")
                update_progress(100, "Thiếu file keyword list_name.txt.")
                return

            keyword_count = 0
            try:
                with open(names_txt, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            keyword_count += 1
            except Exception as e:
                log(f"LỖI: Không đọc được {names_txt}: {e}")
                update_progress(100, "Lỗi đọc file keyword.")
                return

            if keyword_count == 0:
                log("LỖI: list_name.txt không có keyword nào.")
                log("→ Hãy nhập keyword (mỗi dòng 1 keyword) rồi chạy lại.")
                update_progress(100, "list_name.txt không có keyword.")
                return
            else:
                log(f"Đã sẵn sàng {keyword_count} keyword trong {names_txt}")
                update_progress(5, f"Đã chuẩn bị {keyword_count} keyword.")
        except Exception as e:
            log(f"LỖI khi chuẩn bị danh sách keyword: {e}")
            update_progress(100, "Lỗi chuẩn bị keyword.")
            return

        # 2. Generate links file theo chế độ (dùng AI get_link)
        try:
            # Read parameters (parse từ string GUI truyền xuống)
            try:
                mpk = int((videos_per_keyword or "").strip() or '10')
            except Exception:
                mpk = 10
            try:
                mx_max = int((max_duration or "").strip() or '20')
            except Exception:
                mx_max = 20
            try:
                mn_min = int((min_duration or "").strip() or '4')
            except Exception:
                mn_min = 4
            max_minutes = mx_max if mx_max > 0 else None
            min_minutes = mn_min if mn_min > 0 else None
            try:
                ipk = int((images_per_keyword or "").strip() or '10')
            except Exception:
                ipk = 10

            force_flag = bool(regen_links)

            if mode_l == 'both':
                log("Đang tạo link (cả VIDEO và ẢNH)...")
                # LƯU Ý: project_name phải là tham số POSitional thứ 3
                get_link.get_links_main(
                    names_txt,     # keywords_file
                    links_txt,     # output_txt (video)
                    safe_project,  # project_name (POSitional)
                    max_per_keyword=mpk,
                    max_minutes=max_minutes,
                    min_minutes=min_minutes,
                    images_per_keyword=ipk,
                )
                log(f"Đã tạo link VIDEO -> {links_txt}")
                log(f"Đã tạo link ẢNH -> {links_img_txt}")  # file này do get_links_main tự tạo trong cùng thư mục

            elif mode_l == 'video':
                do_regen = True
                if os.path.isfile(links_txt) and not force_flag:
                    do_regen = False
                    log("Giữ lại link VIDEO hiện có (user chọn)")
                if do_regen:
                    log("Đang tạo link VIDEO...")
                    get_link.get_links_main_video(
                        names_txt,     # keywords_file
                        links_txt,     # output_txt
                        safe_project,  # project_name (POSitional)
                        max_per_keyword=mpk,
                        max_minutes=max_minutes,
                        min_minutes=min_minutes,
                    )
                    log(f"Đã tạo link VIDEO -> {links_txt}")

            elif mode_l == 'image':
                do_regen = True
                if os.path.isfile(links_img_txt) and not force_flag:
                    do_regen = False
                    log("Giữ lại link ẢNH hiện có (user chọn)")
                if do_regen:
                    log("Đang tạo link ẢNH...")
                    get_link.get_links_main_image(
                        names_txt,      # keywords_file
                        links_img_txt,  # output_txt
                        safe_project,   # project_name (POSitional)
                        images_per_keyword=ipk,
                    )
                    log(f"Đã tạo link ẢNH -> {links_img_txt}")

            update_progress(10, "Đã tạo link xong.")
        except Exception as e:
            log(f"CẢNH BÁO: Không tạo được link ({e}).")
            # Dù lỗi, vẫn tiếp tục nếu đã có link cũ -> không set progress 100 ở đây

        # 3. Run download logic theo chế độ
        timeline_needed = mode_l in ('both', 'video')
        video_done = False
        image_done = False

        # VIDEO
        if mode_l in ('both', 'video'):
            try:
                log("Bắt đầu tải VIDEO...")
                update_progress(15, "Đang tải VIDEO từ YouTube...")
                from core.downloadTool.down_by_yt import download_main as _dl_main  # type: ignore
                _dl_main(parent, links_txt, _type=dtype)
                video_done = True
                log("Tải VIDEO xong.")

                if mode_l == 'video':
                    update_progress(90, "Đã tải xong VIDEO.")
                elif mode_l == 'both':
                    update_progress(55, "Đã tải xong VIDEO. Chuẩn bị tải ẢNH...")
            except Exception as e:
                log(f"LỖI khi tải VIDEO: {e}")
                update_progress(100, "Lỗi khi tải VIDEO.")
                return

        # IMAGE
        if mode_l in ('both', 'image'):
            # Import downImage lazily to download images
            try:
                import importlib
                down_image = importlib.import_module("core.downloadTool.downImage")
            except Exception as e:
                log(f"LỖI: Không thể import downImage: {e}")
                update_progress(100, "Lỗi import downImage.")
                return
            try:
                log("Bắt đầu tải ẢNH...")
                if mode_l == 'image':
                    update_progress(15, "Đang tải ẢNH...")
                else:
                    update_progress(60, "Đang tải ẢNH...")

                attempted = down_image.download_images_main(parent, links_img_txt)
                log(f"Đã gửi tải {attempted} ảnh. Xem kết quả trong các thư mục *_img tại: {parent}")
                image_done = True

                if mode_l == 'image':
                    update_progress(100, "Đã tải xong ẢNH.")
                elif mode_l == 'both':
                    update_progress(90, "Đã tải xong ẢNH.")
            except Exception as e:
                log(f"LỖI khi tải ẢNH: {e}")
                update_progress(100, "Lỗi khi tải ẢNH.")
                return

        # 4. GENMINI TIMELINE (chỉ khi có VIDEO)
        if timeline_needed and video_done:
            try:
                try:
                    from core.ai.genmini_analyze import (
                        run_genmini_for_project,
                        build_timeline_csv_from_segments,
                    )
                except Exception as e:
                    log(f"LỖI: Không import được core.ai.genmini_analyze: {e}")
                    update_progress(100, "Hoàn tất (lỗi module Genmini).")
                    return

                log("Bắt đầu phân tích video bằng Genmini để sinh timeline...")

                # Giữ behaviour cũ: mode both yêu cầu ảnh ok (nếu bạn muốn bỏ điều kiện này thì xoá block if này)
                if mode_l == 'both' and not image_done:
                    log("CẢNH BÁO: Chế độ both nhưng ảnh chưa tải xong. Bỏ qua sinh timeline.")
                    update_progress(100, "Bỏ qua sinh timeline do thiếu ảnh.")
                else:
                    dl_links_path = links_txt
                    if not os.path.isfile(dl_links_path):
                        log(f"LỖI: Không tìm thấy dl_links.txt để Genmini phân tích: {dl_links_path}")
                        update_progress(100, "Hoàn tất (thiếu dl_links.txt).")
                        return

                    segments_json = os.path.join(data_project_dir, "segments_genmini.json")
                    timeline_csv = os.path.join(data_project_dir, "timeline_export_merged.csv")

                    update_progress(92, "Genmini đang phân tích phân đoạn nhân vật...")
                    num_items = run_genmini_for_project(
                        dl_links_path=dl_links_path,
                        segments_json_path=segments_json,
                        max_segments_per_video=8,
                    )
                    log(f"[Genmini] Đã phân tích xong {num_items} video có segment.")

                    if num_items == 0:
                        log("[Genmini] Không có segment nào được trả về. Bỏ qua sinh timeline.")
                        update_progress(100, "Hoàn tất (Genmini không trả segment).")
                        return

                    update_progress(97, "Đang sinh file timeline cho Premiere...")
                    num_scenes = build_timeline_csv_from_segments(
                        segments_json_path=segments_json,
                        timeline_csv_path=timeline_csv,
                        only_character=None,
                    )
                    log(f"[Genmini] Đã sinh {num_scenes} đoạn vào: {timeline_csv}")
                    log("🎬 Timeline đã được tạo, Premiere sẽ cắt đúng theo phân đoạn Genmini.")
                    update_progress(100, "Hoàn tất! Timeline Genmini đã được tạo.")
            except Exception as e:
                log(f"LỖI khi chạy Genmini timeline: {e}")
                update_progress(100, "Hoàn tất (lỗi khi sinh timeline Genmini).")
                return
        else:
            if mode_l == 'image':
                update_progress(100, "Hoàn tất tải ảnh.")
            elif mode_l == 'both' and not video_done:
                update_progress(100, "Hoàn tất (VIDEO không tải được).")

        # Nhật ký tổng kết
        log(f"Project: {proj_path}")
        log(f"Phiên bản Premiere: {version}")
        log(f"Định dạng tải: {dtype}")
        log("Hoàn tất quy trình.")
        log("=== KẾT THÚC TỰ ĐỘNG ===")

    # -----------------------------------------------------------------
    def run_download_images(
        self,
        proj_path: str,
        log: Callable[[str], None],
    ) -> None:
        """
        Logic cũ trong AutoToolGUI.run_download_images(), tách khỏi UI.
        """
        proj_dir = os.path.dirname(os.path.abspath(proj_path))
        parent = os.path.join(proj_dir, 'resource')

        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
                log(f"Đã tạo thư mục chứa nội dung: {parent}")
            except Exception as e:
                log(f"LỖI: Không tạo được thư mục cha: {e}")
                return

        safe_project = derive_project_slug(proj_path)
        links_dir = os.path.join(self.data_dir, safe_project)
        links_img_txt = os.path.join(links_dir, "dl_links_image.txt")
        if not os.path.isfile(links_img_txt):
            log(f"LỖI: Không tìm thấy file link ảnh: {links_img_txt}")
            log(
                "Hãy chạy 'Chạy tự động' để tạo link trước "
                "hoặc kiểm tra thư mục link tuỳ chọn."
            )
            return

        try:
            import importlib
            down_image = importlib.import_module("core.downloadTool.downImage")
        except Exception as e:
            log(f"LỖI: Không thể import downImage: {e}")
            return

        try:
            attempted = down_image.download_images_main(parent, links_img_txt)
            log(
                f"Đã gửi tải {attempted} ảnh. "
                f"Xem kết quả trong các thư mục *_img tại: {parent}"
            )
        except Exception as e:
            log(f"LỖI khi tải ảnh: {e}")
    