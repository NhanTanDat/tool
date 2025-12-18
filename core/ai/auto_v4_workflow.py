"""
auto_v4_workflow.py

Orchestrator cho workflow mới:
1. Extract keywords từ Track 3 trong Premiere (via JSX)
2. AI analyze videos và match với keywords
3. Auto cut và push scenes vào V4 (via JSX)
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Callable

# Add project root to path
THIS_DIR = Path(__file__).parent.resolve()
CORE_DIR = THIS_DIR.parent
ROOT_DIR = CORE_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.ai.video_scene_matcher import (
    VideoSceneMatcher,
    load_keywords_from_json,
    get_video_pool_from_folder,
)


class AutoV4Workflow:
    """
    Workflow orchestrator cho AI-based auto editing
    """

    def __init__(
        self,
        project_path: str,
        data_folder: str,
        resource_folder: str,
        gemini_api_key: Optional[str] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.project_path = Path(project_path)
        self.data_folder = Path(data_folder)
        self.resource_folder = Path(resource_folder)
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")

        self.log_callback = log_callback or print

        # File paths
        self.track3_keywords_json = self.data_folder / "track3_keywords.json"
        self.scene_matches_json = self.data_folder / "scene_matches.json"

        # JSX scripts
        self.jsx_extract_track3 = CORE_DIR / "premierCore" / "extractTrack3Keywords.jsx"
        self.jsx_auto_cut_v4 = CORE_DIR / "premierCore" / "autoCutAndPushV4.jsx"

    def log(self, msg: str):
        """Log với callback"""
        self.log_callback(msg)

    def run_jsx_script(self, jsx_path: Path) -> bool:
        """
        Chạy JSX script thông qua ExtendScript command line hoặc automation.

        Có 2 cách:
        1. Dùng pywinauto để tự động hóa VS Code (giống control.py)
        2. Dùng Adobe ExtendScript Toolkit CLI (nếu có)

        Ở đây ta dùng cách đơn giản: in hướng dẫn cho user chạy manual
        hoặc tích hợp với control.py
        """
        self.log(f"[run_jsx_script] {jsx_path.name}")

        if not jsx_path.exists():
            self.log(f"ERROR: JSX script not found: {jsx_path}")
            return False

        # TODO: Tích hợp với control.py để tự động chạy JSX
        # Hiện tại: hướng dẫn manual
        self.log(f"  → Cần chạy script này trong Premiere Pro:")
        self.log(f"     {jsx_path}")
        self.log(f"  → Hoặc dùng VS Code ExtendScript Debugger")

        # Placeholder: giả sử script đã chạy thành công
        # Trong production, cần implement automation thực sự
        return True

    def step1_extract_track3_keywords(self) -> bool:
        """
        Bước 1: Extract keywords từ Track 3
        """
        self.log("\n=== STEP 1: Extract Keywords từ Track 3 ===")

        # Chạy JSX script
        success = self.run_jsx_script(self.jsx_extract_track3)

        if not success:
            self.log("ERROR: Không chạy được extractTrack3Keywords.jsx")
            return False

        # Chờ file output
        self.log("Đang chờ file track3_keywords.json...")
        for i in range(30):  # Chờ tối đa 30 giây
            if self.track3_keywords_json.exists():
                self.log(f"✓ Tìm thấy: {self.track3_keywords_json}")
                break
            time.sleep(1)
        else:
            self.log("ERROR: Timeout - không tìm thấy track3_keywords.json")
            return False

        # Validate
        try:
            keywords = load_keywords_from_json(str(self.track3_keywords_json))
            self.log(f"✓ Loaded {len(keywords)} keywords")
            return True
        except Exception as e:
            self.log(f"ERROR: Không đọc được keywords: {e}")
            return False

    def step2_ai_match_videos(self) -> bool:
        """
        Bước 2: AI analyze videos và match với keywords
        """
        self.log("\n=== STEP 2: AI Match Videos với Keywords ===")

        # Load keywords
        try:
            keywords = load_keywords_from_json(str(self.track3_keywords_json))
            self.log(f"Keywords: {len(keywords)}")
        except Exception as e:
            self.log(f"ERROR: Không load được keywords: {e}")
            return False

        # Get video pool
        videos = get_video_pool_from_folder(str(self.resource_folder))
        self.log(f"Video pool: {len(videos)} videos")

        if len(videos) == 0:
            self.log("WARNING: Không có video nào trong resource folder")
            return False

        # Create matcher
        matcher = VideoSceneMatcher(gemini_api_key=self.gemini_api_key)

        # Find matches
        self.log("Đang phân tích videos...")
        matches = matcher.find_best_scenes_for_keywords(keywords, videos)

        # Save results
        output_data = {
            "keywords": keywords,
            "matches": matches,
        }

        try:
            with open(self.scene_matches_json, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            self.log(f"✓ Đã lưu kết quả: {self.scene_matches_json}")
            return True
        except Exception as e:
            self.log(f"ERROR: Không lưu được scene_matches.json: {e}")
            return False

    def step3_auto_cut_push_v4(self) -> bool:
        """
        Bước 3: Auto cut và push vào V4
        """
        self.log("\n=== STEP 3: Auto Cut và Push vào V4 ===")

        # Chạy JSX script
        success = self.run_jsx_script(self.jsx_auto_cut_v4)

        if not success:
            self.log("ERROR: Không chạy được autoCutAndPushV4.jsx")
            return False

        self.log("✓ Đã hoàn thành auto cut và push vào V4")
        return True

    def run_full_workflow(self) -> bool:
        """
        Chạy toàn bộ workflow
        """
        self.log("╔════════════════════════════════════════╗")
        self.log("║   AUTO V4 WORKFLOW - AI POWERED        ║")
        self.log("╚════════════════════════════════════════╝")

        # Validate inputs
        if not self.project_path.exists():
            self.log(f"ERROR: Project không tồn tại: {self.project_path}")
            return False

        if not self.resource_folder.exists():
            self.log(f"ERROR: Resource folder không tồn tại: {self.resource_folder}")
            return False

        # Ensure data folder
        self.data_folder.mkdir(parents=True, exist_ok=True)

        # Step 1: Extract keywords
        if not self.step1_extract_track3_keywords():
            return False

        # Step 2: AI match
        if not self.step2_ai_match_videos():
            return False

        # Step 3: Auto cut and push
        if not self.step3_auto_cut_push_v4():
            return False

        self.log("\n✓✓✓ WORKFLOW HOÀN THÀNH ✓✓✓")
        return True


def main():
    """
    CLI entry point
    """
    import argparse

    parser = argparse.ArgumentParser(description="Auto V4 Workflow")
    parser.add_argument("--project", required=True, help="Path to .prproj file")
    parser.add_argument("--data-folder", required=True, help="Data folder")
    parser.add_argument("--resource-folder", required=True, help="Resource folder with videos")
    parser.add_argument("--gemini-key", help="Gemini API key")

    args = parser.parse_args()

    workflow = AutoV4Workflow(
        project_path=args.project,
        data_folder=args.data_folder,
        resource_folder=args.resource_folder,
        gemini_api_key=args.gemini_key,
    )

    success = workflow.run_full_workflow()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
