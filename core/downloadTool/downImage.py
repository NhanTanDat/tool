import os
import sys
import re
import urllib.request
import urllib.parse
from typing import Optional, Dict, List

# ❌ KHÔNG gọi AI ở đây. Lọc ảnh bằng AI nên để ở bước sinh link (get_link.py), 
# không để ở bước download.
# from core.ai.select_items import select_images_with_ai
# filtered = select_images_with_ai(keyword, image_candidates, max_keep=images_per_keyword)

# Try relative import first (when running as a module), then fallback to absolute
try:
    from .folder_handle import create_folder  # type: ignore
except Exception:
    THIS_FILE = os.path.abspath(__file__)
    DOWNLOAD_TOOL_DIR = os.path.dirname(THIS_FILE)
    CORE_DIR = os.path.dirname(DOWNLOAD_TOOL_DIR)
    ROOT_DIR = os.path.dirname(CORE_DIR)
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    try:
        from core.downloadTool.folder_handle import create_folder  # type: ignore
    except Exception:
        create_folder = None  # Will fallback to os.makedirs


def _sanitize_filename(name: str) -> str:
    """Return a Windows-safe filename by removing invalid characters and trimming.

    - Remove control chars, invalid path chars: \ / : * ? " < > |
    - Collapse whitespace, trim trailing spaces and dots
    - Limit to 255 chars
    """
    if not isinstance(name, str):
        name = str(name)
    # Remove control chars
    name = ''.join(ch for ch in name if ord(ch) >= 32)
    # Remove invalid Windows filename chars
    name = ''.join(ch for ch in name if ch not in '<>:"/\\|?*')
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove trailing dots/spaces
    name = name.rstrip(' .')
    if not name:
        name = 'image'
    if len(name) > 255:
        name = name[:255].rstrip(' .')
    return name


def _extension_from_content_type(ct: str) -> Optional[str]:
    if not ct:
        return None
    ct = ct.lower()
    if not ct.startswith('image/'):
        return None
    sub = ct.split('/', 1)[1]
    mapping = {
        'jpeg': 'jpg',
        'svg+xml': 'svg',
        'x-icon': 'ico',
        'vnd.microsoft.icon': 'ico',
        'webp': 'webp',
        'png': 'png',
        'gif': 'gif',
        'bmp': 'bmp',
        'tiff': 'tif'
    }
    return mapping.get(sub, sub)


def _filename_from_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        name = os.path.basename(parsed.path) or 'image'
        name = name.split('?')[0].split('#')[0]
        return _sanitize_filename(name)
    except Exception:
        return 'image'


def download_image(
    image_url: str,
    save_dir: str,
    filename: Optional[str] = None,
    referer: Optional[str] = None,
    timeout: int = 20
) -> str:
    """Download an image from a final image URL to the specified directory.

    Args:
        image_url: The final URL of the image (e.g., ending with .jpg/.png or image CDN URL).
        save_dir: Directory path to save the image. Will be created if not exists.
        filename: Optional target filename. If missing or without extension, will be inferred.
        referer: Optional Referer header (some origins require it). If None, omitted.
        timeout: Request timeout in seconds.

    Returns:
        The absolute file path of the saved image.
    """
    if not image_url:
        raise ValueError('image_url is required')

    os.makedirs(save_dir, exist_ok=True)

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        )
    }
    if referer:
        headers['Referer'] = referer

    req = urllib.request.Request(image_url, headers=headers, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ct = resp.headers.get('Content-Type', '')
        # Decide filename
        if not filename or not os.path.splitext(filename)[1]:
            base = _filename_from_url(image_url)
            ext = os.path.splitext(filename)[1] if filename else ''
            if not ext:
                infer = _extension_from_content_type(ct)
                if infer:
                    ext = '.' + infer
            filename = base + (ext if ext else '')
        filename = _sanitize_filename(filename)

        target_path = os.path.abspath(os.path.join(save_dir, filename))
        base_no_ext, ext_final = os.path.splitext(target_path)
        counter = 1
        while os.path.exists(target_path):
            target_path = f"{base_no_ext}_{counter}{ext_final}"
            counter += 1

        with open(target_path, 'wb') as fout:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                fout.write(chunk)

    return target_path


def parse_links_from_txt(file_path: str) -> Dict[str, List[str]]:
    """Parse links definition file into {group: [links...]}

    Compatible with down_by_yt.parse_links_from_txt:
      - Header lines: "<number> <name>" or plain name (no https)
      - Link lines: start with https://
      - Group names normalized by replacing spaces with underscores
    """
    groups: Dict[str, List[str]] = {}
    current: Optional[str] = None
    synthetic_index = 1
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('https://'):
                if current is None:
                    current = f"group_{synthetic_index}"
                    groups[current] = []
                    synthetic_index += 1
                groups[current].append(line)
                continue
            # header
            if ' ' in line and line.split(' ', 1)[0].isdigit():
                _, remainder = line.split(' ', 1)
                name = remainder
            else:
                name = line
            name = "_".join(name.split())
            current = name
            groups.setdefault(current, [])
    return groups


def _ensure_folder(base: str, name: str) -> str:
    """Create folder base/name. Uses create_folder if available, else os.makedirs."""
    if create_folder:
        create_folder(base, name)
    else:
        os.makedirs(os.path.join(base, name), exist_ok=True)
    return os.path.join(base, name)


def download_images_batch(
    links_dict: Dict[str, List[str]],
    parent_folder: str,
    referer: Optional[str] = None,
    timeout: int = 20
):
    """Download all images grouped by key into subfolders under parent_folder.

    - Subfolder name for each key: img_<key> (append 'img_' to the beginning of folder name)
    - Creates folders if missing
    - Uses direct HTTP requests (urllib) to download images
    """
    os.makedirs(parent_folder, exist_ok=True)

    for key, links in links_dict.items():
        sub_name = f"img_{key}"
        sub_dir = _ensure_folder(parent_folder, sub_name)
        print(f"[downImage] Downloading {len(links)} images into: {sub_dir}")
        for idx, url in enumerate(links, start=1):
            try:
                saved_path = download_image(
                    url,
                    sub_dir,
                    filename=None,
                    referer=referer,
                    timeout=timeout,
                )
                print(f"[downImage] ({idx}/{len(links)}) Saved: {saved_path}")
            except Exception as e:
                print(f"[downImage] ({idx}/{len(links)}) Failed: {url} -> {e}")


def download_images_main(
    parent_folder: str,
    txt_name: str,
    referer: Optional[str] = None,
    timeout: int = 20
) -> int:
    """Entry similar to down_by_yt.download_main but for images via HTTP.

    - Reads groups and image URLs from txt_name
    - Creates subfolders 'img_<group>'
    - Downloads images directly
    Returns number of images attempted.
    """
    groups = parse_links_from_txt(txt_name)
    if not groups:
        print(f"[downImage] WARN: No groups parsed from {txt_name}")
        return 0
    download_images_batch(groups, parent_folder, referer=referer, timeout=timeout)
    return sum(len(v) for v in groups.values())


# ==============================
#  PHẦN MỚI: LẤY ẢNH TỪ LINK YOUTUBE (OPTIONAL)
# ==============================

def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video id from URL.

    Hỗ trợ:
      - https://www.youtube.com/watch?v=VIDEOID
      - https://youtu.be/VIDEOID
    """
    m = re.search(r"(?:v=|be/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else None


def _build_youtube_thumbs(video_id: str) -> List[str]:
    """Return list thumbnail URLs for a given YouTube video id.

    Thứ tự:
      - maxresdefault
      - hqdefault
    """
    return [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ]


def _write_groups_to_txt(groups: Dict[str, List[str]], file_path: str) -> int:
    """Write {group: [urls]} to txt in the same format parse_links_from_txt expects."""
    total = 0
    with open(file_path, "w", encoding="utf-8") as f:
        for key, links in groups.items():
            if not links:
                continue
            # header: chuyển _ về space cho dễ đọc, khi parse lại vẫn convert ngược
            header = key.replace("_", " ")
            f.write(header + "\n")
            for url in links:
                f.write(url + "\n")
                total += 1
            f.write("\n")
    return total


def gen_image_links_from_yt_txt(
    video_txt_path: str,
    out_txt_path: Optional[str] = None
) -> int:
    """Đọc file link VIDEO (YouTube) và sinh file link ẢNH (thumbnail).

    - Input:  file txt giống dl_links.txt (link video, có group)
    - Output: file txt chứa url thumbnail YouTube, group giống input.

    Returns:
        Số lượng URL ảnh đã ghi ra file.
    """
    if out_txt_path is None:
        base, ext = os.path.splitext(video_txt_path)
        out_txt_path = base + "_image.txt"  # ví dụ dl_links_image.txt

    video_groups = parse_links_from_txt(video_txt_path)
    if not video_groups:
        print(f"[downImage] WARN: No video groups parsed from {video_txt_path}")
        return 0

    image_groups: Dict[str, List[str]] = {}

    for key, links in video_groups.items():
        for url in links:
            vid = _extract_youtube_id(url)
            if not vid:
                print(f"[downImage] WARN: Cannot parse YouTube ID from: {url}")
                continue
            thumbs = _build_youtube_thumbs(vid)
            image_groups.setdefault(key, []).extend(thumbs)

    total = _write_groups_to_txt(image_groups, out_txt_path)
    print(f"[downImage] Generated image links file: {out_txt_path} ({total} urls)")
    return total


if __name__ == '__main__':
    # Usage examples:
    # 1) Download from TXT groups:
    #    python -m core.downloadTool.downImage <parent_folder> <txt_name>
    # 2) Download single image:
    #    python -m core.downloadTool.downImage --single <image_url> <save_dir> [filename]
    # 3) Generate image links from YouTube links:
    #    python -m core.downloadTool.downImage --from-yt <video_txt> [image_txt]
    args = sys.argv[1:]
    if not args:
        print('Usage:')
        print('  python -m core.downloadTool.downImage <parent_folder> <txt_name>')
        print('  python -m core.downloadTool.downImage --single <image_url> <save_dir> [filename]')
        print('  python -m core.downloadTool.downImage --from-yt <video_txt> [image_txt]')
        sys.exit(1)

    if args[0] == '--single':
        if len(args) < 3:
            print('Usage: python -m core.downloadTool.downImage --single <image_url> <save_dir> [filename]')
            sys.exit(1)
        url = args[1]
        out_dir = args[2]
        fname = args[3] if len(args) >= 4 else None
        saved = download_image(url, out_dir, filename=fname)
        print('Saved to:', saved)

    elif args[0] == '--from-yt':
        if len(args) < 2:
            print('Usage: python -m core.downloadTool.downImage --from-yt <video_txt> [image_txt]')
            sys.exit(1)
        video_txt = args[1]
        image_txt = args[2] if len(args) >= 3 else None
        total_links = gen_image_links_from_yt_txt(video_txt, image_txt)
        print('Generated image links:', total_links)

    else:
        if len(args) < 2:
            print('Usage: python -m core.downloadTool.downImage <parent_folder> <txt_name>')
            sys.exit(1)
        parent = args[0]
        txt = args[1]
        total = download_images_main(parent, txt)
        print('Attempted images:', total)
