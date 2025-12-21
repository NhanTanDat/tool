"""
marker_based_workflow.py

Workflow hoàn chỉnh dựa trên Markers:
1. Đọc keywords từ track3_keywords.json
2. Gộp keywords trùng, tìm kiếm & download videos
3. AI phân tích videos, tìm nhiều segments cho mỗi keyword
4. Phân bổ segments khác nhau cho mỗi vị trí marker

LƯU Ý: Mỗi keyword có thể xuất hiện nhiều lần ở các vị trí khác nhau
       → Mỗi vị trí sẽ nhận một segment khác nhau từ video
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from collections import defaultdict

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
    Workflow dựa trên markers với hỗ trợ keywords trùng lặp.
    """

    def __init__(
        self,
        project_path: str,
        data_folder: str,
        resource_folder: str,
        gemini_api_key: Optional[str] = None,
        videos_per_keyword: int = 3,
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

    def group_keywords(self, keywords: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Gộp keywords theo text, trả về dict:
        {
            "Tony Dow best moments": [marker0, marker1, marker2, ...],
            "Wally Cleaver": [marker4, marker5, ...],
        }
        """
        groups = defaultdict(list)
        for kw in keywords:
            text = kw.get("keyword", "").strip()
            if text:
                groups[text].append(kw)
        return dict(groups)

    def step1_analyze_keywords(self) -> Dict[str, List[Dict]]:
        """
        Bước 1: Phân tích keywords - gộp các keywords trùng
        """
        self.log("\n" + "="*50)
        self.log("  BƯỚC 1: PHÂN TÍCH KEYWORDS")
        self.log("="*50)

        if not self.keywords_json.exists():
            self.log(f"❌ Không tìm thấy: {self.keywords_json}")
            self.log("   Hãy chạy 'Đọc Markers' trước!")
            return {}

        try:
            keywords = self.load_keywords()
            self.log(f"\n📋 Tổng số markers: {len(keywords)}")

            groups = self.group_keywords(keywords)
            self.log(f"📋 Keywords unique: {len(groups)}")
            self.log("")

            for kw_text, markers in groups.items():
                self.log(f"   [{len(markers)}x] {kw_text}")
                for m in markers:
                    self.log(f"        └─ {m.get('start_timecode', '')} ({m.get('duration_seconds', 0):.1f}s)")

            return groups

        except Exception as e:
            self.log(f"❌ Lỗi: {e}")
            return {}

    def step2_download_videos(self, keyword_groups: Dict[str, List[Dict]]) -> bool:
        """
        Bước 2: Download videos - chỉ download cho keywords unique
        """
        self.log("\n" + "="*50)
        self.log("  BƯỚC 2: DOWNLOAD VIDEOS")
        self.log("="*50)

        if not keyword_groups:
            self.log("❌ Không có keywords")
            return False

        unique_keywords = list(keyword_groups.keys())
        self.log(f"\n🔍 Sẽ tìm videos cho {len(unique_keywords)} keywords unique")

        # Import search function
        try:
            from core.downloadTool.get_link import _search_youtube_for_keyword
        except ImportError as e:
            self.log(f"❌ Không import được get_link: {e}")
            return False

        # Search và tạo dl_links.txt
        lines = []
        total_links = 0
        global_seen = set()

        for i, kw in enumerate(unique_keywords):
            count_needed = len(keyword_groups[kw])
            # Download nhiều hơn số cần để có lựa chọn
            videos_to_get = max(self.videos_per_keyword, count_needed + 2)

            self.log(f"\n[{i+1}/{len(unique_keywords)}] \"{kw}\"")
            self.log(f"   Cần: {count_needed} segments, download: {videos_to_get} videos")

            try:
                search_n = videos_to_get * 5
                candidates = _search_youtube_for_keyword(kw, max_results=search_n)

                urls_ok = []
                for c in candidates:
                    url = c.get("url", "").strip()
                    if not url or url in global_seen:
                        continue
                    global_seen.add(url)
                    urls_ok.append(url)
                    if len(urls_ok) >= videos_to_get:
                        break

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
        self.log(f"\n✓ Đã lưu {total_links} links → {self.dl_links_txt.name}")

        # Download videos
        self.log("\n📥 Đang download videos...")
        self.resource_folder.mkdir(parents=True, exist_ok=True)

        try:
            from core.downloadTool.down_by_yt import download_all_from_links_txt

            count = download_all_from_links_txt(
                links_txt=str(self.dl_links_txt),
                output_dir=str(self.resource_folder),
                dtype="mp4",
            )
            self.log(f"✓ Đã download {count} videos")
            return count > 0

        except ImportError:
            self.log("⚠ Không import được download function")
            self.log(f"   Chạy thủ công với: {self.dl_links_txt}")
            return True
        except Exception as e:
            self.log(f"⚠ Lỗi download: {e}")
            return True

    def step3_ai_analyze(self, keyword_groups: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Bước 3: AI phân tích videos
        Trả về dict: keyword -> list of segments
        """
        self.log("\n" + "="*50)
        self.log("  BƯỚC 3: AI PHÂN TÍCH VIDEOS")
        self.log("="*50)

        if not self.gemini_api_key:
            self.log("⚠ Không có GEMINI_API_KEY, bỏ qua AI analyze")
            return {}

        key_preview = self.gemini_api_key[:8] + "..." + self.gemini_api_key[-4:]
        self.log(f"\n✓ API Key: {key_preview}")

        # Get videos for each keyword folder
        video_exts = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        keyword_segments = {}

        try:
            from core.ai.genmini_analyze import analyze_video_for_keyword
        except ImportError:
            self.log("⚠ Không import được genmini_analyze")
            return {}

        for kw_text, markers in keyword_groups.items():
            count_needed = len(markers)
            self.log(f"\n🔍 \"{kw_text}\" - cần {count_needed} segments")

            # Find videos in keyword folder
            kw_folder = self.resource_folder / kw_text.replace(" ", "_")
            if not kw_folder.exists():
                # Try finding any matching videos
                kw_folder = self.resource_folder

            videos = []
            for ext in video_exts:
                videos.extend(kw_folder.glob(f"*{ext}"))

            if not videos:
                self.log(f"   ⚠ Không tìm thấy video cho keyword này")
                continue

            self.log(f"   Videos: {len(videos)}")

            # Analyze each video to find segments
            all_segments = []
            for video in videos[:self.videos_per_keyword]:
                try:
                    self.log(f"   Analyzing: {video.name}...")
                    segments = analyze_video_for_keyword(
                        video_path=str(video),
                        keyword=kw_text,
                        max_segments=count_needed + 2,
                        api_key=self.gemini_api_key,
                    )
                    for seg in segments:
                        seg["video_path"] = str(video)
                        seg["video_name"] = video.name
                    all_segments.extend(segments)
                    self.log(f"      → {len(segments)} segments")
                except Exception as e:
                    self.log(f"      ❌ Lỗi: {e}")

            keyword_segments[kw_text] = all_segments
            self.log(f"   ✓ Tổng: {len(all_segments)} segments")

        return keyword_segments

    def step4_generate_cut_list(
        self,
        keyword_groups: Dict[str, List[Dict]],
        keyword_segments: Dict[str, List[Dict]]
    ) -> bool:
        """
        Bước 4: Sinh cut list - phân bổ segments cho từng marker
        """
        self.log("\n" + "="*50)
        self.log("  BƯỚC 4: SINH CUT LIST")
        self.log("="*50)

        # Get all videos in resource folder
        video_exts = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        all_videos = []
        for ext in video_exts:
            all_videos.extend(self.resource_folder.rglob(f"*{ext}"))

        self.log(f"\nVideos trong resource: {len(all_videos)}")

        # Load original keywords list (to preserve order)
        keywords = self.load_keywords()

        cuts = []
        segment_usage = defaultdict(int)  # Track which segment index is used per keyword

        for kw in keywords:
            idx = kw.get("index", 0)
            kw_text = kw.get("keyword", "")
            timeline_start = kw.get("start_seconds", 0)
            timeline_end = kw.get("end_seconds", 0)
            duration = kw.get("duration_seconds", 5)

            self.log(f"\n[{idx}] \"{kw_text}\" @ {kw.get('start_timecode', '')}")

            # Get next available segment for this keyword
            segments = keyword_segments.get(kw_text, [])
            seg_idx = segment_usage[kw_text]

            if segments and seg_idx < len(segments):
                # Use AI segment
                seg = segments[seg_idx]
                segment_usage[kw_text] += 1

                cuts.append({
                    "index": idx,
                    "keyword": kw_text,
                    "timeline_start": timeline_start,
                    "timeline_end": timeline_end,
                    "timeline_duration": duration,
                    "video_path": seg.get("video_path", ""),
                    "video_name": seg.get("video_name", ""),
                    "clip_start": seg.get("start_time", 0),
                    "clip_end": seg.get("end_time", duration),
                    "source": "ai_matched",
                })
                self.log(f"   ✓ AI segment #{seg_idx}: {seg.get('start_time', 0):.1f}s - {seg.get('end_time', 0):.1f}s")

            else:
                # Fallback: Find video in keyword subfolder or use round-robin
                matched_video = None
                kw_slug = kw_text.replace(" ", "_")
                kw_folder = self.resource_folder / kw_slug

                # Method 1: Look in keyword-specific subfolder
                if kw_folder.exists():
                    kw_videos = list(kw_folder.glob("*.mp4")) + list(kw_folder.glob("*.webm"))
                    if kw_videos:
                        # Use round-robin: seg_idx % len(videos)
                        video_idx = seg_idx % len(kw_videos)
                        matched_video = kw_videos[video_idx]
                        self.log(f"   ✓ Folder match: {kw_folder.name}/{matched_video.name}")

                # Method 2: Try filename matching
                if not matched_video:
                    kw_lower = kw_text.lower()
                    for v in all_videos:
                        if kw_lower in v.stem.lower() or v.stem.lower() in kw_lower:
                            matched_video = v
                            break

                # Method 3: Use any available video (round-robin from all)
                if not matched_video and all_videos:
                    # Each keyword gets different videos
                    kw_hash = hash(kw_text) % len(all_videos)
                    video_idx = (kw_hash + seg_idx) % len(all_videos)
                    matched_video = all_videos[video_idx]
                    self.log(f"   ⚠ Fallback: dùng video #{video_idx}: {matched_video.name}")

                if matched_video:
                    # Calculate clip offset for same keyword different position
                    offset = seg_idx * duration if seg_idx > 0 else 0

                    cuts.append({
                        "index": idx,
                        "keyword": kw_text,
                        "timeline_start": timeline_start,
                        "timeline_end": timeline_end,
                        "timeline_duration": duration,
                        "video_path": str(matched_video),
                        "video_name": matched_video.name,
                        "clip_start": offset,
                        "clip_end": offset + duration,
                        "source": "fallback_matched",
                    })
                    segment_usage[kw_text] += 1

                else:
                    cuts.append({
                        "index": idx,
                        "keyword": kw_text,
                        "timeline_start": timeline_start,
                        "timeline_end": timeline_end,
                        "timeline_duration": duration,
                        "video_path": "",
                        "video_name": "NOT_FOUND",
                        "clip_start": 0,
                        "clip_end": 0,
                        "source": "not_found",
                    })
                    self.log(f"   ❌ Không tìm thấy video")

        # Summary
        matched = sum(1 for c in cuts if c["video_path"])
        ai_matched = sum(1 for c in cuts if c.get("source") == "ai_matched")

        # Save cut list
        cut_data = {
            "count": len(cuts),
            "matched": matched,
            "ai_matched": ai_matched,
            "cuts": cuts,
        }

        with open(self.cut_list_json, "w", encoding="utf-8") as f:
            json.dump(cut_data, f, ensure_ascii=False, indent=2)

        self.log("\n" + "="*50)
        self.log(f"  ✓ CUT LIST HOÀN THÀNH")
        self.log("="*50)
        self.log(f"   Tổng markers: {len(cuts)}")
        self.log(f"   Matched:      {matched}")
        self.log(f"   AI matched:   {ai_matched}")
        self.log(f"   File:         {self.cut_list_json.name}")

        return True

    def run_full_workflow(self, skip_download: bool = False) -> bool:
        """
        Chạy toàn bộ workflow
        """
        self.log("\n" + "="*60)
        self.log("  🚀 MARKER-BASED WORKFLOW")
        self.log("="*60)

        # Ensure data folder exists
        self.data_folder.mkdir(parents=True, exist_ok=True)

        # Step 1: Analyze keywords
        keyword_groups = self.step1_analyze_keywords()
        if not keyword_groups:
            return False

        # Step 2: Download videos
        if not skip_download:
            self.step2_download_videos(keyword_groups)

        # Step 3: AI Analyze
        keyword_segments = self.step3_ai_analyze(keyword_groups)

        # Step 4: Generate cut list
        if not self.step4_generate_cut_list(keyword_groups, keyword_segments):
            return False

        self.log("\n" + "="*60)
        self.log("  ✓✓✓ WORKFLOW HOÀN THÀNH ✓✓✓")
        self.log("="*60)
        self.log("\n📋 Bước tiếp theo:")
        self.log("   Chạy executeCuts.jsx trong Premiere để đổ clips vào V4")
        self.log("")

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Marker-based Workflow")
    parser.add_argument("--project", required=True)
    parser.add_argument("--data-folder", required=True)
    parser.add_argument("--resource-folder", required=True)
    parser.add_argument("--videos-per-keyword", type=int, default=3)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--gemini-key")

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
