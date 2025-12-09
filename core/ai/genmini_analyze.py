# core/ai/genmini_analyze.py

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# ======================================================
# ĐỌC KEY TỪ FILE .env Ở THƯ MỤC ROOT
# ======================================================

# genmini_analyze.py nằm ở core/ai/ → root = parent của core
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"


def _load_env_from_dotenv(env_path: Path = ENV_PATH) -> None:
    """
    Đọc file .env (nếu có) và set vào os.environ.
    Format mỗi dòng:
        KEY=VALUE
    Bỏ qua dòng trống và dòng bắt đầu bằng '#'.
    """
    if not env_path.exists():
        return

    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # Không ghi đè nếu đã có trong môi trường
            if key not in os.environ:
                os.environ[key] = value
    except Exception as e:
        # Không raise để tránh crash toàn bộ tool, chỉ log nhẹ
        print(f"[genmini_analyze] CẢNH BÁO: lỗi đọc .env: {e}")


# Load .env vào os.environ (nếu có)
_load_env_from_dotenv()

# Ưu tiên GENMINI_API_KEY, fallback sang GEMINI_API_KEY (nếu bạn dùng chung)
GENMINI_API_KEY = (
    os.environ.get("GENMINI_API_KEY")
    or os.environ.get("GEMINI_API_KEY")
    or ""
)


# ======================================================
# ĐỌC dl_links.txt
# ======================================================

def read_dl_links(dl_links_path: str) -> Dict[str, List[str]]:
    """Đọc dl_links.txt → { keyword: [url1, url2, ...] }."""
    path = Path(dl_links_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy dl_links.txt: {dl_links_path}")

    groups: Dict[str, List[str]] = {}
    current_kw: Optional[str] = None

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            current_kw = None
            continue

        if line.startswith("http://") or line.startswith("https://"):
            if current_kw is None:
                continue
            groups.setdefault(current_kw, []).append(line)
        else:
            current_kw = line
            groups.setdefault(current_kw, [])

    return groups


# ======================================================
# GỌI GENMINI CHO TỪNG VIDEO (MOCK / TODO)
# ======================================================

def analyze_video_with_genmini(
    video_url: str,
    keyword: str,
    character: Optional[str] = None,
    max_segments: int = 8,
) -> List[Dict[str, Any]]:
    """
    Gọi Genmini để lấy list segments: [{start_sec, end_sec, confidence}, ...].

    TODO: Bạn cần chỉnh lại hàm này cho đúng API thật (requests.post tới Genmini),
    ví dụ:
        - truyền video_url
        - truyền keyword / character
        - parse JSON trả về, map sang list dict như dưới.

    Hiện tại đang MOCK để test pipeline.
    """
    if not GENMINI_API_KEY:
        raise RuntimeError(
            "Chưa có GENMINI_API_KEY / GEMINI_API_KEY.\n"
            "Hãy tạo file .env ở thư mục root và thêm dòng:\n"
            "    GENMINI_API_KEY=your_real_key_here"
        )

    # TODO: thay bằng gọi API thật
    # Ví dụ:
    #   resp = requests.post(..., headers={"Authorization": f"Bearer {GENMINI_API_KEY}"}, json={...})
    #   data = resp.json()
    #   return [{"start_sec": ..., "end_sec": ..., "confidence": ...}, ...]
    #
    # Tạm thời mock vài đoạn cho dễ test:
    mock_segments = [
        {"start_sec": 10.0, "end_sec": 13.0, "confidence": 0.9},
        {"start_sec": 30.0, "end_sec": 35.0, "confidence": 0.82},
    ]
    return mock_segments[:max_segments]


# ======================================================
# CHẠY GENMINI CHO CẢ PROJECT → segments_genmini.json
# ======================================================

def run_genmini_for_project(
    dl_links_path: str,
    segments_json_path: str,
    max_segments_per_video: int = 8,
) -> int:
    """
    Đọc dl_links.txt → gọi Genmini cho từng link → ghi segments_genmini.json.
    Trả về số record (keyword+video) có segment.
    """
    groups = read_dl_links(dl_links_path)
    results: List[Dict[str, Any]] = []

    for kw, urls in groups.items():
        if not urls:
            continue

        for vid_idx, url in enumerate(urls):
            segments = analyze_video_with_genmini(
                video_url=url,
                keyword=kw,
                character=None,
                max_segments=max_segments_per_video,
            )
            if not segments:
                continue

            results.append({
                "keyword": kw,
                "video_url": url,
                "video_index": vid_idx,
                "segments": segments,
            })

    Path(segments_json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(segments_json_path).write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return len(results)


# ======================================================
# ĐỔI segments_genmini.json → timeline_export_merged.csv
# ======================================================

def build_timeline_csv_from_segments(
    segments_json_path: str,
    timeline_csv_path: str,
    only_character: Optional[str] = None,
) -> int:
    """
    Đổi segments_genmini.json → timeline_export_merged.csv

    CSV format (PHÙ HỢP cutAndPush.jsx):

        scene_index,character,bin_name,video_index,src_start,src_end,duration_sec

    - character: dùng keyword (có thể là tên nhân vật)
    - bin_name : keyword chuyển thành snake_case để map tên bin trong Premiere
    - video_index: index của link trong dl_links.txt (0-based)
    - src_start, src_end: thời gian trên video gốc (giây)
    - duration_sec: e - s
    """
    data = json.loads(Path(segments_json_path).read_text(encoding="utf-8"))
    lines: List[str] = []
    header = "scene_index,character,bin_name,video_index,src_start,src_end,duration_sec"
    lines.append(header)

    scene_idx = 0

    for item in data:
        kw = item["keyword"]
        video_index = item["video_index"]
        segments = item["segments"]

        # Có thể coi keyword là tên nhân vật / chủ đề
        character = kw
        bin_name = kw.replace(" ", "_")

        if only_character:
            if character.lower().strip() != only_character.lower().strip():
                continue

        for seg in segments:
            s = float(seg["start_sec"])
            e = float(seg["end_sec"])
            if e <= s:
                continue
            duration = e - s

            lines.append(
                f"{scene_idx},{character},{bin_name},{video_index},{s:.3f},{e:.3f},{duration:.3f}"
            )
            scene_idx += 1

    Path(timeline_csv_path).write_text("\n".join(lines), encoding="utf-8")
    return scene_idx
