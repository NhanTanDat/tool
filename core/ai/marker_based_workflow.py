"""
marker_based_workflow.py

Workflow hoàn chỉnh dựa trên Markers:
1. Đọc keywords từ track3_keywords.json
2. Gộp keywords trùng, tìm kiếm & download videos
3. AI phân tích videos, tìm nhiều segments cho mỗi keyword
4. Phân bổ segments khác nhau cho mỗi vị trí marker (keyword trùng -> mỗi marker 1 segment khác)

FIX:
- Không reset seg_idx cho mỗi marker nữa -> dùng cursor theo keyword
- Tìm folder keyword robust (slugify + fallback)
- Parse segment time fields an toàn
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Tuple
from collections import defaultdict

# Use centralized utilities
from core.utils import setup_paths, load_env, get_gemini_api_key

setup_paths()
load_env()


# =========================
# Helpers
# =========================
def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _slugify_keyword(s: str) -> str:
    s = (s or "").strip()
    s = s.replace(" ", "_")
    s = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in s)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_") or "unknown"


def _keyword_folder_candidates(keyword: str) -> List[str]:
    """
    Sinh nhiều candidate để match folder name do tool download tạo ra.
    """
    kw = (keyword or "").strip()
    cands = []
    if kw:
        cands.append(kw)  # đôi khi folder giữ nguyên
        cands.append(kw.replace(" ", "_"))
        cands.append(_slugify_keyword(kw))
        cands.append(_slugify_keyword(kw).lower())
    # unique preserve order
    seen = set()
    out = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _find_keyword_folder(resource_folder: Path, keyword: str) -> Path:
    """
    Tìm folder phù hợp trong resource_folder cho keyword.
    Ưu tiên khớp chính xác theo candidates; nếu không có -> fallback resource_folder.
    """
    if not resource_folder.exists():
        return resource_folder

    for name in _keyword_folder_candidates(keyword):
        p = resource_folder / name
        if p.exists() and p.is_dir():
            return p

    # Fuzzy: tìm folder con chứa substring đã slugify
    key = _slugify_keyword(keyword).lower()
    if key:
        for child in resource_folder.iterdir():
            if child.is_dir() and key in child.name.lower():
                return child

    return resource_folder


def _list_videos(folder: Path) -> List[Path]:
    exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    if not folder.exists():
        return []
    out = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    out.sort()
    return out


def _seg_times(seg: Dict[str, Any]) -> Tuple[float, float]:
    """
    Genmini segments có thể dùng:
    - start_time/end_time
    - start_seconds/end_seconds
    - start/end
    """
    st = seg.get("start_time", seg.get("start_seconds", seg.get("start", 0)))
    en = seg.get("end_time", seg.get("end_seconds", seg.get("end", 0)))
    stf = _f(st, 0.0)
    enf = _f(en, stf)
    if enf < stf:
        enf = stf
    return stf, enf


def _seg_id(seg: Dict[str, Any]) -> str:
    st, en = _seg_times(seg)
    vp = seg.get("video_path", "") or ""
    return f"{vp}|{st:.3f}|{en:.3f}"


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
        self.gemini_api_key = gemini_api_key or get_gemini_api_key() or ""
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
            text = (kw.get("keyword", "") or "").strip()
            if text:
                groups[text].append(kw)
        return dict(groups)

    def step1_analyze_keywords(self) -> Dict[str, List[Dict]]:
        self.log("\n" + "=" * 50)
        self.log("  BƯỚC 1: PHÂN TÍCH KEYWORDS")
        self.log("=" * 50)

        if not self.keywords_json.exists():
            self.log(f"❌ Không tìm thấy: {self.keywords_json}")
            self.log("   Hãy chạy 'Đọc Markers' trước!")
            return {}

        try:
            keywords = self.load_keywords()
            self.log(f"\n📋 Tổng số markers: {len(keywords)}")

            groups = self.group_keywords(keywords)
            self.log(f"📋 Keywords unique: {len(groups)}\n")

            for kw_text, markers in groups.items():
                self.log(f"   [{len(markers)}x] {kw_text}")
                for m in markers:
                    self.log(f"        └─ {m.get('start_timecode', '')} ({_f(m.get('duration_seconds', 0)):.1f}s)")

            return groups
        except Exception as e:
            self.log(f"❌ Lỗi: {e}")
            return {}

    def step2_download_videos(self, keyword_groups: Dict[str, List[Dict]]) -> bool:
        self.log("\n" + "=" * 50)
        self.log("  BƯỚC 2: DOWNLOAD VIDEOS")
        self.log("=" * 50)

        if not keyword_groups:
            self.log("❌ Không có keywords")
            return False

        unique_keywords = list(keyword_groups.keys())
        self.log(f"\n🔍 Sẽ tìm videos cho {len(unique_keywords)} keywords unique")

        try:
            from core.downloadTool.get_link import _search_youtube_for_keyword
        except ImportError as e:
            self.log(f"❌ Không import được get_link: {e}")
            return False

        lines = []
        total_links = 0
        global_seen = set()

        for i, kw in enumerate(unique_keywords):
            count_needed = len(keyword_groups[kw])
            videos_to_get = max(self.videos_per_keyword, count_needed + 2)

            self.log(f"\n[{i + 1}/{len(unique_keywords)}] \"{kw}\"")
            self.log(f"   Cần: {count_needed} segments, download: {videos_to_get} videos")

            try:
                search_n = videos_to_get * 5
                candidates = _search_youtube_for_keyword(kw, max_results=search_n)

                urls_ok = []
                for c in candidates:
                    url = (c.get("url", "") or "").strip()
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

        self.dl_links_txt.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"\n✓ Đã lưu {total_links} links → {self.dl_links_txt.name}")

        self.log("\n📥 Đang download videos...")
        self.resource_folder.mkdir(parents=True, exist_ok=True)

        try:
            from core.downloadTool.down_by_yt import download_main

            download_main(
                parent_folder=str(self.resource_folder),
                txt_name=str(self.dl_links_txt),
                _type="mp4",
            )
            self.log(f"✓ Đã download videos vào {self.resource_folder}")
            return True
        except ImportError as e:
            self.log(f"⚠ Không import được download function: {e}")
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
        self.log("\n" + "=" * 50)
        self.log("  BƯỚC 3: AI PHÂN TÍCH VIDEOS")
        self.log("=" * 50)

        if not self.gemini_api_key:
            self.log("⚠ Không có GEMINI_API_KEY, bỏ qua AI analyze")
            return {}

        key_preview = self.gemini_api_key[:8] + "..." + self.gemini_api_key[-4:]
        self.log(f"\n✓ API Key: {key_preview}")

        keyword_segments: Dict[str, List[Dict]] = {}

        try:
            from core.ai.genmini_analyze import analyze_video_for_keyword
        except ImportError:
            self.log("⚠ Không import được genmini_analyze")
            return {}

        for kw_text, markers in keyword_groups.items():
            total_duration = sum(_f(m.get("duration_seconds", 5), 5.0) for m in markers)
            avg_seg_duration = 5.0
            segments_needed = int(total_duration / avg_seg_duration) + 5

            self.log(f"\n🔍 \"{kw_text}\"")
            self.log(f"   Markers: {len(markers)}, Tổng duration: {total_duration:.0f}s")
            self.log(f"   Cần ~{segments_needed} segments để fill đầy")

            kw_folder = _find_keyword_folder(self.resource_folder, kw_text)
            videos = _list_videos(kw_folder)

            if not videos and kw_folder != self.resource_folder:
                videos = _list_videos(self.resource_folder)

            if not videos:
                self.log(f"   ⚠ Không tìm thấy video cho keyword này")
                continue

            self.log(f"   Folder dùng: {kw_folder.name}")
            self.log(f"   Videos: {len(videos)}")

            all_segments: List[Dict[str, Any]] = []
            segs_per_video = max(10, segments_needed // max(1, len(videos[: self.videos_per_keyword])) + 3)

            for video in videos[: self.videos_per_keyword]:
                try:
                    self.log(f"   Analyzing: {video.name} (max {segs_per_video} segments)...")
                    segments = analyze_video_for_keyword(
                        video_path=str(video),
                        keyword=kw_text,
                        max_segments=segs_per_video,
                        api_key=self.gemini_api_key,
                    )

                    # Normalize + attach video info
                    fixed = []
                    for seg in segments or []:
                        st, en = _seg_times(seg)
                        if en <= st:
                            continue
                        seg["video_path"] = str(video)
                        seg["video_name"] = video.name
                        seg["start_time"] = st
                        seg["end_time"] = en
                        fixed.append(seg)

                    all_segments.extend(fixed)
                    self.log(f"      → {len(fixed)} segments")
                except Exception as e:
                    self.log(f"      ❌ Lỗi: {e}")

            # De-dup segments
            uniq = []
            seen_ids = set()
            for s in all_segments:
                sid = _seg_id(s)
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                uniq.append(s)

            keyword_segments[kw_text] = uniq
            self.log(f"   ✓ Tổng unique: {len(uniq)} segments")

        # Save for debug
        try:
            with open(self.segments_json, "w", encoding="utf-8") as f:
                json.dump(keyword_segments, f, ensure_ascii=False, indent=2)
            self.log(f"\n✓ Saved segments → {self.segments_json.name}")
        except Exception as e:
            self.log(f"⚠ Không lưu được segments_genmini.json: {e}")

        return keyword_segments

    def step4_generate_cut_list(
        self,
        keyword_groups: Dict[str, List[Dict]],
        keyword_segments: Dict[str, List[Dict]],
    ) -> bool:
        """
        Bước 4: Sinh cut_list.json - fill marker bằng multi-clip.
        FIX: keyword trùng -> mỗi marker lấy segment khác nhau (cursor theo keyword).
        """
        self.log("\n" + "=" * 50)
        self.log("  BƯỚC 4: SINH CUT LIST (MULTI-CLIP)")
        self.log("=" * 50)

        all_videos = _list_videos(self.resource_folder)
        self.log(f"\nVideos trong resource: {len(all_videos)}")

        keywords = self.load_keywords()

        # Cursor theo keyword: phân bổ segment khác nhau cho từng marker occurrence
        seg_cursor: Dict[str, int] = defaultdict(int)

        cuts: List[Dict[str, Any]] = []

        for kw in keywords:
            idx = int(kw.get("index", 0))
            kw_text = (kw.get("keyword", "") or "").strip()
            if not kw_text:
                continue

            timeline_start = _f(kw.get("start_seconds", 0), 0.0)
            timeline_end = _f(kw.get("end_seconds", timeline_start), timeline_start)
            marker_duration = _f(kw.get("duration_seconds", max(0.0, timeline_end - timeline_start)), 5.0)
            marker_duration = max(0.0, marker_duration)

            self.log(f"\n[{idx}] \"{kw_text}\" @ {kw.get('start_timecode', '')} ({marker_duration:.1f}s)")

            segments = keyword_segments.get(kw_text, []) or []

            marker_clips: List[Dict[str, Any]] = []
            current_pos = timeline_start
            remaining = marker_duration

            # Track used segments để không duplicate
            used_segment_ids = set()

            # Fill bằng AI segments theo cursor của keyword
            safety = 0
            while remaining > 0.5 and segments and safety < 500:
                safety += 1

                cur = seg_cursor[kw_text]
                if cur >= len(segments):
                    # HẾT AI SEGMENTS - KHÔNG LOOP, chuyển sang fallback time-based
                    self.log(f"   ⚠ Hết AI segments ({len(segments)}), dùng time-based chunks")
                    break

                seg = segments[seg_cursor[kw_text]]
                seg_cursor[kw_text] += 1

                # Check duplicate
                seg_id = f"{seg.get('video_path', '')}|{_f(seg.get('start_time', 0)):.1f}"
                if seg_id in used_segment_ids:
                    self.log(f"   SKIP duplicate segment: {seg_id}")
                    continue
                used_segment_ids.add(seg_id)

                st, en = _seg_times(seg)
                seg_dur = max(0.0, en - st)
                if seg_dur < 0.6:
                    continue

                clip_dur = min(seg_dur, remaining)

                marker_clips.append(
                    {
                        "video_path": seg.get("video_path", ""),
                        "video_name": seg.get("video_name", ""),
                        "clip_start": st,
                        "clip_end": st + clip_dur,
                        "timeline_pos": current_pos,
                        "duration": clip_dur,
                        "source": "ai_matched",
                    }
                )

                current_pos += clip_dur
                remaining -= clip_dur

                if len(marker_clips) >= 20:
                    break

            # TIME-BASED FALLBACK: khi hết AI segments, dùng sequential chunks từ video
            if remaining > 0.5 and segments:
                # Lấy video từ segment cuối cùng đã dùng
                last_video = segments[-1].get("video_path", "") if segments else ""
                if last_video:
                    # Tìm video end time (ước tính 5 phút nếu không biết)
                    last_seg_end = max(_seg_times(s)[1] for s in segments if s.get("video_path") == last_video)
                    chunk_start = last_seg_end + 1.0  # Bắt đầu sau segment cuối
                    chunk_idx = 0

                    self.log(f"   → Dùng time-based chunks từ {chunk_start:.1f}s")

                    while remaining > 0.5 and chunk_idx < 50:
                        chunk_dur = min(5.0, remaining)  # Mỗi chunk 5s

                        marker_clips.append(
                            {
                                "video_path": last_video,
                                "video_name": Path(last_video).name if last_video else "unknown",
                                "clip_start": chunk_start,
                                "clip_end": chunk_start + chunk_dur,
                                "timeline_pos": current_pos,
                                "duration": chunk_dur,
                                "source": "time_based_fallback",
                            }
                        )

                        current_pos += chunk_dur
                        remaining -= chunk_dur
                        chunk_start += chunk_dur + 0.5  # Gap nhỏ giữa các chunks
                        chunk_idx += 1

            # Fallback nếu không có AI segments
            if remaining > 0.5 and not segments and all_videos:
                kw_hash = abs(hash(kw_text)) % len(all_videos)
                fallback_idx = 0

                while remaining > 0.5:
                    video_idx = (kw_hash + fallback_idx) % len(all_videos)
                    matched_video = all_videos[video_idx]

                    chunk_start = (fallback_idx * 5) % 60
                    clip_dur = min(10.0, remaining)

                    marker_clips.append(
                        {
                            "video_path": str(matched_video),
                            "video_name": matched_video.name,
                            "clip_start": float(chunk_start),
                            "clip_end": float(chunk_start + clip_dur),
                            "timeline_pos": float(current_pos),
                            "duration": float(clip_dur),
                            "source": "fallback",
                        }
                    )

                    current_pos += clip_dur
                    remaining -= clip_dur
                    fallback_idx += 1

                    if len(marker_clips) >= 20:
                        break

            if marker_clips:
                self.log(f"   → {len(marker_clips)} clips để fill {marker_duration:.1f}s")
            else:
                self.log("   ⚠ Không có clip nào cho marker này")

            cuts.append(
                {
                    "index": idx,
                    "keyword": kw_text,
                    "timeline_start": timeline_start,
                    "timeline_end": timeline_end,
                    "timeline_duration": marker_duration,
                    "clips": marker_clips,
                    "clip_count": len(marker_clips),
                }
            )

        total_clips = sum(c.get("clip_count", 0) for c in cuts)
        markers_with_clips = sum(1 for c in cuts if c.get("clip_count", 0) > 0)
        ai_clips = sum(sum(1 for clip in c.get("clips", []) if clip.get("source") == "ai_matched") for c in cuts)

        cut_data = {
            "count": len(cuts),
            "total_clips": total_clips,
            "markers_with_clips": markers_with_clips,
            "ai_clips": ai_clips,
            "cuts": cuts,
        }

        with open(self.cut_list_json, "w", encoding="utf-8") as f:
            json.dump(cut_data, f, ensure_ascii=False, indent=2)

        self.log("\n" + "=" * 50)
        self.log("  ✓ CUT LIST HOÀN THÀNH")
        self.log("=" * 50)
        self.log(f"   Tổng markers:      {len(cuts)}")
        self.log(f"   Markers có clips:  {markers_with_clips}")
        self.log(f"   Tổng clips:        {total_clips}")
        self.log(f"   AI clips:          {ai_clips}")
        self.log(f"   File:              {self.cut_list_json.name}")

        return True

    def run_full_workflow(self, skip_download: bool = False) -> bool:
        self.log("\n" + "=" * 60)
        self.log("  🚀 MARKER-BASED WORKFLOW")
        self.log("=" * 60)

        self.data_folder.mkdir(parents=True, exist_ok=True)

        keyword_groups = self.step1_analyze_keywords()
        if not keyword_groups:
            return False

        if not skip_download:
            self.step2_download_videos(keyword_groups)

        keyword_segments = self.step3_ai_analyze(keyword_groups)

        if not self.step4_generate_cut_list(keyword_groups, keyword_segments):
            return False

        self.log("\n" + "=" * 60)
        self.log("  ✓✓✓ WORKFLOW HOÀN THÀNH ✓✓✓")
        self.log("=" * 60)
        self.log("\n📋 Bước tiếp theo:")
        self.log("   Chạy executeCuts.jsx trong Premiere để đổ clips vào V4\n")

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

    ok = workflow.run_full_workflow(skip_download=args.skip_download)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
