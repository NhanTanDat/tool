"""
run_genmini_push_v4.py

Script helper để chạy autoCutAndPushV4.jsx với genmini_map.json
"""

import os
import sys
from pathlib import Path

# Add project root to path
THIS_DIR = Path(__file__).parent.resolve()
CORE_DIR = THIS_DIR.parent
ROOT_DIR = CORE_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.premierCore.control_jsx import run_jsx_in_premiere


def run_genmini_push_v4(
    project_path: str,
    data_folder: str,
    resource_folder: str,
    premiere_version: str = "2022",
):
    """
    Chạy autoCutAndPushV4.jsx để push videos từ genmini_map.json vào V4

    Args:
        project_path: Path to .prproj file
        data_folder: Data folder chứa genmini_map.json
        resource_folder: Resource folder chứa video files
        premiere_version: Premiere version (2022, 2023, 2024, 2025)
    """
    print("╔════════════════════════════════════════╗")
    print("║  Push Videos to V4 từ genmini_map.json ║")
    print("╚════════════════════════════════════════╝\n")

    # Validate inputs
    project_path = Path(project_path)
    data_folder = Path(data_folder)
    resource_folder = Path(resource_folder)

    if not project_path.exists():
        print(f"ERROR: Project không tồn tại: {project_path}")
        return False

    genmini_map = data_folder / "genmini_map.json"
    if not genmini_map.exists():
        print(f"ERROR: Không tìm thấy genmini_map.json: {genmini_map}")
        return False

    if not resource_folder.exists():
        print(f"ERROR: Resource folder không tồn tại: {resource_folder}")
        return False

    # Write path.txt config
    data_folder.mkdir(parents=True, exist_ok=True)
    path_txt = data_folder / "path.txt"

    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(f"data_folder={data_folder}\n")
        f.write(f"resource_folder={resource_folder}\n")
        f.write(f"project_path={project_path}\n")

    print(f"✓ Config written to: {path_txt}")
    print(f"  - Data folder: {data_folder}")
    print(f"  - Resource folder: {resource_folder}")
    print(f"  - Genmini map: {genmini_map}")

    # Run JSX
    jsx_path = CORE_DIR / "premierCore" / "autoCutAndPushV4.jsx"

    print(f"\n→ Running JSX script: {jsx_path.name}")
    print("  IMPORTANT: Đảm bảo Premiere Pro đang mở project này!")
    print("             và sequence đã được mở (active sequence)")

    success = run_jsx_in_premiere(
        str(jsx_path),
        premiere_version=premiere_version,
        wait_seconds=20  # Chờ lâu hơn vì có thể có nhiều videos
    )

    if success:
        print("\n✓✓✓ HOÀN THÀNH! Kiểm tra Track V4 trong Premiere ✓✓✓")
        return True
    else:
        print("\n✗ Script thất bại. Xem log để biết chi tiết.")
        return False


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Push videos to V4 từ genmini_map.json"
    )
    parser.add_argument("--project", required=True, help="Path to .prproj file")
    parser.add_argument("--data-folder", required=True, help="Data folder")
    parser.add_argument(
        "--resource-folder", required=True, help="Resource folder with videos"
    )
    parser.add_argument(
        "--premiere-version",
        default="2022",
        help="Premiere version (2022, 2023, 2024, 2025)",
    )

    args = parser.parse_args()

    success = run_genmini_push_v4(
        project_path=args.project,
        data_folder=args.data_folder,
        resource_folder=args.resource_folder,
        premiere_version=args.premiere_version,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
