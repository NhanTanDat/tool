import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None

# Path setup
THIS_FILE = os.path.abspath(__file__)
DOWNLOAD_TOOL_DIR = os.path.dirname(THIS_FILE)
CORE_DIR = os.path.dirname(DOWNLOAD_TOOL_DIR)
ROOT_DIR = os.path.dirname(CORE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Optional: nếu bạn có module sinh link ảnh riêng
try:
    from core.downloadTool.downImage import gen_image_links_from_yt_txt
except Exception:
    gen_image_links_from_yt_txt = None


def _env_int(name: str, default: str) -> int:
    try:
        return int((os.environ.get(name, default) or default).strip())
    except Exception:
        return int(default)


def _env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or default).strip()


# =============================
# CONFIG (mới)
# =============================
COOKIES_FILE = _env_str("YTDLP_COOKIES_FILE", "")
YTDLP_PLAYER_CLIENT = _env_str("YTDLP_PLAYER_CLIENT", "android").lower() or "android"

# Search tuning
SEARCH_MULTIPLIER = _env_int("SEARCH_MULTIPLIER", "8")     # lấy nhiều candidate hơn để chọn đủ VPK
SEARCH_MIN = _env_int("SEARCH_MIN", "20")                  # tối thiểu số video search mỗi keyword


def _read_keywords(keywords_file: str) -> List[str]:
    path = Path(keywords_file)
    if not path.exists():
        raise FileNotFoundError(f"keywords_file không tồn tại: {keywords_file}")

    seen = set()
    result: List[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        kw = raw.strip()
        if not kw or kw in seen:
            continue
        seen.add(kw)
        result.append(kw)
    return result


def _search_youtube_for_keyword(keyword: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Chỉ search và lấy url/title cơ bản (extract_flat) => nhanh, ít lỗi, không phụ thuộc subtitles.
    """
    if YoutubeDL is None:
        raise RuntimeError("yt_dlp chưa được cài. Cài: py -3.12 -m pip install -U yt-dlp")

    query = f"ytsearch{max_results}:{keyword}"
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "skip_download": True,
        "default_search": "ytsearch",
        "noplaylist": True,
        "extract_flat": True,
        "ignoreerrors": True,
        # giảm rủi ro warning do client/web
        "extractor_args": {"youtube": {"player_client": [YTDLP_PLAYER_CLIENT]}},
    }
    if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
        ydl_opts["cookiefile"] = COOKIES_FILE

    out: List[Dict[str, Any]] = []
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False) or {}
        for e in (info.get("entries") or []):
            if not isinstance(e, dict):
                continue
            url = e.get("url") or e.get("webpage_url")
            if not url:
                continue
            if not str(url).startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"
            out.append(
                {
                    "title": e.get("title") or "",
                    "url": url,
                }
            )
    return out


def _extract_video_id(url: str) -> Optional[str]:
    """
    Lấy video id từ nhiều dạng url:
    - https://www.youtube.com/watch?v=ID
    - https://youtu.be/ID
    - https://www.youtube.com/shorts/ID
    """
    if not url:
        return None

    # watch?v=
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)

    # youtu.be/ID
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)

    # /shorts/ID
    m = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)

    return None


def _fallback_gen_image_links_from_video_txt(video_txt: str, image_txt: Optional[str] = None) -> Optional[str]:
    """
    Fallback: nếu không import được gen_image_links_from_yt_txt
    => tự sinh thumbnail youtube theo video id.

    Output format: giữ nguyên group keyword (giống video txt)
    """
    in_path = Path(video_txt)
    if not in_path.exists():
        print(f"[get_link] WARN: video_txt không tồn tại: {video_txt}")
        return None

    if image_txt is None:
        base, _ = os.path.splitext(video_txt)
        image_txt = base + "_image.txt"

    lines_in = in_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lines_out: List[str] = []

    for raw in lines_in:
        line = raw.strip()
        if not line:
            lines_out.append("")
            continue

        # keyword header (không phải url)
        if not line.startswith("http"):
            lines_out.append(line)
            continue

        vid = _extract_video_id(line)
        if not vid:
            # không parse được id => bỏ qua hoặc giữ rỗng
            continue

        # Ưu tiên maxres (nếu có), còn không thì hq/mq vẫn ok.
        # Bạn chỉ cần link -> tool download của bạn tự xử lý 404 nếu maxres không tồn tại.
        thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
        lines_out.append(thumb)

    Path(image_txt).write_text("\n".join(lines_out), encoding="utf-8")
    print(f"[get_link] (fallback) Đã sinh link ảnh vào: {image_txt}")
    return image_txt


def _auto_gen_image_links(video_txt: str, image_txt: Optional[str] = None) -> Optional[str]:
    """
    Ưu tiên dùng module của bạn nếu có, không có thì fallback.
    """
    if gen_image_links_from_yt_txt is not None:
        if image_txt is None:
            base, _ = os.path.splitext(video_txt)
            image_txt = base + "_image.txt"
        try:
            total = gen_image_links_from_yt_txt(video_txt, image_txt)
            print(f"[get_link] Đã sinh {total} link ảnh vào: {image_txt}")
            return image_txt
        except Exception as e:
            print(f"[get_link] WARN: gen_image_links_from_yt_txt lỗi: {e} => dùng fallback")

    return _fallback_gen_image_links_from_video_txt(video_txt, image_txt)


def _write_video_links_txt(output_txt: str, keywords: List[str], videos_per_keyword: int) -> int:
    """
    Ghi file theo format group:
      keyword
      url1
      url2
      ...

      keyword2
      url1
      ...
    """
    total_links = 0
    lines: List[str] = []

    global_seen: set[str] = set()

    for kw in keywords:
        search_n = max(videos_per_keyword * SEARCH_MULTIPLIER, SEARCH_MIN)
        candidates = _search_youtube_for_keyword(kw, max_results=search_n)

        urls_ok: List[str] = []
        for c in candidates:
            url = (c.get("url") or "").strip()
            if not url:
                continue

            # tránh trùng toàn cục
            if url in global_seen:
                continue

            global_seen.add(url)
            urls_ok.append(url)

            if len(urls_ok) >= videos_per_keyword:
                break

        # luôn ghi header keyword
        lines.append(kw)
        for url in urls_ok:
            lines.append(url)
            total_links += 1
        lines.append("")

        if not urls_ok:
            print(f"[get_link][WARN] No videos found for keyword: {kw}")

    Path(output_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(output_txt).write_text("\n".join(lines), encoding="utf-8")
    return total_links


def get_links_main(*args, **kwargs) -> None:
    if len(args) < 3:
        raise ValueError("get_links_main yêu cầu: keywords_file, output_txt, project_name")

    keywords_file = args[0]
    output_txt = args[1]
    project_name = args[2]

    videos_per_keyword = kwargs.get("videos_per_keyword", 4)
    if len(args) >= 4 and isinstance(args[3], int):
        videos_per_keyword = args[3]

    print("[get_link] === START get_links_main ===")
    print(f"[get_link] keywords_file        = {keywords_file}")
    print(f"[get_link] output_txt           = {output_txt}")
    print(f"[get_link] project_name         = {project_name}")
    print(f"[get_link] videos_per_keyword   = {videos_per_keyword}")
    print(f"[get_link] MODE: NO subtitle filter | NO VTT probe | search-only")

    keywords = _read_keywords(keywords_file)
    print(f"[get_link] Loaded {len(keywords)} unique keywords (order preserved).")
    if not keywords:
        print("[get_link] Không có keyword nào.")
        return

    total_video_links = _write_video_links_txt(output_txt, keywords, videos_per_keyword)
    print(f"[get_link] Đã ghi {total_video_links} link video vào: {output_txt}")

    _auto_gen_image_links(output_txt)
    print("[get_link] === END get_links_main ===")


if __name__ == "__main__":
    cli_args = sys.argv[1:]
    if len(cli_args) < 3:
        print("Usage:")
        print("  python -m core.downloadTool.get_link <keywords_file> <output_txt> <project_name> [videos_per_keyword]")
        sys.exit(1)

    kf = cli_args[0]
    out_txt = cli_args[1]
    proj = cli_args[2]
    vpk = int(cli_args[3]) if len(cli_args) >= 4 else 4
    get_links_main(kf, out_txt, proj, vpk)
