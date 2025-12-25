"""
marker_based_workflow.py

Workflow dựa trên Markers:
1. Đọc keywords từ track3_keywords.json
2. Gộp keywords trùng, tìm kiếm & download videos
3. AI phân tích videos, lấy danh sách segments "best"
4. Với mỗi marker:
   - CHỈ lấy 2-3 clip xuất sắc nhất (mặc định 3)
   - keyword trùng -> mỗi marker 1-3 segment KHÁC nhau (cursor theo keyword)
   - KHÔNG fill full duration bằng nhiều clip nữa

FIX/IMPROVE:
- Cursor theo keyword (không reset theo marker)
- Tìm folder keyword robust (slugify + fallback)
- Parse segment time fields an toàn
- Sort segments theo confidence desc để lấy best trước
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
    kw = (keyword or "").strip()
    cands = []
    if kw:
        cands.append(kw)  # đôi khi folder giữ nguyên
        cands.append(kw.replace(" ", "_"))
        cands.append(_slugify_keyword(kw))
        cands.append(_slugify_keyword(kw).lower())
    seen = set()
    out = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _find_keyword_folder(resource_folder: Path, keyword: str) -> Path:
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
    Segments có thể dùng:
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


def _seg_conf(seg: Dict[str, Any]) -> float:
    return _f(seg.get("confidence", seg.get("score", 0.0)), 0.0)


# =========================
# Workflow Class
# =========================
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
        clips_per_marker: int = 3,  # <-- NEW: 2-3
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.project_path = Path(project_path)
        self.data_folder = Path(data_folder)
        self.resource_folder = Path(resource_folder)
        self.gemini_api_key = gemini_api_key or get_gemini_api_key() or ""
        self.videos_per_keyword = max(1, int(videos_per_keyword))
        self.log_callback = log_callback or print

        # clamp clips_per_marker -> [2..3]
        try:
            cpm = int(clips_per_marker)
        except Exception:
            cpm = 3
        if cpm < 2:
            cpm = 2
        if cpm > 3:
            cpm = 3
        self.clips_per_marker = cpm

        # File paths
        self.keywords_json = self.data_folder / "track3_keywords.json"
        self.dl_links_txt = self.data_folder / "dl_links.txt"
        self.segments_json = self.data_folder / "segments_genmini.json"
        self.cut_list_json = self.data_folder / "cut_list.json"

    def log(self, msg: str):
        self.log_callback(msg)

    def load_keywords(self) -> List[Dict[str, Any]]:
        if not self.keywords_json.exists():
            raise FileNotFoundError(f"Không tìm thấy: {self.keywords_json}")

        with open(self.keywords_json, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        return data.get("keywords", [])

    def group_keywords(self, keywords: List[Dict]) -> Dict[str, List[Dict]]:
        groups = defaultdict(list)
        for kw in keywords:
            text = (kw.get("keyword", "") or "").strip()
            if text:
                groups[text].append(kw)
        return dict(groups)

    # =========================
    # STEP 1
    # =========================
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

            self.log(f"\n🎯 Cấu hình: clips_per_marker={self.clips_per_marker} (mỗi marker lấy 2-3 clip best)")
            return groups
        except Exception as e:
            self.log(f"❌ Lỗi: {e}")
            return {}

    # =========================
    # STEP 2
    # =========================
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
            count_needed_markers = len(keyword_groups[kw])

            # Với yêu cầu chỉ 2-3 clips/marker:
            # Nên tải dư 1 chút để AI có nguồn chọn
            videos_to_get = max(self.videos_per_keyword, min(10, count_needed_markers + 2))

            self.log(f"\n[{i + 1}/{len(unique_keywords)}] \"{kw}\"")
            self.log(f"   Markers: {count_needed_markers}, download: {videos_to_get} videos")

            try:
                search_n = videos_to_get * 6
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

    # =========================
    # STEP 3
    # =========================
    def step3_ai_analyze(self, keyword_groups: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Bước 3: AI phân tích videos
        Trả về dict: keyword -> list of segments (đã sort best trước)
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
            self.log("⚠ Không import được core.ai.genmini_analyze")
            return {}

        for kw_text, markers in keyword_groups.items():
            marker_count = len(markers)

            # Mỗi marker cần 2-3 clip best => tổng cần ~ marker_count * clips_per_marker (+ buffer)
            total_needed = marker_count * self.clips_per_marker
            buffer = 3
            target_total = max(6, total_needed + buffer)

            self.log(f"\n🔍 \"{kw_text}\"")
            self.log(f"   Markers: {marker_count}")
            self.log(f"   Target segments tổng: {target_total} (để đủ cấp cho marker trùng)")

            kw_folder = _find_keyword_folder(self.resource_folder, kw_text)
            videos = _list_videos(kw_folder)

            if not videos and kw_folder != self.resource_folder:
                videos = _list_videos(self.resource_folder)

            if not videos:
                self.log("   ⚠ Không tìm thấy video cho keyword này")
                continue

            use_videos = videos[: self.videos_per_keyword]
            self.log(f"   Folder dùng: {kw_folder.name}")
            self.log(f"   Videos dùng: {len(use_videos)}/{len(videos)}")

            # Chia quota segments cho từng video để tổng đạt target_total
            per_video = max(3, min(8, (target_total // max(1, len(use_videos))) + 1))

            all_segments: List[Dict[str, Any]] = []

            for video in use_videos:
                try:
                    self.log(f"   Analyzing: {video.name} (max {per_video} segments)...")
                    segments = analyze_video_for_keyword(
                        video_path=str(video),
                        keyword=kw_text,
                        max_segments=per_video,
                        api_key=self.gemini_api_key,
                    )

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

            # De-dup
            uniq = []
            seen_ids = set()
            for s in all_segments:
                sid = _seg_id(s)
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                uniq.append(s)

            # Sort BEST first (confidence desc, rồi duration desc)
            def _sort_key(s: Dict[str, Any]):
                st, en = _seg_times(s)
                dur = max(0.0, en - st)
                return (_seg_conf(s), dur)

            uniq.sort(key=_sort_key, reverse=True)

            # Giữ top để khỏi quá nhiều (đủ cấp marker)
            uniq = uniq[: max(target_total, 10)]

            keyword_segments[kw_text] = uniq
            self.log(f"   ✓ Tổng unique (sorted best): {len(uniq)} segments")

        # Save for debug
        try:
            with open(self.segments_json, "w", encoding="utf-8") as f:
                json.dump(keyword_segments, f, ensure_ascii=False, indent=2)
            self.log(f"\n✓ Saved segments → {self.segments_json.name}")
        except Exception as e:
            self.log(f"⚠ Không lưu được segments_genmini.json: {e}")

        return keyword_segments

    # =========================
    # STEP 4
    # =========================
    def step4_generate_cut_list(
        self,
        keyword_groups: Dict[str, List[Dict]],
        keyword_segments: Dict[str, List[Dict]],
    ) -> bool:
        """
        Bước 4: Sinh cut_list.json
        YÊU CẦU:
        - Mỗi marker chỉ lấy 2-3 clip best
        - keyword trùng -> mỗi marker lấy segment khác nhau (cursor theo keyword)
        - KHÔNG fill full duration nữa
        """
        self.log("\n" + "=" * 50)
        self.log("  BƯỚC 4: SINH CUT LIST (2-3 CLIPS / MARKER)")
        self.log("=" * 50)

        all_videos = _list_videos(self.resource_folder)
        self.log(f"\nVideos trong resource: {len(all_videos)}")

        keywords = self.load_keywords()

        # Cursor theo keyword
        seg_cursor: Dict[str, int] = defaultdict(int)

        cuts: List[Dict[str, Any]] = []

        for kw in keywords:
            idx = int(kw.get("index", 0))
            kw_text = (kw.get("keyword", "") or "").strip()
            if not kw_text:
                continue

            timeline_start = _f(kw.get("start_seconds", 0), 0.0)
            timeline_end = _f(kw.get("end_seconds", timeline_start), timeline_start)
            marker_duration = _f(
                kw.get("duration_seconds", max(0.0, timeline_end - timeline_start)),
                max(0.0, timeline_end - timeline_start),
            )
            marker_duration = max(0.0, marker_duration)

            # Nếu end_seconds không có / lỗi, tự suy ra end theo duration
            if timeline_end <= timeline_start and marker_duration > 0:
                timeline_end = timeline_start + marker_duration

            self.log(f"\n[{idx}] \"{kw_text}\" @ {kw.get('start_timecode', '')} ({marker_duration:.1f}s)")

            segments = keyword_segments.get(kw_text, []) or []

            marker_clips: List[Dict[str, Any]] = []
            current_pos = timeline_start

            # Mục tiêu: 2-3 clips/marker (mặc định 3)
            target = self.clips_per_marker

            used_segment_ids = set()
            picked = 0
            safety = 0

            while picked < target and safety < 500:
                safety += 1

                if not segments:
                    break

                cur = seg_cursor[kw_text]
                if cur >= len(segments):
                    break

                seg = segments[cur]
                seg_cursor[kw_text] += 1

                sid = _seg_id(seg)
                if sid in used_segment_ids:
                    continue
                used_segment_ids.add(sid)

                st, en = _seg_times(seg)
                seg_dur = max(0.0, en - st)
                if seg_dur <= 0.6:
                    continue

                # KHÔNG vượt quá marker end (để tránh đè marker sau)
                remaining = max(0.0, timeline_end - current_pos) if timeline_end > timeline_start else seg_dur
                if remaining < 0.8:
                    break

                clip_dur = min(seg_dur, remaining)

                # Nếu clip quá ngắn do remaining, bỏ qua để không ra clip “lụi”
                # (vì bạn muốn clip xuất sắc 2-4s)
                if clip_dur < 1.8:
                    # nếu chưa pick được gì, vẫn cố pick 1 clip để khỏi rỗng
                    if picked == 0:
                        clip_dur = seg_dur
                    else:
                        continue

                marker_clips.append(
                    {
                        "video_path": seg.get("video_path", ""),
                        "video_name": seg.get("video_name", ""),
                        "clip_start": float(st),
                        "clip_end": float(st + clip_dur),
                        "timeline_pos": float(current_pos),
                        "duration": float(clip_dur),
                        "source": "ai_best",
                        "confidence": float(_seg_conf(seg)),
                        "description": seg.get("description", seg.get("script_notes", "")),
                    }
                )

                current_pos += clip_dur
                picked += 1

            # Nếu không có segment AI -> fallback 1 clip ngắn (vẫn giữ logic tối thiểu)
            if not marker_clips and all_videos:
                fallback_video = all_videos[abs(hash(kw_text)) % len(all_videos)]
                # chọn 1 đoạn 3s random-ish theo hash
                base = (abs(hash(kw_text + str(idx))) % 50)  # 0..49s
                clip_dur = 3.0
                marker_clips.append(
                    {
                        "video_path": str(fallback_video),
                        "video_name": fallback_video.name,
                        "clip_start": float(base),
                        "clip_end": float(base + clip_dur),
                        "timeline_pos": float(timeline_start),
                        "duration": float(clip_dur),
                        "source": "fallback_one",
                        "confidence": 0.1,
                        "description": "fallback",
                    }
                )

            if marker_clips:
                self.log(f"   → Picked {len(marker_clips)} clips (target {target})")
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
        ai_clips = sum(sum(1 for clip in c.get("clips", []) if clip.get("source") == "ai_best") for c in cuts)

        cut_data = {
            "count": len(cuts),
            "total_clips": total_clips,
            "markers_with_clips": markers_with_clips,
            "ai_clips": ai_clips,
            "clips_per_marker": self.clips_per_marker,
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

    # =========================
    # RUN
    # =========================
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
    parser.add_argument("--clips-per-marker", type=int, default=3)  # 2..3
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--gemini-key")

    args = parser.parse_args()

    workflow = MarkerBasedWorkflow(
        project_path=args.project,
        data_folder=args.data_folder,
        resource_folder=args.resource_folder,
        gemini_api_key=args.gemini_key,
        videos_per_keyword=args.videos_per_keyword,
        clips_per_marker=args.clips_per_marker,
    )

    ok = workflow.run_full_workflow(skip_download=args.skip_download)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
