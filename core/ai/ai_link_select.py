import json
from typing import List, Dict, Any

from core.ai.gen_timeline_from_list import get_client, _extract_json_block


def _build_video_items_text(candidates: List[Dict[str, Any]]) -> str:
    """
    Format list candidate cho LLM đọc:

    0. title='...', duration=123s, channel='...', url='...'
    """
    lines: List[str] = []
    for idx, c in enumerate(candidates):
        title = c.get("title") or ""
        url = c.get("url") or ""
        channel = c.get("channel") or ""
        dur = c.get("duration_seconds")
        if dur is None:
            dur_str = "unknown"
        else:
            dur_str = f"{int(dur)}s"

        lines.append(
            f"{idx}. title={title!r}, duration={dur_str}, channel={channel!r}, url={url}"
        )
    return "\n".join(lines)


def select_videos_with_ai(
    keyword: str,
    candidates: List[Dict[str, Any]],
    max_keep: int = 2,
) -> List[Dict[str, Any]]:
    """
    Để LLM quyết định giữ video nào cho 1 keyword.

    candidates: list dict có ít nhất: url, title, duration_seconds, channel.
    Trả về list đã được lọc (giữ nguyên thứ tự gốc).
    """
    if not candidates:
        return []

    client = get_client()

    system_prompt = (
        "You are a video curator that only outputs JSON.\n"
        "For a given search keyword and a list of candidate YouTube videos, "
        "you decide which videos are truly relevant, high quality and suitable "
        "for editing.\n"
        "You must ONLY return a JSON object, no explanation."
    )

    items_text = _build_video_items_text(candidates)

    user_prompt = f"""
Keyword: {keyword}

Below is a list of candidate videos from a YouTube search.
Each line is one video with its index, title, duration (in seconds), channel, and url:

{items_text}

Task:
- Pick at most {max_keep} videos that best match the keyword and are suitable to be used as B-roll/resource footage.
- Prefer videos that are:
  - Clearly about the keyword.
  - Not 'live', 'premiere', 'upcoming', or random compilation spam.
  - Reasonable length (not several hours unless the keyword implies that).
- If none are acceptable, return an empty list.

Return STRICT JSON with this structure, and nothing else:

{{
  "keep_indices": [0, 3, 5]
}}

If you keep nothing, return:

{{ "keep_indices": [] }}
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
            f"AI trả JSON không hợp lệ (select_videos_with_ai): {e}\nNội dung: {raw[:500]}"
        )

    idx_list = data.get("keep_indices", [])
    if not isinstance(idx_list, list):
        idx_list = []

    # Lọc & dedupe index hợp lệ
    seen = set()
    final_indices: List[int] = []
    for v in idx_list:
        try:
            i = int(v)
        except Exception:
            continue
        if 0 <= i < len(candidates) and i not in seen:
            seen.add(i)
            final_indices.append(i)

    final_candidates = [candidates[i] for i in final_indices]
    return final_candidates

def select_images_with_ai(keyword: str, candidates: List[Dict[str, Any]], max_keep: int = 5) -> List[Dict[str, Any]]:
    # giống select_videos_with_ai nhưng prompt nói về image