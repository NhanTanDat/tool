"""
face_v4_workflow.py

Workflow tối ưu sử dụng Face Recognition để:
1. Nhận keyword/tên nhân vật từ Track 3
2. Quét video tìm khuôn mặt nhân vật
3. Trích xuất clips 2-4 giây chứa nhân vật
4. Push vào Track V4 trong Premiere

Tích hợp với auto_v4_workflow nhưng sử dụng face detection thay vì AI text matching.
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

from core.faceDetect.face_scene_extractor import (
    FaceSceneExtractor,
    ExtractionConfig,
    FaceClip
)
from core.ai.video_scene_matcher import (
    load_keywords_from_json,
    get_video_pool_from_folder,
)


class FaceV4Workflow:
    """
    Workflow sử dụng Face Recognition để tìm và cắt scenes chứa nhân vật.

    So với AutoV4Workflow:
    - Thay vì dùng AI text matching (Gemini), dùng face recognition (DeepFace)
    - Clips được trích xuất chính xác 2-4 giây
    - Cần setup faces_db với ảnh nhân vật trước
    """

    def __init__(
        self,
        project_path: str,
        data_folder: str,
        resource_folder: str,
        faces_db_path: str = None,
        min_clip_duration: float = 2.0,
        max_clip_duration: float = 4.0,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            project_path: Đường dẫn đến file .prproj
            data_folder: Thư mục data (chứa output JSON)
            resource_folder: Thư mục chứa video nguồn
            faces_db_path: Đường dẫn đến thư mục faces_db (chứa ảnh nhân vật)
            min_clip_duration: Độ dài clip tối thiểu (giây)
            max_clip_duration: Độ dài clip tối đa (giây)
            log_callback: Callback để log
        """
        self.project_path = Path(project_path)
        self.data_folder = Path(data_folder)
        self.resource_folder = Path(resource_folder)
        self.faces_db_path = Path(faces_db_path) if faces_db_path else None

        self.log_callback = log_callback or print

        # Config
        self.config = ExtractionConfig(
            min_clip_duration=min_clip_duration,
            max_clip_duration=max_clip_duration,
            target_clip_duration=(min_clip_duration + max_clip_duration) / 2,
        )

        # File paths
        self.track3_keywords_json = self.data_folder / "track3_keywords.json"
        self.face_matches_json = self.data_folder / "face_scene_matches.json"
        self.scene_matches_json = self.data_folder / "scene_matches.json"  # Compatible format

        # JSX scripts
        self.jsx_extract_track3 = CORE_DIR / "premierCore" / "extractTrack3Keywords.jsx"
        self.jsx_auto_cut_v4 = CORE_DIR / "premierCore" / "autoCutAndPushV4.jsx"

        # Face extractor
        self.extractor = None

    def log(self, msg: str):
        """Log với callback"""
        self.log_callback(msg)

    def _init_extractor(self):
        """Khởi tạo FaceSceneExtractor"""
        if self.extractor is None:
            self.extractor = FaceSceneExtractor(
                faces_db_path=str(self.faces_db_path) if self.faces_db_path else None,
                config=self.config,
                log_callback=self.log
            )

    def run_jsx_script(self, jsx_path: Path, wait_seconds: int = 10) -> bool:
        """
        Chạy JSX script thông qua VS Code ExtendScript.
        """
        self.log(f"[run_jsx_script] {jsx_path.name}")

        if not jsx_path.exists():
            self.log(f"ERROR: JSX script not found: {jsx_path}")
            return False

        try:
            from core.premierCore.control_jsx import run_jsx_in_premiere

            self.log(f"  -> Running via VS Code ExtendScript...")
            success = run_jsx_in_premiere(
                str(jsx_path),
                premiere_version="2022",
                wait_seconds=wait_seconds
            )

            if success:
                self.log(f"  [OK] Script completed!")
            else:
                self.log(f"  [FAIL] Script failed")

            return success

        except Exception as e:
            self.log(f"ERROR: Cannot run JSX automatically: {e}")
            self.log(f"  -> Please run manually: {jsx_path}")
            return False

    def check_faces_database(self) -> List[str]:
        """
        Kiểm tra faces database và trả về danh sách characters có sẵn.
        """
        self._init_extractor()
        characters = self.extractor.get_available_characters()

        self.log(f"\n[Faces Database Check]")
        if self.faces_db_path:
            self.log(f"  Path: {self.faces_db_path}")
        else:
            self.log(f"  Path: {self.extractor.faces_db_path} (default)")

        if characters:
            self.log(f"  Available characters ({len(characters)}):")
            for char in characters:
                self.log(f"    - {char}")
        else:
            self.log(f"  [WARNING] No characters found in database!")
            self.log(f"  Setup: Create folders with character names in faces_db/")
            self.log(f"         Add face images (jpg/png) to each folder")

        return characters

    def step1_extract_track3_keywords(self) -> bool:
        """
        Bước 1: Extract keywords từ Track 3 (TỰ ĐỘNG)
        """
        self.log("\n=== STEP 1: Extract Keywords từ Track 3 ===")

        success = self.run_jsx_script(self.jsx_extract_track3, wait_seconds=15)

        if not success:
            self.log("ERROR: Không chạy được extractTrack3Keywords.jsx")
            return False

        self.log("Waiting for file to be written...")
        time.sleep(2)

        if not self.track3_keywords_json.exists():
            self.log(f"ERROR: File not found: {self.track3_keywords_json}")
            return False

        try:
            keywords = load_keywords_from_json(str(self.track3_keywords_json))
            self.log(f"[OK] Loaded {len(keywords)} keywords")

            # Show keywords
            for kw in keywords[:5]:  # Show first 5
                self.log(f"  - '{kw.get('keyword', '')}' ({kw.get('duration_seconds', 0):.1f}s)")
            if len(keywords) > 5:
                self.log(f"  ... and {len(keywords) - 5} more")

            return len(keywords) > 0

        except Exception as e:
            self.log(f"ERROR: Cannot read keywords: {e}")
            return False

    def step2_face_match_videos(self) -> bool:
        """
        Bước 2: Sử dụng Face Recognition để tìm clips chứa nhân vật
        """
        self.log("\n=== STEP 2: Face Recognition Match ===")

        self._init_extractor()

        # Check database
        characters = self.check_faces_database()
        if not characters:
            self.log("ERROR: No characters in faces database. Cannot proceed.")
            return False

        # Load keywords
        try:
            keywords = load_keywords_from_json(str(self.track3_keywords_json))
            self.log(f"\nKeywords to process: {len(keywords)}")
        except Exception as e:
            self.log(f"ERROR: Cannot load keywords: {e}")
            return False

        # Get video pool
        videos = get_video_pool_from_folder(str(self.resource_folder))
        self.log(f"Video pool: {len(videos)} videos")

        if not videos:
            self.log("WARNING: No videos in resource folder")
            return False

        # Process with face detection
        self.log("\n--- Starting Face Detection ---")
        matches = self.extractor.process_keywords_batch(keywords, videos)

        # Export both formats (for compatibility)
        # 1. Face-specific format
        self.extractor.export_for_premiere(
            matches, keywords, str(self.face_matches_json)
        )

        # 2. Compatible format for autoCutAndPushV4.jsx
        compatible_output = {
            "keywords": keywords,
            "matches": matches
        }

        with open(self.scene_matches_json, 'w', encoding='utf-8') as f:
            json.dump(compatible_output, f, ensure_ascii=False, indent=2)

        self.log(f"[OK] Saved: {self.face_matches_json}")
        self.log(f"[OK] Saved: {self.scene_matches_json} (compatible)")

        # Summary
        total_clips = sum(len(m) for m in matches.values())
        self.log(f"\n--- Summary ---")
        self.log(f"Keywords processed: {len(keywords)}")
        self.log(f"Total clips found: {total_clips}")

        for keyword, clips in matches.items():
            if clips:
                self.log(f"  '{keyword}': {len(clips)} clips")

        return True

    def step3_auto_cut_push_v4(self) -> bool:
        """
        Bước 3: Auto cut và push vào V4
        """
        self.log("\n=== STEP 3: Auto Cut và Push vào V4 ===")

        success = self.run_jsx_script(self.jsx_auto_cut_v4, wait_seconds=20)

        if not success:
            self.log("ERROR: Không chạy được autoCutAndPushV4.jsx")
            return False

        self.log("[OK] Completed auto cut and push to V4")
        self.log("[OK] Check Track V4 in Premiere to see results!")
        return True

    def run_full_workflow(self) -> bool:
        """
        Chạy toàn bộ workflow Face Recognition V4
        """
        self.log("=" * 50)
        self.log("  FACE RECOGNITION V4 WORKFLOW")
        self.log("  Clips: 2-4 seconds")
        self.log("=" * 50)

        # Validate inputs
        if not self.project_path.exists():
            self.log(f"ERROR: Project not found: {self.project_path}")
            return False

        if not self.resource_folder.exists():
            self.log(f"ERROR: Resource folder not found: {self.resource_folder}")
            return False

        # Ensure data folder
        self.data_folder.mkdir(parents=True, exist_ok=True)

        # Check faces database first
        characters = self.check_faces_database()
        if not characters:
            self.log("\n[SETUP REQUIRED]")
            self.log("Please add character faces to the database:")
            self.log(f"  1. Create folder: faces_db/<character_name>/")
            self.log(f"  2. Add face images (jpg/png) to the folder")
            self.log(f"  3. Run this workflow again")
            return False

        # Step 1: Extract keywords
        if not self.step1_extract_track3_keywords():
            return False

        # Step 2: Face match
        if not self.step2_face_match_videos():
            return False

        # Step 3: Auto cut and push
        if not self.step3_auto_cut_push_v4():
            return False

        self.log("\n" + "=" * 50)
        self.log("  WORKFLOW COMPLETED!")
        self.log("=" * 50)
        return True

    def run_face_detection_only(self) -> Dict[str, Any]:
        """
        Chỉ chạy face detection (không cần Premiere).
        Hữu ích để test hoặc tiền xử lý.

        Returns:
            Dict với kết quả detection
        """
        self.log("\n=== FACE DETECTION ONLY MODE ===")

        self._init_extractor()

        # Check database
        characters = self.check_faces_database()
        if not characters:
            return {"error": "No characters in database"}

        # Get videos
        videos = get_video_pool_from_folder(str(self.resource_folder))
        if not videos:
            return {"error": "No videos found"}

        self.log(f"\nFound {len(videos)} videos")
        self.log(f"Processing for characters: {characters}")

        # Process each character
        results = {}

        for character in characters:
            self.log(f"\n--- Processing: {character} ---")
            character_clips = []

            for video_path in videos:
                clips = self.extractor.extract_character_clips(video_path, character)
                for clip in clips:
                    character_clips.append({
                        "video": os.path.basename(clip.video_path),
                        "video_path": clip.video_path,
                        "start": clip.start_time,
                        "end": clip.end_time,
                        "duration": clip.duration,
                        "confidence": clip.confidence
                    })

            results[character] = character_clips
            self.log(f"  Found {len(character_clips)} clips for {character}")

        return results


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Face Recognition V4 Workflow")
    parser.add_argument("--project", required=True, help="Path to .prproj file")
    parser.add_argument("--data-folder", required=True, help="Data folder")
    parser.add_argument("--resource-folder", required=True, help="Resource folder with videos")
    parser.add_argument("--faces-db", help="Path to faces database")
    parser.add_argument("--min-duration", type=float, default=2.0, help="Min clip duration")
    parser.add_argument("--max-duration", type=float, default=4.0, help="Max clip duration")
    parser.add_argument("--detect-only", action="store_true", help="Only run face detection (no Premiere)")

    args = parser.parse_args()

    workflow = FaceV4Workflow(
        project_path=args.project,
        data_folder=args.data_folder,
        resource_folder=args.resource_folder,
        faces_db_path=args.faces_db,
        min_clip_duration=args.min_duration,
        max_clip_duration=args.max_duration,
    )

    if args.detect_only:
        results = workflow.run_face_detection_only()
        print("\n" + "=" * 50)
        print("DETECTION RESULTS:")
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        success = workflow.run_full_workflow()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
