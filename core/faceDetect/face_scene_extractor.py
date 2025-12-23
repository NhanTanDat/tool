"""
face_scene_extractor.py

Module tối ưu AI nhận dạng khuôn mặt:
1. Dựa trên keyword để tìm nhân vật cụ thể
2. Trích xuất clip 2-4 giây khi phát hiện khuôn mặt
3. Tích hợp với workflow Auto V4
"""

import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import contextlib
import io

# Giảm log TensorFlow
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False
    print("[WARNING] DeepFace not installed. Face detection disabled.")


@dataclass
class FaceClip:
    """Đại diện cho một clip chứa khuôn mặt được phát hiện"""
    character: str  # Tên nhân vật (từ keyword)
    video_path: str
    start_time: float  # Thời điểm bắt đầu clip (giây)
    end_time: float  # Thời điểm kết thúc clip (giây)
    duration: float  # Độ dài clip
    confidence: float  # Độ tin cậy detection
    face_count: int  # Số lần detect face trong clip này
    center_time: float  # Thời điểm trung tâm (nơi detect rõ nhất)


@dataclass
class ExtractionConfig:
    """Cấu hình cho quá trình trích xuất"""
    min_clip_duration: float = 2.0  # Clip tối thiểu 2 giây
    max_clip_duration: float = 4.0  # Clip tối đa 4 giây
    target_clip_duration: float = 3.0  # Độ dài mục tiêu 3 giây

    sample_interval: float = 0.5  # Sample mỗi 0.5 giây (tăng độ chính xác)
    fine_sample_interval: float = 0.1  # Sample chi tiết khi tìm thấy face

    merge_gap_threshold: float = 1.0  # Merge các detection cách nhau < 1 giây
    min_confidence: float = 0.5  # Ngưỡng confidence tối thiểu

    max_clips_per_keyword: int = 10  # Số clip tối đa cho mỗi keyword
    prefer_center_face: bool = True  # Ưu tiên face ở giữa frame


class FaceSceneExtractor:
    """
    Class chính để trích xuất scenes chứa khuôn mặt nhân vật.

    Workflow:
    1. Load face database theo keyword/character name
    2. Scan video để tìm frames có nhân vật
    3. Xác định clip 2-4 giây tối ưu
    4. Export kết quả JSON tương thích với Premiere workflow
    """

    def __init__(
        self,
        faces_db_path: str = None,
        config: ExtractionConfig = None,
        log_callback: callable = None
    ):
        """
        Args:
            faces_db_path: Đường dẫn đến thư mục chứa ảnh faces database
                          Cấu trúc: faces_db/{character_name}/{images...}
            config: Cấu hình extraction
            log_callback: Callback function để log
        """
        self.faces_db_path = Path(faces_db_path) if faces_db_path else self._default_db_path()
        self.config = config or ExtractionConfig()
        self.log_callback = log_callback or print

        # Cache cho face encodings
        self._face_cache: Dict[str, List] = {}

        if not HAS_DEEPFACE:
            self.log("[ERROR] DeepFace not available. Cannot perform face detection.")

    def _default_db_path(self) -> Path:
        """Lấy đường dẫn mặc định cho faces database"""
        return Path(__file__).parent / "faces_db"

    def log(self, msg: str):
        """Log message"""
        self.log_callback(msg)

    def get_available_characters(self) -> List[str]:
        """
        Lấy danh sách các nhân vật có trong database.
        Mỗi thư mục con trong faces_db là một character.
        """
        if not self.faces_db_path.exists():
            return []

        characters = []
        for item in self.faces_db_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Kiểm tra có ảnh trong thư mục không
                images = list(item.glob("*.jpg")) + list(item.glob("*.png")) + list(item.glob("*.jpeg"))
                if images:
                    characters.append(item.name)

        return characters

    def setup_character_from_keyword(self, keyword: str) -> Optional[str]:
        """
        Map keyword sang character name trong database.
        Tìm kiếm fuzzy matching.

        Args:
            keyword: Từ khóa (có thể là tên nhân vật hoặc mô tả)

        Returns:
            Character name nếu tìm thấy, None nếu không
        """
        keyword_lower = keyword.lower().strip()
        available = self.get_available_characters()

        # Exact match
        for char in available:
            if char.lower() == keyword_lower:
                return char

        # Partial match
        for char in available:
            if keyword_lower in char.lower() or char.lower() in keyword_lower:
                return char

        # Keyword contains character name
        for char in available:
            char_parts = char.lower().split()
            if any(part in keyword_lower for part in char_parts):
                return char

        return None

    def _get_character_db_path(self, character: str) -> Optional[Path]:
        """Lấy đường dẫn DB cho character cụ thể"""
        char_path = self.faces_db_path / character
        if char_path.exists() and char_path.is_dir():
            return char_path
        return None

    def _detect_face_in_frame(
        self,
        frame: np.ndarray,
        character_db_path: Path
    ) -> Tuple[bool, float]:
        """
        Detect face trong frame và so khớp với database.

        Args:
            frame: OpenCV frame (BGR)
            character_db_path: Đường dẫn đến DB của character

        Returns:
            Tuple (found: bool, confidence: float)
        """
        if not HAS_DEEPFACE:
            return False, 0.0

        try:
            # Suppress DeepFace output
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = DeepFace.find(
                    img_path=frame,
                    db_path=str(character_db_path),
                    enforce_detection=False,
                    silent=True,
                    detector_backend='opencv',  # Faster than default
                    model_name='VGG-Face'  # Good balance of speed/accuracy
                )

            if isinstance(result, list) and len(result) > 0:
                df = result[0]
                if len(df) > 0:
                    # Lấy confidence từ khoảng cách (distance nhỏ = confidence cao)
                    # VGG-Face distance thường từ 0-1, threshold ~0.4
                    if 'distance' in df.columns:
                        min_distance = df['distance'].min()
                        confidence = max(0.0, 1.0 - min_distance)
                    elif 'VGG-Face_cosine' in df.columns:
                        min_distance = df['VGG-Face_cosine'].min()
                        confidence = max(0.0, 1.0 - min_distance)
                    else:
                        confidence = 0.7  # Default nếu không có distance

                    return True, confidence

            return False, 0.0

        except Exception as e:
            # Các lỗi như không tìm thấy face là bình thường
            return False, 0.0

    def _scan_video_for_faces(
        self,
        video_path: str,
        character: str,
        character_db_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Scan toàn bộ video để tìm frames có nhân vật.
        Sử dụng 2 phase: coarse scan + fine scan

        Returns:
            List các detection points: {time, confidence}
        """
        self.log(f"  Scanning video for '{character}'...")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.log(f"  [ERROR] Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        self.log(f"  Video: {duration:.1f}s, {fps:.1f}fps")

        detections = []

        # Phase 1: Coarse scan (mỗi sample_interval giây)
        coarse_interval = self.config.sample_interval
        coarse_frame_step = int(fps * coarse_interval)
        if coarse_frame_step < 1:
            coarse_frame_step = 1

        frame_idx = 0
        potential_regions = []  # Các vùng có khả năng có face

        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            time_sec = frame_idx / fps
            found, confidence = self._detect_face_in_frame(frame, character_db_path)

            if found and confidence >= self.config.min_confidence:
                potential_regions.append({
                    'time': time_sec,
                    'confidence': confidence
                })
                detections.append({
                    'time': time_sec,
                    'confidence': confidence,
                    'phase': 'coarse'
                })

            frame_idx += coarse_frame_step

            # Progress log
            if frame_idx % (coarse_frame_step * 20) == 0:
                progress = (frame_idx / total_frames) * 100
                self.log(f"    Coarse scan: {progress:.0f}% ({len(potential_regions)} regions found)")

        self.log(f"  Coarse scan complete: {len(potential_regions)} potential regions")

        # Phase 2: Fine scan trong các vùng tiềm năng
        if potential_regions:
            fine_interval = self.config.fine_sample_interval
            fine_frame_step = max(1, int(fps * fine_interval))

            for region in potential_regions:
                region_time = region['time']
                # Scan trong window ±2 giây
                start_time = max(0, region_time - 2.0)
                end_time = min(duration, region_time + 2.0)

                start_frame = int(start_time * fps)
                end_frame = int(end_time * fps)

                for f_idx in range(start_frame, end_frame, fine_frame_step):
                    if f_idx == int(region_time * fps):
                        continue  # Skip đã scan

                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    time_sec = f_idx / fps
                    found, confidence = self._detect_face_in_frame(frame, character_db_path)

                    if found and confidence >= self.config.min_confidence:
                        detections.append({
                            'time': time_sec,
                            'confidence': confidence,
                            'phase': 'fine'
                        })

        cap.release()

        self.log(f"  Total detections: {len(detections)}")
        return detections

    def _merge_detections_to_clips(
        self,
        detections: List[Dict[str, Any]],
        video_duration: float
    ) -> List[Tuple[float, float, float, int]]:
        """
        Merge các detection gần nhau thành clips.

        Returns:
            List of (start_time, end_time, avg_confidence, detection_count)
        """
        if not detections:
            return []

        # Sort by time
        sorted_dets = sorted(detections, key=lambda x: x['time'])

        # Merge liên tiếp
        clusters = []
        current_cluster = [sorted_dets[0]]

        for det in sorted_dets[1:]:
            if det['time'] - current_cluster[-1]['time'] <= self.config.merge_gap_threshold:
                current_cluster.append(det)
            else:
                clusters.append(current_cluster)
                current_cluster = [det]

        clusters.append(current_cluster)

        # Convert clusters to clips
        clips = []
        for cluster in clusters:
            times = [d['time'] for d in cluster]
            confidences = [d['confidence'] for d in cluster]

            center_time = sum(times) / len(times)
            avg_confidence = sum(confidences) / len(confidences)

            # Tạo clip 2-4 giây xung quanh center
            half_duration = self.config.target_clip_duration / 2

            start_time = max(0, center_time - half_duration)
            end_time = min(video_duration, center_time + half_duration)

            # Điều chỉnh để đảm bảo duration trong range
            actual_duration = end_time - start_time

            if actual_duration < self.config.min_clip_duration:
                # Mở rộng nếu quá ngắn
                if start_time == 0:
                    end_time = min(video_duration, self.config.min_clip_duration)
                else:
                    start_time = max(0, end_time - self.config.min_clip_duration)
            elif actual_duration > self.config.max_clip_duration:
                # Thu hẹp nếu quá dài
                center = (start_time + end_time) / 2
                start_time = center - self.config.max_clip_duration / 2
                end_time = center + self.config.max_clip_duration / 2

            clips.append((start_time, end_time, avg_confidence, len(cluster)))

        return clips

    def extract_character_clips(
        self,
        video_path: str,
        keyword: str
    ) -> List[FaceClip]:
        """
        Trích xuất clips 2-4 giây chứa nhân vật từ video.

        Args:
            video_path: Đường dẫn video
            keyword: Từ khóa/tên nhân vật

        Returns:
            List các FaceClip
        """
        self.log(f"\n[extract_character_clips] Video: {os.path.basename(video_path)}")
        self.log(f"  Keyword: '{keyword}'")

        # Map keyword -> character
        character = self.setup_character_from_keyword(keyword)
        if not character:
            self.log(f"  [WARNING] Character not found in database for keyword: {keyword}")
            self.log(f"  Available characters: {self.get_available_characters()}")
            return []

        self.log(f"  Matched character: '{character}'")

        # Get character DB path
        char_db_path = self._get_character_db_path(character)
        if not char_db_path:
            self.log(f"  [ERROR] Database path not found for: {character}")
            return []

        # Get video duration
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps if fps > 0 else 0
        cap.release()

        # Scan video
        detections = self._scan_video_for_faces(video_path, character, char_db_path)

        if not detections:
            self.log(f"  No faces detected for '{character}'")
            return []

        # Merge to clips
        raw_clips = self._merge_detections_to_clips(detections, video_duration)

        # Convert to FaceClip objects
        clips = []
        for start, end, conf, count in raw_clips:
            clip = FaceClip(
                character=character,
                video_path=video_path,
                start_time=round(start, 2),
                end_time=round(end, 2),
                duration=round(end - start, 2),
                confidence=round(conf, 3),
                face_count=count,
                center_time=round((start + end) / 2, 2)
            )
            clips.append(clip)

        # Sort by confidence và limit
        clips.sort(key=lambda x: x.confidence, reverse=True)
        clips = clips[:self.config.max_clips_per_keyword]

        self.log(f"  Extracted {len(clips)} clips for '{character}'")
        for i, clip in enumerate(clips):
            self.log(f"    [{i+1}] {clip.start_time:.1f}s - {clip.end_time:.1f}s "
                    f"(dur: {clip.duration:.1f}s, conf: {clip.confidence:.2f})")

        return clips

    def process_keywords_batch(
        self,
        keywords_data: List[Dict[str, Any]],
        video_pool: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Xử lý batch keywords và tìm clips từ video pool.
        Tương thích với format của video_scene_matcher.

        Args:
            keywords_data: List of {keyword, start_seconds, end_seconds, duration_seconds}
            video_pool: List đường dẫn video

        Returns:
            Dict mapping keyword -> list of matched clips với scenes
        """
        results = {}

        self.log(f"\n{'='*50}")
        self.log(f"FACE SCENE EXTRACTION - Processing {len(keywords_data)} keywords")
        self.log(f"Video pool: {len(video_pool)} videos")
        self.log(f"{'='*50}")

        for kw_item in keywords_data:
            keyword = kw_item.get("keyword", "")
            required_duration = kw_item.get("duration_seconds", 3.0)

            self.log(f"\n>>> Keyword: '{keyword}' (need {required_duration:.1f}s clip)")

            # Kiểm tra keyword có phải là character không
            character = self.setup_character_from_keyword(keyword)

            if not character:
                self.log(f"  [SKIP] No character match for keyword")
                results[keyword] = []
                continue

            keyword_matches = []

            for video_path in video_pool:
                if not os.path.exists(video_path):
                    continue

                clips = self.extract_character_clips(video_path, keyword)

                for clip in clips:
                    # Điều chỉnh duration nếu cần
                    adjusted_start = clip.start_time
                    adjusted_end = clip.end_time

                    # Đảm bảo clip duration phù hợp với required_duration
                    if clip.duration < required_duration:
                        # Mở rộng clip nếu có thể
                        need_more = required_duration - clip.duration
                        adjusted_start = max(0, clip.start_time - need_more / 2)
                        adjusted_end = clip.end_time + need_more / 2
                    elif clip.duration > required_duration:
                        # Thu hẹp clip
                        center = clip.center_time
                        half_dur = required_duration / 2
                        adjusted_start = center - half_dur
                        adjusted_end = center + half_dur

                    match_entry = {
                        "video_path": video_path,
                        "confidence": clip.confidence,
                        "reason": f"Face detected: {clip.character} ({clip.face_count} detections)",
                        "character": clip.character,
                        "suggested_scenes": [{
                            "start_time": round(adjusted_start, 2),
                            "end_time": round(adjusted_end, 2),
                            "duration": round(adjusted_end - adjusted_start, 2),
                            "description": f"Face clip of {clip.character}",
                            "original_clip": {
                                "start": clip.start_time,
                                "end": clip.end_time,
                                "duration": clip.duration
                            }
                        }]
                    }
                    keyword_matches.append(match_entry)

            # Sort by confidence
            keyword_matches.sort(key=lambda x: x['confidence'], reverse=True)
            results[keyword] = keyword_matches

            self.log(f"  Total matches for '{keyword}': {len(keyword_matches)}")

        return results

    def export_for_premiere(
        self,
        matches: Dict[str, List[Dict[str, Any]]],
        keywords_data: List[Dict[str, Any]],
        output_path: str
    ):
        """
        Export kết quả sang JSON format tương thích với Premiere workflow.

        Format output giống scene_matches.json của video_scene_matcher
        """
        output_data = {
            "version": "1.0",
            "extraction_type": "face_recognition",
            "config": {
                "min_clip_duration": self.config.min_clip_duration,
                "max_clip_duration": self.config.max_clip_duration,
                "target_clip_duration": self.config.target_clip_duration,
                "min_confidence": self.config.min_confidence
            },
            "keywords": keywords_data,
            "matches": matches
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        self.log(f"\nExported results to: {output_path}")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Face Scene Extractor - Extract 2-4s clips by face recognition")
    parser.add_argument("--keywords-json", required=True, help="Path to keywords JSON (from Track 3)")
    parser.add_argument("--video-folder", required=True, help="Folder containing videos")
    parser.add_argument("--faces-db", help="Path to faces database folder")
    parser.add_argument("--output", default="face_scene_matches.json", help="Output JSON file")
    parser.add_argument("--min-duration", type=float, default=2.0, help="Minimum clip duration (seconds)")
    parser.add_argument("--max-duration", type=float, default=4.0, help="Maximum clip duration (seconds)")
    parser.add_argument("--sample-interval", type=float, default=0.5, help="Sample interval for scanning (seconds)")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Minimum detection confidence")

    args = parser.parse_args()

    # Load keywords
    with open(args.keywords_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    keywords = data.get('keywords', [])
    print(f"Loaded {len(keywords)} keywords from {args.keywords_json}")

    # Get video pool
    video_folder = Path(args.video_folder)
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    videos = []
    for ext in video_extensions:
        videos.extend([str(f) for f in video_folder.rglob(f"*{ext}")])
    print(f"Found {len(videos)} videos in {args.video_folder}")

    # Create config
    config = ExtractionConfig(
        min_clip_duration=args.min_duration,
        max_clip_duration=args.max_duration,
        sample_interval=args.sample_interval,
        min_confidence=args.min_confidence
    )

    # Create extractor
    extractor = FaceSceneExtractor(
        faces_db_path=args.faces_db,
        config=config
    )

    # Show available characters
    characters = extractor.get_available_characters()
    print(f"Available characters in database: {characters}")

    # Process
    matches = extractor.process_keywords_batch(keywords, videos)

    # Export
    extractor.export_for_premiere(matches, keywords, args.output)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
