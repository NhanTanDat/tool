"""
down_by_yt.py
-----------------------------------
Dùng yt-dlp để tải VIDEO/AUDIO.

Trường hợp thường dùng với AutoTool:
    - type = "mp4"  -> TẢI VIDEO H.264 + MP4 (ưu tiên có cả audio, Premiere ăn chắc).
    - type = "mp3"  -> nếu có ffmpeg thì convert sang mp3, nếu không thì chỉ tải audio gốc.

YÊU CẦU:
    py -3.12 -m pip install yt-dlp
    (khuyến nghị cài thêm ffmpeg và add vào PATH)
"""

import os
import shutil
from typing import Dict, List

# ---------------------------------------------------------------------------
# Detect ffmpeg
# ---------------------------------------------------------------------------
FFMPEG_PATH = shutil.which("ffmpeg")
HAS_FFMPEG = FFMPEG_PATH is not None

# ---------------------------------------------------------------------------
# Helper thư mục
# ---------------------------------------------------------------------------

def ensure_folder(parent: str, name: str) -> str:
    """
    Tạo thư mục con parent/name nếu chưa có, và LUÔN trả về đường dẫn đó.
    """
    path = os.path.join(parent, name)
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Import yt-dlp
# ---------------------------------------------------------------------------
try:
    from yt_dlp import YoutubeDL
except ImportError:
    raise ImportError(
        "\nThiếu thư viện yt-dlp!\n"
        "Cài bằng lệnh:\n\n"
        "    py -3.12 -m pip install yt-dlp\n"
    )


# ---------------------------------------------------------------------------
# Parse file dl_links.txt -> {group_name: [url1, url2,...]}
# ---------------------------------------------------------------------------
def parse_links_from_txt(file_path: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    current = None
    synthetic_index = 1

    if not os.path.isfile(file_path):
        print(f"[down_by_yt][WARN] File không tồn tại: {file_path}")
        return groups

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # Link
            if line.startswith("https://") or line.startswith("http://"):
                if current is None:
                    current = f"group_{synthetic_index}"
                    groups[current] = []
                    synthetic_index += 1
                groups[current].append(line)
                continue

            # Header group: "1 Naruto" -> "Naruto"
            if " " in line and line.split(" ", 1)[0].isdigit():
                _, name = line.split(" ", 1)
            else:
                name = line

            safe_name = "_".join(name.split())  # thay khoảng trắng bằng _
            current = safe_name
            groups.setdefault(current, [])

    return groups


# ---------------------------------------------------------------------------
# Download 1 group link vào 1 folder con
# ---------------------------------------------------------------------------
def _download_group(group_name: str, links: List[str], parent_folder: str, media_type: str):
    if not links:
        print(f"[down_by_yt][INFO] Group '{group_name}' không có link → bỏ qua.")
        return

    # Tạo thư mục con: parent_folder/group_name
    group_dir = ensure_folder(parent_folder, group_name)

    print(f"[down_by_yt] === Group: {group_name} -> {len(links)} link")
    print(f"[down_by_yt] Folder: {group_dir}")

    # Cấu hình chung cho yt-dlp
    ydl_opts = {
        "outtmpl": os.path.join(group_dir, "%(title).80s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "ignoreerrors": True,
        "restrictfilenames": True,
        "continuedl": True,
        "quiet": False,
    }

    # Nếu có ffmpeg và sau này dùng mp3/mp4 merge thì cho yt-dlp biết
    if HAS_FFMPEG:
        ydl_opts["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

    media_type = media_type.lower().strip()

    # ======================== AUDIO (mp3) ========================
    if media_type == "mp3":
        if HAS_FFMPEG:
            # Dùng ffmpeg để convert sang mp3
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        else:
            # Không có ffmpeg -> chỉ tải audio gốc, không convert
            print(
                "[down_by_yt][WARN] Bạn chọn mp3 nhưng ffmpeg KHÔNG tìm thấy.\n"
                "  → Sẽ chỉ tải 'bestaudio/best' (webm/m4a...), KHÔNG convert sang .mp3.\n"
                "  Nếu muốn file .mp3, hãy cài ffmpeg và thêm vào PATH."
            )
            ydl_opts.update({
                "format": "bestaudio/best",
            })

    # ======================== VIDEO (mp4 H.264, PREMIERE-FRIENDLY) ========================
    else:
        # Mục tiêu:
        #   - CHỈ tải format Premiere ăn chắc: MP4 + H.264 (avc1)
        #   - Nếu có ffmpeg: cho phép tải video+audio tách rồi merge thành mp4
        #   - Nếu KHÔNG có ffmpeg: chỉ lấy progressive mp4 h.264; nếu không có thì SKIP
        if HAS_FFMPEG:
            # Ưu tiên:
            #   1) best video-only mp4 (avc1) + best audio m4a -> merge mp4
            #   2) nếu không có -> progressive mp4 (avc1)
            ydl_opts.update({
                "format": (
                    "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/"
                    "b[ext=mp4][vcodec^=avc1]"
                ),
                "merge_output_format": "mp4",
            })
            print("[down_by_yt] Dùng profile VIDEO MP4(H.264) + merge bằng ffmpeg cho Premiere.")
        else:
            # Không có ffmpeg: chỉ chấp nhận progressive mp4 H.264
            # Nếu video không có stream này -> yt-dlp sẽ báo lỗi và bỏ qua.
            ydl_opts.update({
                "format": "b[ext=mp4][vcodec^=avc1]",
            })
            print(
                "[down_by_yt][WARN] ffmpeg KHÔNG có, chỉ tải được progressive MP4 H.264.\n"
                "  Nếu video không có định dạng này thì sẽ bị SKIP."
            )

    # Tải từng link
    with YoutubeDL(ydl_opts) as ydl:
        for i, url in enumerate(links, start=1):
            print(f"[down_by_yt]   ({i}/{len(links)}) Download: {url}")
            try:
                ydl.download([url])
            except Exception as e:
                print(f"[down_by_yt][ERROR] Lỗi tải {url}: {e}")


# ---------------------------------------------------------------------------
# Hàm public: AutoTool sẽ gọi download_main()
#   - parent_folder: thư mục resource của project Premiere
#   - txt_name: đường dẫn dl_links.txt
#   - _type: 'mp4' (video H.264+MP4) hoặc 'mp3'
# ---------------------------------------------------------------------------
def download_main(parent_folder: str, txt_name: str, _type: str = "mp4"):
    print("[down_by_yt] === START download_main ===")
    print(f"[down_by_yt] parent_folder = {parent_folder}")
    print(f"[down_by_yt] txt_name      = {txt_name}")
    print(f"[down_by_yt] type          = {_type}")
    print(f"[down_by_yt] ffmpeg        = {FFMPEG_PATH if HAS_FFMPEG else 'NOT FOUND'}")

    # Đảm bảo thư mục cha tồn tại
    try:
        os.makedirs(parent_folder, exist_ok=True)
    except Exception as e:
        print(f"[down_by_yt][ERROR] Không tạo được {parent_folder}: {e}")
        print("[down_by_yt] === END download_main ===")
        return

    # Parse file dl_links.txt
    groups = parse_links_from_txt(txt_name)
    if not groups:
        print("[down_by_yt][WARN] Không tìm thấy group/link nào trong file link!")
        print("[down_by_yt] === END download_main ===")
        return

    total_groups = len(groups)
    total_links = sum(len(v) for v in groups.values())
    print(f"[down_by_yt] Tổng group: {total_groups}, tổng link: {total_links}")

    media_type = _type.lower().strip()
    if media_type not in ("mp4", "mp3"):
        print(f"[down_by_yt][WARN] Loại '{_type}' không hợp lệ → dùng 'mp4'.")
        media_type = "mp4"

    # Tải từng group
    for idx, (group, links) in enumerate(groups.items(), start=1):
        print(f"[down_by_yt] --- ({idx}/{total_groups}) Group '{group}' ---")
        _download_group(group, links, parent_folder, media_type)

    print("[down_by_yt] === END download_main ===")


# ---------------------------------------------------------------------------
# Test trực tiếp (không qua GUI)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    THIS_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
    DATA_DIR = os.path.join(ROOT_DIR, "data")

    parent_folder = os.path.join(ROOT_DIR, "test_download")
    txt_name = os.path.join(DATA_DIR, "dl_links.txt")

    print("Test download_main với:")
    print("  parent_folder =", parent_folder)
    print("  txt_name      =", txt_name)
    download_main(parent_folder, txt_name, _type="mp4")
