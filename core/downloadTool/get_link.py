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


def _env_bool(name: str, default: str = "0") -> bool:
    v = (os.environ.get(name, default) or default).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _coerce_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        if isinstance(v, int):
            return v
        s = str(v).strip()
        if not s:
            return default
        return int(s)
    except Exception:
        return default


# =============================
# CONFIG
# =============================
COOKIES_FILE = _env_str("YTDLP_COOKIES_FILE", "")
YTDLP_PLAYER_CLIENT = _env_str("YTDLP_PLAYER_CLIENT", "android").lower() or "android"

# Search tuning
SEARCH_MULTIPLIER = _env_int("SEARCH_MULTIPLIER", "8")     # lấy nhiều candidate hơn để chọn đủ VPK
SEARCH_MIN = _env_int("SEARCH_MIN", "20")                  # tối thiểu số video search mỗi keyword

# Dedupe toàn cục (tránh trùng video giữa các keyword). Nếu muốn luôn đủ 20/keyword thì có thể tắt:
GLOBAL_DEDUP = _env_bool("GLOBAL_DEDUP", "1")


def _strip_index_prefix(line: str) -> str:
    """
    "1 keyword" -> "keyword"
    """
    s = (line or "").strip()
    if not s:
        return ""
    parts = s.split(maxsplit=1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].strip()
    return s


def _read_keywords(keywords_file: str) -> List[str]:
    """
    Đọc keyword từ list_name.txt:
    - Bỏ số đầu dòng nếu có ("1 xxx")
    - Bỏ dòng rỗng
    - Bỏ dòng là URL
    - Giữ thứ tự
    """
    path = Path(keywords_file)
    if not path.exists():
        raise FileNotFoundError(f"keywords_file không tồn tại: {keywords_file}")

    seen = set()
    result: List[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            continue

        kw = _strip_index_prefix(line)
        if not kw:
            continue
        if kw in seen:
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
            out.append({"title": e.get("title") or "", "url": url})
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

    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)

    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)

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

        # keyword header
        if not line.startswith("http"):
            lines_out.append(line)
            continue

        vid = _extract_video_id(line)
        if not vid:
            continue

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


def _write_video_links_txt(
    output_txt: str,
    keywords: List[str],
    videos_per_keyword: int,
    *,
    global_dedup: bool = True,
) -> int:
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
        # search nhiều hơn để lấy đủ VPK
        search_n = max(int(videos_per_keyword) * SEARCH_MULTIPLIER, SEARCH_MIN)
        candidates = _search_youtube_for_keyword(kw, max_results=search_n)

        urls_ok: List[str] = []
        local_seen: set[str] = set()

        for c in candidates:
            url = (c.get("url") or "").strip()
            if not url:
                continue

            # tránh trùng trong cùng keyword
            if url in local_seen:
                continue
            local_seen.add(url)

            # tránh trùng toàn cục (tuỳ chọn)
            if global_dedup and url in global_seen:
                continue

            if global_dedup:
                global_seen.add(url)

            urls_ok.append(url)

            if len(urls_ok) >= int(videos_per_keyword):
                break

        # luôn ghi header keyword
        lines.append(kw)
        for url in urls_ok:
            lines.append(url)
            total_links += 1
        lines.append("")

        if len(urls_ok) < int(videos_per_keyword):
            print(
                f"[get_link][WARN] keyword='{kw}' chỉ lấy được {len(urls_ok)}/{videos_per_keyword} link "
                f"(search_n={search_n}, global_dedup={global_dedup})"
            )

    Path(output_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(output_txt).write_text("\n".join(lines), encoding="utf-8")
    return total_links


def _write_image_links_txt_from_keywords(
    output_txt: str,
    keywords: List[str],
    images_per_keyword: int,
    *,
    global_dedup: bool = True,
) -> int:
    """
    Tạo file ảnh trực tiếp theo keyword:
      keyword
      thumb1
      thumb2
      ...
    """
    total = 0
    lines: List[str] = []
    global_seen: set[str] = set()

    for kw in keywords:
        search_n = max(int(images_per_keyword) * SEARCH_MULTIPLIER, SEARCH_MIN)
        candidates = _search_youtube_for_keyword(kw, max_results=search_n)

        imgs_ok: List[str] = []
        local_seen: set[str] = set()

        for c in candidates:
            url = (c.get("url") or "").strip()
            vid = _extract_video_id(url)
            if not vid:
                continue

            thumb = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"

            if thumb in local_seen:
                continue
            local_seen.add(thumb)

            if global_dedup and thumb in global_seen:
                continue
            if global_dedup:
                global_seen.add(thumb)

            imgs_ok.append(thumb)
            if len(imgs_ok) >= int(images_per_keyword):
                break

        lines.append(kw)
        lines.extend(imgs_ok)
        lines.append("")
        total += len(imgs_ok)

        if len(imgs_ok) < int(images_per_keyword):
            print(
                f"[get_link][WARN] IMAGE keyword='{kw}' chỉ lấy được {len(imgs_ok)}/{images_per_keyword} ảnh "
                f"(search_n={search_n}, global_dedup={global_dedup})"
            )

    Path(output_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(output_txt).write_text("\n".join(lines), encoding="utf-8")
    return total


def get_links_main(*args, **kwargs) -> None:
    """
    Tương thích nhiều kiểu gọi:
    - get_links_main(keywords_file, output_txt, project_name, 20)
    - get_links_main(keywords_file, output_txt, project_name, videos_per_keyword=20)
    - get_links_main(keywords_file, output_txt, project_name, max_per_keyword=20)  # code cũ
    """
    if len(args) < 3:
        raise ValueError("get_links_main yêu cầu: keywords_file, output_txt, project_name")

    keywords_file = args[0]
    output_txt = args[1]
    project_name = args[2]

    # ✅ lấy VPK từ nhiều nguồn (ưu tiên args[3])
    videos_per_keyword = 4
    if len(args) >= 4:
        videos_per_keyword = _coerce_int(args[3], videos_per_keyword)

    # kwargs synonyms
    if "videos_per_keyword" in kwargs:
        videos_per_keyword = _coerce_int(kwargs.get("videos_per_keyword"), videos_per_keyword)
    if "max_per_keyword" in kwargs:
        videos_per_keyword = _coerce_int(kwargs.get("max_per_keyword"), videos_per_keyword)
    if "vpk" in kwargs:
        videos_per_keyword = _coerce_int(kwargs.get("vpk"), videos_per_keyword)

    if videos_per_keyword <= 0:
        videos_per_keyword = 1

    global_dedup = bool(kwargs.get("global_dedup", GLOBAL_DEDUP))

    print("[get_link] === START get_links_main ===")
    print(f"[get_link] keywords_file        = {keywords_file}")
    print(f"[get_link] output_txt           = {output_txt}")
    print(f"[get_link] project_name         = {project_name}")
    print(f"[get_link] videos_per_keyword   = {videos_per_keyword}")
    print(f"[get_link] global_dedup         = {global_dedup}")
    print(f"[get_link] MODE: search-only (extract_flat)")

    keywords = _read_keywords(keywords_file)
    print(f"[get_link] Loaded {len(keywords)} unique keywords (order preserved).")
    if not keywords:
        print("[get_link] Không có keyword nào.")
        return

    total_video_links = _write_video_links_txt(
        output_txt,
        keywords,
        int(videos_per_keyword),
        global_dedup=global_dedup,
    )
    print(f"[get_link] Đã ghi {total_video_links} link video vào: {output_txt}")

    # auto create image links: dl_links.txt => dl_links_image.txt
    _auto_gen_image_links(output_txt)
    print("[get_link] === END get_links_main ===")


def get_links_main_video(
    keywords_file: str,
    output_txt: str,
    project_name: str,
    *,
    videos_per_keyword: int = 4,
    max_per_keyword: Optional[int] = None,
    vpk: Optional[int] = None,
    global_dedup: Optional[bool] = None,
    **kwargs,
) -> None:
    """
    Wrapper cho mode VIDEO (GUI hay gọi).
    """
    if max_per_keyword is not None:
        videos_per_keyword = int(max_per_keyword)
    if vpk is not None:
        videos_per_keyword = int(vpk)

    if global_dedup is None:
        global_dedup = GLOBAL_DEDUP

    get_links_main(
        keywords_file,
        output_txt,
        project_name,
        int(videos_per_keyword),
        global_dedup=bool(global_dedup),
        **kwargs,
    )


def get_links_main_image(
    keywords_file: str,
    output_txt: str,
    project_name: str,
    *,
    images_per_keyword: int = 10,
    global_dedup: Optional[bool] = None,
    **kwargs,
) -> None:
    """
    Tạo file ảnh theo keyword trực tiếp (không cần dl_links.txt trước).
    Output group giống video.
    """
    if global_dedup is None:
        global_dedup = GLOBAL_DEDUP

    print("[get_link] === START get_links_main_image ===")
    print(f"[get_link] keywords_file        = {keywords_file}")
    print(f"[get_link] output_txt           = {output_txt}")
    print(f"[get_link] project_name         = {project_name}")
    print(f"[get_link] images_per_keyword   = {images_per_keyword}")
    print(f"[get_link] global_dedup         = {bool(global_dedup)}")

    keywords = _read_keywords(keywords_file)
    if not keywords:
        print("[get_link] Không có keyword nào.")
        return

    total = _write_image_links_txt_from_keywords(
        output_txt,
        keywords,
        int(images_per_keyword),
        global_dedup=bool(global_dedup),
    )
    print(f"[get_link] Đã ghi {total} link ảnh vào: {output_txt}")
    print("[get_link] === END get_links_main_image ===")


if __name__ == "__main__":
    cli_args = sys.argv[1:]
    if len(cli_args) < 3:
        print("Usage:")
        print("  python -m core.downloadTool.get_link <keywords_file> <output_txt> <project_name> [videos_per_keyword]")
        print("Env:")
        print("  GLOBAL_DEDUP=1/0, SEARCH_MULTIPLIER, SEARCH_MIN, YTDLP_COOKIES_FILE, YTDLP_PLAYER_CLIENT")
        sys.exit(1)

    kf = cli_args[0]
    out_txt = cli_args[1]
    proj = cli_args[2]
    vpk = _coerce_int(cli_args[3], 4) if len(cli_args) >= 4 else 4
    get_links_main(kf, out_txt, proj, int(vpk))
