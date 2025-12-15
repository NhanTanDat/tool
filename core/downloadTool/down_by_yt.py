"""
down_by_yt.py
-----------------------------------
Dùng yt-dlp để tải VIDEO/AUDIO.

- mp4: ưu tiên MP4 H.264 (avc1) + audio m4a (merge mp4) cho Premiere
- mp3: nếu có ffmpeg thì convert mp3, nếu không thì tải audio gốc

✅ MODE (theo yêu cầu):
- KHÔNG check subtitles
- KHÔNG filter link
- CHỈ download đúng thứ tự link trong file
"""

import os
import re
import shutil
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# CONFIG: đặt tên file theo index
# ---------------------------------------------------------------------------
INDEX_START = 0     # 0-based để khớp video_index trong CSV
INDEX_PAD = 4       # 0000, 0001...

# Cookie (nếu cần)
COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE", "").strip()

# Ép client để giảm warning SABR (tuỳ chọn)
YTDLP_PLAYER_CLIENT = (os.environ.get("YTDLP_PLAYER_CLIENT", "android") or "android").strip().lower()

# Retry tuning (tuỳ chọn)
YTDLP_RETRIES = int(os.environ.get("YTDLP_RETRIES", "10"))
YTDLP_SLEEP_INTERVAL = float(os.environ.get("YTDLP_SLEEP_INTERVAL", "2"))
YTDLP_MAX_SLEEP_INTERVAL = float(os.environ.get("YTDLP_MAX_SLEEP_INTERVAL", "6"))

# ---------------------------------------------------------------------------
# Detect ffmpeg
# ---------------------------------------------------------------------------
FFMPEG_PATH = shutil.which("ffmpeg")
HAS_FFMPEG = FFMPEG_PATH is not None

# ---------------------------------------------------------------------------
# Helper: sanitize folder name (Windows-safe)
# ---------------------------------------------------------------------------
def sanitize_folder_name(name: str) -> str:
    if not isinstance(name, str):
        name = str(name)
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = "".join(ch for ch in name if ch not in '<>:"/\\|?*')
    name = name.rstrip(" .")
    return name or "group"


def ensure_folder(parent: str, name: str) -> str:
    safe = sanitize_folder_name(name)
    path = os.path.join(parent, safe)
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
        "    py -3.12 -m pip install -U yt-dlp\n"
    )


# ---------------------------------------------------------------------------
# Parse file dl_links.txt -> {group_name: [url1, url2,...]}
# ---------------------------------------------------------------------------
def parse_links_from_txt(file_path: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    current: Optional[str] = None
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

            safe_name = sanitize_folder_name(name)
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

    group_dir = ensure_folder(parent_folder, group_name)

    print(f"[down_by_yt] === Group: {group_name} -> {len(links)} link")
    print(f"[down_by_yt] Folder: {group_dir}")

    # Base ydl options
    ydl_opts = {
        "outtmpl": {"default": os.path.join(group_dir, "temp_%(id)s.%(ext)s")},
        "noplaylist": True,
        "ignoreerrors": True,
        "restrictfilenames": True,
        "continuedl": True,
        "quiet": False,
        "retries": YTDLP_RETRIES,
        "sleep_interval": YTDLP_SLEEP_INTERVAL,
        "max_sleep_interval": YTDLP_MAX_SLEEP_INTERVAL,
        # giảm warning SABR
        "extractor_args": {"youtube": {"player_client": [YTDLP_PLAYER_CLIENT]}},
    }

    if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    if HAS_FFMPEG:
        # ffmpeg_location nên là folder chứa ffmpeg.exe
        ydl_opts["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

    media_type = media_type.lower().strip()

    # ======================== AUDIO (mp3) ========================
    if media_type == "mp3":
        if HAS_FFMPEG:
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        else:
            print(
                "[down_by_yt][WARN] Bạn chọn mp3 nhưng ffmpeg KHÔNG tìm thấy.\n"
                "  → Sẽ chỉ tải 'bestaudio/best' (webm/m4a...), KHÔNG convert sang .mp3.\n"
                "  Nếu muốn file .mp3, hãy cài ffmpeg và thêm vào PATH."
            )
            ydl_opts.update({"format": "bestaudio/best"})

    # ======================== VIDEO (mp4 H.264) ========================
    else:
        if HAS_FFMPEG:
            ydl_opts.update({
                "format": (
                    "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/"
                    "b[ext=mp4][vcodec^=avc1]"
                ),
                "merge_output_format": "mp4",
                "final_ext": "mp4",
            })
            print("[down_by_yt] Dùng profile VIDEO MP4(H.264) + merge bằng ffmpeg cho Premiere.")
        else:
            ydl_opts.update({
                "format": "b[ext=mp4][vcodec^=avc1]",
                "final_ext": "mp4",
            })
            print(
                "[down_by_yt][WARN] ffmpeg KHÔNG có, chỉ tải được progressive MP4 H.264.\n"
                "  Nếu video không có định dạng này thì sẽ bị SKIP."
            )

    # ✅ KHÔNG FILTER GÌ HẾT: tải đúng thứ tự links
    with YoutubeDL(ydl_opts) as ydl:
        for idx, url in enumerate(links, start=INDEX_START):
            tmpl = os.path.join(group_dir, f"{idx:0{INDEX_PAD}d}.%(ext)s")

            # outtmpl là dict -> update "default"
            if isinstance(ydl.params.get("outtmpl"), dict):
                ydl.params["outtmpl"]["default"] = tmpl
            else:
                ydl.params["outtmpl"] = {"default": tmpl}

            print(f"[down_by_yt]   ({idx - INDEX_START + 1}/{len(links)}) Download -> index={idx}: {url}")
            try:
                ydl.download([url])
            except Exception as e:
                print(f"[down_by_yt][ERROR] Lỗi tải {url}: {e}")


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
def download_main(parent_folder: str, txt_name: str, _type: str = "mp4"):
    print("[down_by_yt] === START download_main ===")
    print(f"[down_by_yt] parent_folder = {parent_folder}")
    print(f"[down_by_yt] txt_name      = {txt_name}")
    print(f"[down_by_yt] type          = {_type}")
    print(f"[down_by_yt] ffmpeg        = {FFMPEG_PATH if HAS_FFMPEG else 'NOT FOUND'}")
    print(f"[down_by_yt] index naming  = start={INDEX_START}, pad={INDEX_PAD}")
    print(f"[down_by_yt] MODE          = download-only (no subtitle filter/check)")
    print(f"[down_by_yt] player_client = {YTDLP_PLAYER_CLIENT}")

    try:
        os.makedirs(parent_folder, exist_ok=True)
    except Exception as e:
        print(f"[down_by_yt][ERROR] Không tạo được {parent_folder}: {e}")
        print("[down_by_yt] === END download_main ===")
        return

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

    for idx, (group, links) in enumerate(groups.items(), start=1):
        print(f"[down_by_yt] --- ({idx}/{total_groups}) Group '{group}' ---")
        _download_group(group, links, parent_folder, media_type)

    print("[down_by_yt] === END download_main ===")


if __name__ == "__main__":
    THIS_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
    DATA_DIR = os.path.join(ROOT_DIR, "data")

    parent_folder = os.path.join(ROOT_DIR, "test_download")
    txt_name = os.path.join(DATA_DIR, "dl_links.txt")

    download_main(parent_folder, txt_name, _type="mp4")
