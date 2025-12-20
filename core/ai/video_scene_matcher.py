"""
video_scene_matcher.py

AI module để:
1. Phân tích video từ YouTube đã tải về
2. Tìm scenes/phân cảnh phù hợp với keyword
3. Trả về timecode của scenes để cắt và đẩy vào V4
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import AI models (nếu có)
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from yt_dlp import YoutubeDL
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False


class VideoSceneMatcher:
    """
    Class để match keyword với video scenes.
    Sử dụng AI (Gemini) hoặc fallback methods.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")

        if HAS_GEMINI and self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            # Use gemini-2.0-flash (gemini-1.5-flash is deprecated)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.use_ai = True
            print("[VideoSceneMatcher] Gemini AI enabled")
        else:
            self.use_ai = False
            print("[VideoSceneMatcher] AI disabled, using fallback methods")

    def analyze_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """
        Phân tích metadata của video (title, description, tags).
        """
        if not HAS_YTDLP:
            return {"title": "", "description": "", "tags": []}

        try:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_path, download=False)
                return {
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "tags": info.get("tags", []),
                    "duration": info.get("duration", 0),
                }
        except Exception as e:
            print(f"[analyze_video_metadata] Error: {e}")
            return {"title": "", "description": "", "tags": [], "duration": 0}

    def extract_subtitle_text(self, video_path: str) -> str:
        """
        Trích xuất subtitles/captions từ video (nếu có).
        """
        if not HAS_YTDLP:
            return ""

        try:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en", "vi"],
                "subtitlesformat": "vtt",
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_path, download=False)
                subtitles = info.get("subtitles", {})
                auto_subs = info.get("automatic_captions", {})

                # Lấy English hoặc Vietnamese subtitles
                for lang in ["en", "vi"]:
                    if lang in subtitles:
                        # Download subtitle và parse
                        # (simplified - thực tế cần download và parse VTT)
                        return f"[Subtitles available in {lang}]"
                    if lang in auto_subs:
                        return f"[Auto captions available in {lang}]"

                return ""
        except Exception as e:
            print(f"[extract_subtitle_text] Error: {e}")
            return ""

    def match_keyword_simple(
        self, keyword: str, video_metadata: Dict[str, Any]
    ) -> float:
        """
        Simple keyword matching dựa trên title, description, tags.
        Return score 0.0 - 1.0
        """
        keyword_lower = keyword.lower()
        score = 0.0

        # Check title
        title = (video_metadata.get("title") or "").lower()
        if keyword_lower in title:
            score += 0.5

        # Check description
        desc = (video_metadata.get("description") or "").lower()
        if keyword_lower in desc:
            score += 0.3

        # Check tags
        tags = [t.lower() for t in (video_metadata.get("tags") or [])]
        for tag in tags:
            if keyword_lower in tag:
                score += 0.2
                break

        return min(score, 1.0)

    def ai_analyze_video_for_keyword(
        self, keyword: str, video_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sử dụng Gemini AI để phân tích video và tìm scenes phù hợp.
        """
        if not self.use_ai:
            return self._fallback_analysis(keyword, video_metadata)

        try:
            prompt = f"""
Phân tích video sau và xác định xem nội dung có liên quan đến từ khóa "{keyword}" không:

Title: {video_metadata.get('title', 'N/A')}
Description: {video_metadata.get('description', 'N/A')[:500]}
Tags: {', '.join(video_metadata.get('tags', [])[:10])}
Duration: {video_metadata.get('duration', 0)} seconds

Hãy trả lời theo format JSON:
{{
    "relevant": true/false,
    "confidence": 0.0-1.0,
    "reason": "Giải thích ngắn gọn",
    "suggested_scenes": [
        {{
            "start_time": 0,
            "end_time": 10,
            "description": "Mô tả ngắn"
        }}
    ]
}}

Chỉ trả về JSON, không thêm text nào khác.
"""

            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Parse JSON
            # Remove markdown code blocks if present
            text = re.sub(r"```json\n?", "", text)
            text = re.sub(r"```\n?", "", text)

            result = json.loads(text)
            return result

        except Exception as e:
            print(f"[ai_analyze_video_for_keyword] Error: {e}")
            return self._fallback_analysis(keyword, video_metadata)

    def _fallback_analysis(
        self, keyword: str, video_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback method khi AI không khả dụng.
        """
        score = self.match_keyword_simple(keyword, video_metadata)
        duration = video_metadata.get("duration", 0)

        return {
            "relevant": score > 0.3,
            "confidence": score,
            "reason": f"Simple keyword matching: {score:.2f}",
            "suggested_scenes": [
                {
                    "start_time": 0,
                    "end_time": min(duration, 30),
                    "description": "Full video or first 30 seconds",
                }
            ],
        }

    def find_best_scenes_for_keywords(
        self,
        keywords_data: List[Dict[str, Any]],
        video_pool: List[str],
        max_videos_per_keyword: int = 3,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Tìm best matching scenes cho mỗi keyword từ pool videos.

        Args:
            keywords_data: List of {keyword, start_seconds, end_seconds, duration_seconds}
            video_pool: List of video file paths
            max_videos_per_keyword: Số videos tối đa để analyze cho mỗi keyword

        Returns:
            Dict mapping keyword -> list of matching videos with scenes
        """
        results = {}

        for kw_item in keywords_data:
            keyword = kw_item["keyword"]
            required_duration = kw_item["duration_seconds"]

            print(f"\n[find_best_scenes] Processing keyword: '{keyword}' (need {required_duration:.1f}s)")

            matches = []

            for video_path in video_pool[:max_videos_per_keyword]:
                if not os.path.exists(video_path):
                    continue

                print(f"  Analyzing video: {os.path.basename(video_path)}")

                # Get metadata
                metadata = self.analyze_video_metadata(video_path)

                # AI analysis
                analysis = self.ai_analyze_video_for_keyword(keyword, metadata)

                if analysis.get("relevant", False):
                    matches.append(
                        {
                            "video_path": video_path,
                            "confidence": analysis.get("confidence", 0.0),
                            "reason": analysis.get("reason", ""),
                            "suggested_scenes": analysis.get("suggested_scenes", []),
                            "duration": metadata.get("duration", 0),
                        }
                    )

            # Sort by confidence
            matches.sort(key=lambda x: x["confidence"], reverse=True)

            results[keyword] = matches
            print(f"  Found {len(matches)} relevant videos for '{keyword}'")

        return results


def load_keywords_from_json(json_path: str) -> List[Dict[str, Any]]:
    """
    Load keywords từ file JSON được export từ extractTrack3Keywords.jsx
    """
    # Use utf-8-sig to automatically handle UTF-8 BOM from ExtendScript
    with open(json_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data.get("keywords", [])


def get_video_pool_from_folder(folder_path: str) -> List[str]:
    """
    Lấy tất cả video files từ folder.
    """
    video_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    videos = []

    folder = Path(folder_path)
    if not folder.exists():
        return videos

    for ext in video_extensions:
        videos.extend([str(f) for f in folder.rglob(f"*{ext}")])

    return videos


def main():
    """
    Test function
    """
    import argparse

    parser = argparse.ArgumentParser(description="Video Scene Matcher")
    parser.add_argument("--keywords-json", required=True, help="Path to track3_keywords.json")
    parser.add_argument("--video-folder", required=True, help="Folder containing videos")
    parser.add_argument("--output", default="scene_matches.json", help="Output JSON file")
    parser.add_argument("--gemini-key", help="Gemini API key")

    args = parser.parse_args()

    # Load keywords
    keywords = load_keywords_from_json(args.keywords_json)
    print(f"Loaded {len(keywords)} keywords from {args.keywords_json}")

    # Get video pool
    videos = get_video_pool_from_folder(args.video_folder)
    print(f"Found {len(videos)} videos in {args.video_folder}")

    # Create matcher
    matcher = VideoSceneMatcher(gemini_api_key=args.gemini_key)

    # Find matches
    results = matcher.find_best_scenes_for_keywords(keywords, videos)

    # Save results
    output_data = {
        "keywords": keywords,
        "matches": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
