import os
import csv
import json
from pathlib import Path
from typing import List

from openai import OpenAI

# =============================
# HÀM HELPER: LẤY JSON THUẦN
# =============================

def _extract_json_block(raw: str) -> str:
    """
    Làm sạch output của model:
    - Bỏ ```json / ``` nếu có
    - Cắt từ dấu '{' đầu tiên đến '}' cuối cùng
    để còn lại 1 JSON object thuần cho json.loads.
    """
    if not raw:
        return raw

    raw = raw.strip()

    # Nếu có ``` hoặc ```json thì bỏ các dòng fence
    if raw.startswith("```"):
        lines = raw.splitlines()
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                continue
            cleaned_lines.append(line)
        raw = "\n".join(cleaned_lines).strip()

    # Fallback: cắt từ '{' đầu tiên tới '}' cuối cùng
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end >= start:
        raw = raw[start:end + 1].strip()

    return raw


# =============================
# ĐỊNH NGHĨA ĐƯỜNG DẪN GỐC
# =============================

# ROOT_DIR = thư mục gốc của project autotool
# (autotool/core/ai/gen_timeline_from_list.py => parents[2] = autotool)
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
CURRENT_PROJECT_FILE = DATA_DIR / "_current_project.txt"

# Tự load file .env ở ROOT_DIR (nếu có)
env_path = ROOT_DIR / ".env"
if env_path.exists():
    try:
        for _line in env_path.read_text(encoding="utf-8").splitlines():
            line = _line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception as _e:
        # Không cần kill script nếu .env lỗi, chỉ in cảnh báo khi chạy tay
        print(f"[WARN] Không đọc được .env: {_e}")


# =============================
# HÀM TRỢ GIÚP
# =============================

def get_current_project_slug() -> str:
    """
    Đọc project_slug từ data/_current_project.txt.
    GUI đã gọi write_current_project_marker(slug) trước khi gọi AI.
    Nếu file không có, thử đoán từ tên thư mục trong data (khi chỉ chạy tay).
    """
    if CURRENT_PROJECT_FILE.exists():
        slug = CURRENT_PROJECT_FILE.read_text(encoding="utf-8").strip()
        if slug:
            return slug

    # Fallback khi chạy tay: nếu có đúng 1 thư mục con trong data -> dùng nó
    if DATA_DIR.exists():
        dirs = [p.name for p in DATA_DIR.iterdir() if p.is_dir()]
        if len(dirs) == 1:
            return dirs[0]

    raise RuntimeError(
        f"Không xác định được project_slug. "
        f"Không tìm thấy hoặc rỗng: {CURRENT_PROJECT_FILE}"
    )


def get_client() -> OpenAI:
    """
    Lấy OpenAI client chỉ từ biến môi trường / file .env.

    Ưu tiên theo thứ tự:
    - OPENAI_API_KEY_TIMELINE  (key riêng cho timeline nếu muốn)
    - OPENAI_API_KEY_TL
    - OPENAI_API_KEY2
    - OPENAI_API_KEY

    => Tất cả đều đọc từ biến môi trường, mà biến này đã load từ .env ở trên.
    Không dùng data/openai_key.txt nữa.
    """
    key_candidates = [
        "OPENAI_API_KEY_TIMELINE",
        "OPENAI_API_KEY_TL",
        "OPENAI_API_KEY2",
        "OPENAI_API_KEY",
    ]

    api_key = None
    used_var = None
    for var_name in key_candidates:
        val = os.getenv(var_name)
        if val:
            api_key = val.strip()
            used_var = var_name
            break

    if not api_key:
        raise RuntimeError(
            "Không tìm thấy API key trong biến môi trường / file .env.\n"
            "- Hãy thêm vào file .env ở thư mục gốc autotool, ví dụ:\n"
            "    OPENAI_API_KEY=sk-...\n"
            "hoặc:\n"
            "    OPENAI_API_KEY_TIMELINE=sk-...\n"
        )

    # Debug (ẩn bớt key cho an toàn)
    display_key = (
        api_key[:5] + "..." + api_key[-4:]
        if len(api_key) > 12 else "********"
    )
    print(f"[DEBUG] Đang dùng OpenAI API key từ biến môi trường {used_var} (file .env: {env_path})")
    print(f"[DEBUG] Key = {display_key}")

    return OpenAI(api_key=api_key)


def load_keywords(project_slug: str) -> List[str]:
    txt_path = DATA_DIR / project_slug / "list_name.txt"
    if not txt_path.exists():
        return []
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip()]


def save_keywords(project_slug: str, keywords: List[str]) -> None:
    txt_path = DATA_DIR / project_slug / "list_name.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with txt_path.open("w", encoding="utf-8") as f:
        for kw in keywords:
            f.write(kw.strip() + "\n")


# =============================
# AI: TOPIC -> KEYWORDS
# =============================

def ai_expand_topic_to_keywords(client: OpenAI, topic: str, n_keywords: int = 25) -> List[str]:
    """
    Dùng AI để biến 1 TOPIC thành nhiều KEYWORD liên quan.
    """
    system_prompt = "You are a helpful assistant that outputs ONLY JSON. No explanation."
    user_prompt = f"""
Tôi có một chủ đề video như sau:

\"{topic}\"

Hãy nghĩ ra một danh sách khoảng {n_keywords} keyword/ngữ cảnh NGẮN GỌN, tiếng Việt,
liên quan chặt chẽ đến chủ đề này, có thể dùng để tìm clip hoặc hình ảnh minh họa.

Trả về JSON đúng cấu trúc:
{{
  "keywords": [
    "keyword 1",
    "keyword 2",
    ...
  ]
}}

CHỈ TRẢ VỀ JSON, KHÔNG THÊM GIẢI THÍCH.
    """.strip()

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = resp.output[0].content[0].text
    cleaned = _extract_json_block(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"AI trả JSON không hợp lệ (keywords): {e}\nNội dung: {raw[:500]}"
        )

    kws = data.get("keywords", [])
    if not isinstance(kws, list):
        raise RuntimeError("JSON không có trường 'keywords' dạng list")

    return [str(k).strip() for k in kws if str(k).strip()]


# =============================
# AI: KEYWORDS -> TIMELINE
# =============================

def build_timeline_prompt(keywords: List[str]) -> str:
    joined = "\n".join(f"- {kw}" for kw in keywords)
    return f"""
Bạn là editor video chuyên nghiệp.

Tôi có danh sách KEYWORD cho một video:
{joined}

Hãy chia video thành các SCENE theo thứ tự hợp lý.
Mỗi scene có cấu trúc JSON như sau:
{{
  "scene_index": number,          // 1,2,3,...
  "keyword": string,              // keyword chính, phải nằm trong list tôi gửi
  "duration_sec": number,         // độ dài đoạn này, giây (6-12s tuỳ nội dung)
  "search_query": string,         // câu search YouTube/stock image
  "voiceover": string             // nội dung voiceover/caption
}}

Trả về JSON với cấu trúc:
{{
  "scenes": [ ... ]
}}

Yêu cầu:
- Tổng thời lượng khoảng 180–240 giây (3–4 phút).
- Nội dung mạch lạc, dễ hiểu.
- "search_query" nên chi tiết hơn keyword (thêm mô tả, bối cảnh...).
- CHỈ TRẢ VỀ JSON, KHÔNG THÊM TEXT NÀO KHÁC.
    """.strip()


def call_ai_for_timeline(client: OpenAI, keywords: List[str]) -> List[dict]:
    system_prompt = "You are a helpful video editor AI that outputs strict JSON only."
    prompt = build_timeline_prompt(keywords)

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    raw = resp.output[0].content[0].text
    cleaned = _extract_json_block(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"AI trả JSON không hợp lệ (timeline): {e}\nNội dung: {raw[:500]}"
        )

    scenes = data.get("scenes")
    if not isinstance(scenes, list):
        raise RuntimeError("JSON không có trường 'scenes' dạng list")

    norm_scenes: List[dict] = []
    for scene in scenes:
        try:
            norm_scenes.append(
                {
                    "scene_index": int(scene.get("scene_index")),
                    "keyword": str(scene.get("keyword", "")).strip(),
                    "duration_sec": float(scene.get("duration_sec", 0)) or 0,
                    "search_query": str(scene.get("search_query", "")).strip(),
                    "voiceover": str(scene.get("voiceover", "")).strip(),
                }
            )
        except Exception as e:
            print("Bỏ qua scene lỗi:", scene, "->", e)
    return norm_scenes


def save_csv(project_slug: str, scenes: List[dict]) -> Path:
    """
    Ghi ra timeline_export_merged.csv.
    Nếu cutAndPush.jsx dùng header khác, sửa fieldnames cho khớp.
    """
    out_path = DATA_DIR / project_slug / "timeline_export_merged.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "scene_index",
        "keyword",
        "duration_sec",
        "search_query",
        "voiceover",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for scene in scenes:
            writer.writerow(scene)

    return out_path


# =============================
# MAIN
# =============================

def main():
    print("=== GEN KEYWORDS + TIMELINE (AI mode) ===")
    project_slug = get_current_project_slug()
    print(f"- project_slug: {project_slug}")

    client = get_client()

    keywords = load_keywords(project_slug)
    print(f"- Đọc được {len(keywords)} dòng từ list_name.txt")

    # Nếu <= 1 dòng => coi là TOPIC -> nhờ AI expand
    if len(keywords) <= 1:
        if len(keywords) == 1:
            topic = keywords[0]
            print(f"- Dùng dòng duy nhất trong list_name.txt làm chủ đề: {topic}")
        else:
            topic = project_slug
            print(f"- list_name.txt rỗng, dùng project_slug làm chủ đề: {topic}")

        new_keywords = ai_expand_topic_to_keywords(client, topic, n_keywords=25)
        print(f"- AI sinh ra {len(new_keywords)} keyword từ chủ đề.")
        save_keywords(project_slug, new_keywords)
        keywords = new_keywords
    else:
        print("- Đã có sẵn danh sách keyword, bỏ qua bước sinh keyword từ topic.")

    scenes = call_ai_for_timeline(client, keywords)
    print(f"- AI trả về {len(scenes)} scene")

    out_path = save_csv(project_slug, scenes)
    print(f"✅ Đã sinh file timeline_export_merged.csv tại:\n   {out_path}")


if __name__ == "__main__":
    main()
