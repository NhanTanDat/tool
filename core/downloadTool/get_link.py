import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# =============================
#  IMPORT & PATH SETUP
# =============================

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None  # sẽ báo lỗi đẹp nếu thiếu

# Cho phép import cả dạng module lẫn chạy trực tiếp
THIS_FILE = os.path.abspath(__file__)
DOWNLOAD_TOOL_DIR = os.path.dirname(THIS_FILE)
CORE_DIR = os.path.dirname(DOWNLOAD_TOOL_DIR)
ROOT_DIR = os.path.dirname(CORE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Dùng lại hàm sinh link ảnh từ downImage.py
try:
    from core.downloadTool.downImage import gen_image_links_from_yt_txt
except Exception:
    gen_image_links_from_yt_txt = None


# =============================
#  HÀM ĐỌC KEYWORD
# =============================

def _read_keywords(keywords_file: str) -> List[str]:
    """
    Đọc list keyword từ file, loại trùng nhưng giữ nguyên thứ tự.
    """
    path = Path(keywords_file)
    if not path.exists():
        raise FileNotFoundError(f"keywords_file không tồn tại: {keywords_file}")

    seen = set()
    result: List[str] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        kw = raw.strip()
        if not kw:
            continue
        if kw in seen:
            continue
        seen.add(kw)
        result.append(kw)

    return result


# =============================
#  SEARCH YOUTUBE
# =============================

def _search_youtube_for_keyword(keyword: str, max_results: int = 4) -> List[Dict[str, Any]]:
    """
    Search YouTube bằng yt_dlp, trả về list candidate:
    [
      {
        "title": ...,
        "url": ...,
        "duration": seconds or None,
        "channel": ...
      },
      ...
    ]
    """
    if YoutubeDL is None:
        raise RuntimeError(
            "yt_dlp chưa được cài. Hãy cài bằng:\n"
            "    pip install yt-dlp"
        )

    query = f"ytsearch{max_results}:{keyword}"

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "default_search": "ytsearch",
        "noplaylist": True,
        "extract_flat": True,
    }

    out: List[Dict[str, Any]] = []

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        entries = info.get("entries", [])
        for e in entries:
            url = e.get("url") or e.get("webpage_url")
            if not url:
                continue
            # yt_dlp extract_flat thường trả về id, cần build lại URL
            if not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"

            item = {
                "title": e.get("title") or "",
                "url": url,
                "duration": e.get("duration"),
                "channel": (e.get("uploader") or e.get("channel")) or "",
            }
            out.append(item)

    return out


# =============================
#  GHI FILE LINK VIDEO
# =============================

def _write_video_links_txt(
    output_txt: str,
    keywords: List[str],
    videos_per_keyword: int,
) -> int:
    """
    Ghi file link video theo format:

    <keyword 1>
    https://youtube.com/...
    https://youtube.com/...

    <keyword 2>
    https://youtube.com/...
    ...

    Trả về: tổng số link.
    """
    total_links = 0
    lines: List[str] = []

    for kw in keywords:
        candidates = _search_youtube_for_keyword(kw, max_results=videos_per_keyword)
        urls = [c["url"] for c in candidates if c.get("url")]

        if not urls:
            # vẫn ghi header để down_by_yt sau này có thể tạo folder trống cho keyword
            lines.append(kw)
            lines.append("")  # dòng trống
            continue

        lines.append(kw)
        for url in urls:
            lines.append(url)
            total_links += 1
        lines.append("")  # dòng trống giữa các group

    Path(output_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(output_txt).write_text("\n".join(lines), encoding="utf-8")

    return total_links


# =============================
#  TỰ SINH LINK ẢNH TỪ LINK VIDEO
# =============================

def _auto_gen_image_links(video_txt: str, image_txt: Optional[str] = None) -> Optional[str]:
    """
    Từ file link VIDEO, tự động sinh file link ẢNH thumbnail YouTube.

    Nếu thiếu downImage.gen_image_links_from_yt_txt thì chỉ log cảnh báo.
    """
    if gen_image_links_from_yt_txt is None:
        print("[get_link] WARN: Không import được gen_image_links_from_yt_txt, bỏ qua bước tạo link ảnh.")
        return None

    if image_txt is None:
        base, ext = os.path.splitext(video_txt)
        image_txt = base + "_image.txt"  # ví dụ: dl_links_image.txt

    try:
        total = gen_image_links_from_yt_txt(video_txt, image_txt)
        print(f"[get_link] Đã sinh {total} link ảnh vào: {image_txt}")
    except Exception as e:
        print(f"[get_link] LỖI khi sinh link ảnh: {e}")
        return None

    return image_txt


# =============================
#  HÀM MAIN CHO GUI
# =============================

def get_links_main(*args, **kwargs) -> None:
    """
    Hàm main được GUI gọi.

    Hỗ trợ cả style cũ (chỉ VIDEO) lẫn mới (VIDEO + ẢNH).

    Expect phổ biến:
        get_links_main(keywords_file, output_txt, project_name)

    Có thể mở rộng:
        get_links_main(keywords_file, output_txt, project_name, videos_per_keyword=4)
    """
    if len(args) < 3:
        raise ValueError(
            "get_links_main yêu cầu ít nhất 3 tham số: "
            "keywords_file, output_txt, project_name"
        )

    keywords_file = args[0]
    output_txt = args[1]
    project_name = args[2]  # hiện tại chỉ dùng để log

    # Default config
    videos_per_keyword = kwargs.get("videos_per_keyword", 4)

    # Cho phép truyền videos_per_keyword dạng positional (arg thứ 4)
    if len(args) >= 4 and isinstance(args[3], int):
        videos_per_keyword = args[3]

    print("[get_link] === START get_links_main ===")
    print(f"[get_link] keywords_file        = {keywords_file}")
    print(f"[get_link] output_txt           = {output_txt}")
    print(f"[get_link] project_name         = {project_name}")
    print(f"[get_link] videos_per_keyword   = {videos_per_keyword}")

    keywords = _read_keywords(keywords_file)
    print(f"[get_link] Loaded {len(keywords)} unique keywords (order preserved).")
    if not keywords:
        print("[get_link] Không có keyword nào, bỏ qua.")
        print("[get_link] === END get_links_main (NO KEYWORDS) ===")
        return

    # Ghi file link VIDEO
    total_video_links = _write_video_links_txt(
        output_txt=output_txt,
        keywords=keywords,
        videos_per_keyword=videos_per_keyword,
    )
    print(f"[get_link] Đã ghi {total_video_links} link video vào: {output_txt}")

    # Tự động sinh file link ẢNH từ link video (thumbnail YouTube)
    _auto_gen_image_links(output_txt)

    print("[get_link] === END get_links_main ===")


# =============================
#  CHO PHÉP CHẠY TỪ COMMAND LINE
# =============================

if __name__ == "__main__":
    # Ví dụ:
    #   python -m core.downloadTool.get_link data/naruto/list_name.txt data/naruto/dl_links.txt naruto
    cli_args = sys.argv[1:]
    if len(cli_args) < 3:
        print("Usage:")
        print("  python -m core.downloadTool.get_link "
              "<keywords_file> <output_txt> <project_name> [videos_per_keyword]")
        sys.exit(1)

    kf = cli_args[0]
    out_txt = cli_args[1]
    proj = cli_args[2]
    vpk = int(cli_args[3]) if len(cli_args) >= 4 else 4

    get_links_main(kf, out_txt, proj, vpk)
