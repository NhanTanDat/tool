# core/project_creator.py

import os
import re
import shutil
from pathlib import Path
from typing import Dict

from . import project_data


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _slugify(text: str) -> str:
    """
    Convert 1 chuỗi topic thành slug an toàn để làm tên folder / file.
    Ví dụ: "Hoàng đế khai quốc" -> "hoang_de_khai_quoc"
    """
    text = (text or "").strip()
    if not text:
        return "project"

    text = text.lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "project"


def create_project_from_template(
    template_prproj: str,
    output_root: str,
    topic: str,
) -> Dict[str, str]:
    """
    Tạo project Premiere mới bằng cách copy 1 file template .prproj.

    template_prproj: đường dẫn tới file template.prproj
    output_root:     thư mục gốc để chứa các project mới (ví dụ D:/PremiereProjects)
    topic:           chủ đề / tên project (dùng để tạo slug)

    Trả về dict:
      - slug
      - project_dir  (folder chứa .prproj + resource)
      - project_path (.prproj mới)
      - resource_dir (folder resource cho tool)
      - data_dir     (data/<slug>)
    """
    template_path = Path(template_prproj).expanduser().resolve()
    if not template_path.is_file():
        raise FileNotFoundError(f"Template project not found: {template_path}")

    out_root = Path(output_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    slug = _slugify(topic or template_path.stem)

    project_dir = out_root / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    project_path = project_dir / f"{slug}.prproj"
    # Nếu đã tồn tại thì ghi đè (bạn có thể đổi thành raise nếu không muốn)
    shutil.copy2(template_path, project_path)

    resource_dir = project_dir / "resource"
    resource_dir.mkdir(parents=True, exist_ok=True)

    # Tạo data/<slug> và ghi marker _current_project.txt
    data_dir = project_data.ensure_project_data_dir(slug)
    project_data.write_current_project_marker(slug)

    return {
        "slug": slug,
        "project_dir": str(project_dir),
        "project_path": str(project_path),
        "resource_dir": str(resource_dir),
        "data_dir": data_dir,
    }
