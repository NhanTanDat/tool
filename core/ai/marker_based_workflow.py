"""
marker_based_workflow.py

Workflow hoàn chỉnh dựa trên Markers:
1. Đọc keywords từ track3_keywords.json (output từ extractTrack3Keywords.jsx)
2. Tìm kiếm YouTube và download videos theo keywords
3. AI phân tích videos và match với keywords
4. Sinh timeline để cắt và push vào V4
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

# Add project root to path
THIS_DIR = Path(__file__).parent.resolve()
CORE_DIR = THIS_DIR.parent
ROOT_DIR = CORE_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load .env
ENV_PATH = ROOT_DIR / ".env"

def _load_env_file():
    if not ENV_PATH.exists():
        return
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)
    except Exception as e:
        print(f"[WARN] Cannot read .env: {e}")

_load_env_file()


class MarkerBasedWorkflow:
    """
    Workflow dựa trên markers:
    Step 1: Đọc keywords từ markers (đã chạy từ JSX)
    Step 2: Search & Download videos theo keywords
    Step 3: AI phân tích và match
    Step 4: Sinh timeline / cut list
    """

    def __init__(
        self,
        project_path: str,
        data_folder: str,
        resource_folder: str,
        gemini_api_key: Optional[str] = None,
        videos_per_keyword: int = 5,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.project_path = Path(project_path)
        self.data_folder = Path(data_folder)
        self.resource_folder = Path(resource_folder)
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.videos_per_keyword = videos_per_keyword
        self.log_callback = log_callback or print

        # File paths
        self.keywords_json = self.data_folder / "track3_keywords.json"
        self.dl_links_txt = self.data_folder / "dl_links.txt"
        self.segments_json = self.data_folder / "segments_genmini.json"
        self.timeline_csv = self.data_folder / "timeline_export_merged.csv"
        self.cut_list_json = self.data_folder / "cut_list.json"

    def log(self, msg: str):
        self.log_callback(msg)

    def load_keywords(self) -> List[Dict[str, Any]]:
        """Load keywords từ track3_keywords.json"""
        if not self.keywords_json.exists():
            raise FileNotFoundError(f"Không tìm thấy: {self.keywords_json}")

        with open(self.keywords_json, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        return data.get("keywords", [])

    def step1_check_keywords(self) -> bool:
        """
        Bước 1: Kiểm tra keywords đã được đọc từ markers
        """
        self.log("\n=== BƯỚC 1: Kiểm tra Keywords ===")

        if not self.keywords_json.exists():
            self.log(f"❌ Không tìm thấy: {self.keywords_json}")
            self.log("   Hãy chạy 'Đọc Markers' trước!")
            return False

        try:
            keywords = self.load_keywords()
            self.log(f"✓ Tìm thấy {len(keywords)} keywords:")
            for kw in keywords[:5]:  # Show first 5
                self.log(f"   - {kw.get('keyword', '')} @ {kw.get('start_timecode', '')}")
            if len(keywords) > 5:
                self.log(f"   ... và {len(keywords) - 5} keywords khác")
            return True
        except Exception as e:
            self.log(f"❌ Lỗi đọc keywords: {e}")
            return False

    def step2_search_and_download(self) -> bool:
        """
        Bước 2: Tìm kiếm YouTube và download videos
        """
        self.log("\n=== BƯỚC 2: Search & Download Videos ===")

        try:
            keywords = self.load_keywords()
        except Exception as e:
            self.log(f"❌ Lỗi load keywords: {e}")
            return False

        # Extract keyword strings
        keyword_list = [kw.get("keyword", "") for kw in keywords if kw.get("keyword")]

        if not keyword_list:
            self.log("❌ Không có keyword nào")
            return False

        self.log(f"Keywords: {keyword_list}")

        # Import search function
        try:
            from core.downloadTool.get_link import _search_youtube_for_keyword
        except ImportError as e:
            self.log(f"❌ Không import được get_link: {e}")
            return False

        # Search và tạo dl_links.txt
        self.log(f"\n🔍 Đang tìm kiếm videos cho {len(keyword_list)} keywords...")
        self.log(f"   Videos per keyword: {self.videos_per_keyword}")

        lines = []
        total_links = 0
        global_seen = set()

        for i, kw in enumerate(keyword_list):
            self.log(f"\n[{i+1}/{len(keyword_list)}] Searching: {kw}")

            try:
                # Search nhiều hơn để có đủ lựa chọn
                search_n = max(self.videos_per_keyword * 5, 20)
                candidates = _search_youtube_for_keyword(kw, max_results=search_n)

                urls_ok = []
                for c in candidates:
                    url = c.get("url", "").strip()
                    if not url or url in global_seen:
                        continue
                    global_seen.add(url)
                    urls_ok.append(url)
                    if len(urls_ok) >= self.videos_per_keyword:
                        break

                # Write to lines
                lines.append(kw)
                for url in urls_ok:
                    lines.append(url)
                    total_links += 1
                lines.append("")

                self.log(f"   ✓ Tìm được {len(urls_ok)} videos")

            except Exception as e:
                self.log(f"   ❌ Lỗi: {e}")
                lines.append(kw)
                lines.append("")

        # Write dl_links.txt
        self.dl_links_txt.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"\n✓ Đã lưu {total_links} links vào: {self.dl_links_txt}")

        # Download videos
        self.log("\n📥 Đang download videos...")

        try:
            from core.downloadTool.down_by_yt import download_all_from_links_txt

            # Ensure resource folder exists
            self.resource_folder.mkdir(parents=True, exist_ok=True)

            count = download_all_from_links_txt(
                links_txt=str(self.dl_links_txt),
                output_dir=str(self.resource_folder),
                dtype="mp4",
            )
            self.log(f"✓ Đã download {count} videos")
            return count > 0

        except ImportError:
            self.log("⚠ Không import được download function")
            self.log(f"   Chạy thủ công: yt-dlp với file {self.dl_links_txt}")
            return True  # Links đã được tạo
        except Exception as e:
            self.log(f"❌ Lỗi download: {e}")
            return False

    def step3_ai_analyze(self) -> bool:
        """
        Bước 3: AI phân tích videos và match với keywords
        """
        self.log("\n=== BƯỚC 3: AI Phân Tích Videos ===")

        if not self.gemini_api_key:
            self.log("❌ Không có GEMINI_API_KEY!")
            self.log(f"   Thêm vào .env: {ENV_PATH}")
            return False

        key_preview = self.gemini_api_key[:8] + "..." + self.gemini_api_key[-4:]
        self.log(f"✓ API Key: {key_preview}")

        try:
            from core.ai.genmini_analyze import (
                run_genmini_for_project,
                build_timeline_csv_from_segments,
            )
        except ImportError as e:
            self.log(f"❌ Không import được genmini_analyze: {e}")
            return False

        # Check dl_links.txt exists
        if not self.dl_links_txt.exists():
            self.log(f"❌ Không tìm thấy: {self.dl_links_txt}")
            return False

        self.log("\n🤖 Đang phân tích videos bằng Gemini AI...")

        try:
            num_items = run_genmini_for_project(
                dl_links_path=str(self.dl_links_txt),
                segments_json_path=str(self.segments_json),
                max_segments_per_video=8,
            )
            self.log(f"✓ Đã phân tích {num_items} videos")

            if num_items == 0:
                self.log("⚠ Không có segment nào được trả về")
                return False

            # Build timeline CSV
            self.log("\n📊 Đang sinh timeline...")
            num_scenes = build_timeline_csv_from_segments(
                segments_json_path=str(self.segments_json),
                timeline_csv_path=str(self.timeline_csv),
                only_character=None,
            )
            self.log(f"✓ Đã sinh {num_scenes} scenes vào: {self.timeline_csv}")

            return True

        except Exception as e:
            self.log(f"❌ Lỗi AI analyze: {e}")
            return False

    def step4_generate_cut_list(self) -> bool:
        """
        Bước 4: Sinh cut list cho Premiere
        """
        self.log("\n=== BƯỚC 4: Sinh Cut List ===")

        try:
            keywords = self.load_keywords()
        except Exception as e:
            self.log(f"❌ Lỗi load keywords: {e}")
            return False

        # Get videos in resource folder
        video_exts = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        videos = []
        for ext in video_exts:
            videos.extend(self.resource_folder.glob(f"*{ext}"))
            videos.extend(self.resource_folder.glob(f"**/*{ext}"))

        self.log(f"Videos trong resource: {len(videos)}")

        # Match keywords with videos
        cuts = []
        for kw in keywords:
            keyword = kw.get("keyword", "")
            kw_lower = keyword.lower()

            # Find matching video
            matched_video = None
            for v in videos:
                if kw_lower in v.stem.lower() or v.stem.lower() in kw_lower:
                    matched_video = v
                    break

            cuts.append({
                "index": kw.get("index", 0),
                "keyword": keyword,
                "timeline_start": kw.get("start_seconds", 0),
                "timeline_end": kw.get("end_seconds", 0),
                "timeline_duration": kw.get("duration_seconds", 5),
                "video_path": str(matched_video) if matched_video else "",
                "video_name": matched_video.name if matched_video else "NOT_FOUND",
            })

        # Save cut list
        matched = sum(1 for c in cuts if c["video_path"])
        cut_data = {
            "count": len(cuts),
            "matched": matched,
            "cuts": cuts,
        }

        with open(self.cut_list_json, "w", encoding="utf-8") as f:
            json.dump(cut_data, f, ensure_ascii=False, indent=2)

        self.log(f"✓ Đã sinh cut list: {self.cut_list_json}")
        self.log(f"   Keywords: {len(cuts)}")
        self.log(f"   Matched: {matched}")

        return True

    def run_full_workflow(self, skip_download: bool = False) -> bool:
        """
        Chạy toàn bộ workflow
        """
        self.log("╔════════════════════════════════════════╗")
        self.log("║   MARKER-BASED WORKFLOW                ║")
        self.log("╚════════════════════════════════════════╝")

        # Ensure data folder exists
        self.data_folder.mkdir(parents=True, exist_ok=True)

        # Step 1: Check keywords
        if not self.step1_check_keywords():
            return False

        # Step 2: Search & Download (optional skip)
        if not skip_download:
            if not self.step2_search_and_download():
                self.log("⚠ Download thất bại, tiếp tục với videos hiện có...")

        # Step 3: AI Analyze
        if not self.step3_ai_analyze():
            self.log("⚠ AI analyze thất bại, sinh cut list dựa trên filename...")

        # Step 4: Generate cut list
        if not self.step4_generate_cut_list():
            return False

        self.log("\n╔════════════════════════════════════════╗")
        self.log("║   ✓ WORKFLOW HOÀN THÀNH!               ║")
        self.log("╚════════════════════════════════════════╝")
        self.log(f"\nBước tiếp theo:")
        self.log(f"   Chạy executeCuts.jsx trong Premiere để đổ clips vào V4")

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Marker-based Workflow")
    parser.add_argument("--project", required=True, help="Path to .prproj file")
    parser.add_argument("--data-folder", required=True, help="Data folder")
    parser.add_argument("--resource-folder", required=True, help="Resource folder")
    parser.add_argument("--videos-per-keyword", type=int, default=5)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--gemini-key", help="Gemini API key")

    args = parser.parse_args()

    workflow = MarkerBasedWorkflow(
        project_path=args.project,
        data_folder=args.data_folder,
        resource_folder=args.resource_folder,
        gemini_api_key=args.gemini_key,
        videos_per_keyword=args.videos_per_keyword,
    )

    success = workflow.run_full_workflow(skip_download=args.skip_download)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
