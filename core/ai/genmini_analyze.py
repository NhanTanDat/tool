from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ======================================================
# Imports
# ======================================================
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None

# ======================================================
# Logging
# ======================================================
LOG = logging.getLogger("genmini")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    # Tắt log rác từ các thư viện khác
    for name in ("httpx", "httpcore", "urllib3", "google", "grpc", "numba", "absl"):
        try:
            logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass


def _ensure_logging_ready() -> None:
    if not logging.getLogger().handlers:
        _setup_logging(os.environ.get("GENMINI_LOG", "INFO"))


# ======================================================
# CONFIG & ENV
# ======================================================
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"


def _load_env_from_dotenv(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        LOG.warning("cannot read .env: %s", e)


_load_env_from_dotenv()


def _env_bool(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or default).strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "on",
    )


@dataclass(frozen=True)
class Cfg:
    gemini_api_key: str = (os.environ.get("GEMINI_API_KEY") or "").strip()
    gemini_model: str = (os.environ.get("GENMINI_MODEL") or "gemini-2.0-flash").strip()

    # yt-dlp config
    cookies_file: str = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    player_client: str = (os.environ.get("YTDLP_PLAYER_CLIENT", "android") or "android").strip().lower()

    # Editing rules
    pad_sec: float = float(os.environ.get("GENMINI_PAD_SEC", "0.10"))
    min_seg_dur: float = float(os.environ.get("GENMINI_MIN_SEG_DUR", "2.0"))
    max_seg_dur: float = float(os.environ.get("GENMINI_MAX_SEG_DUR", "10.0"))  # mặc định 10s cho đúng prompt

    # Dedupe thresholds
    dedupe_iou_thr: float = float(os.environ.get("GENMINI_DEDUPE_IOU_THR", "0.55"))
    dedupe_text_sim_thr: float = float(os.environ.get("GENMINI_DEDUPE_TEXT_SIM_THR", "0.78"))
    cross_video_dedupe: bool = _env_bool("GENMINI_CROSS_VIDEO_DEDUPE", "1")
    cross_video_text_sim_thr: float = float(os.environ.get("GENMINI_CROSS_VIDEO_TEXT_SIM_THR", "0.80"))

    verbose: bool = _env_bool("GENMINI_VERBOSE", "1")


CFG = Cfg()


def _vinfo(msg: str, *args: Any) -> None:
    if CFG.verbose:
        LOG.info(msg, *args)


def _ensure_gemini_setup() -> None:
    if genai is None:
        raise RuntimeError("Missing dependency: google-generativeai. Install: pip install google-generativeai")
    if not CFG.gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY.")
    genai.configure(api_key=CFG.gemini_api_key)


# ======================================================
# Utils
# ======================================================
def read_dl_links(dl_links_path: str) -> Dict[str, List[str]]:
    path = Path(dl_links_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing: {dl_links_path}")
    groups: Dict[str, List[str]] = {}
    current: Optional[str] = None
    idx = 1
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            current = None
            continue
        if line.startswith("http"):
            if current is None:
                current = f"Group_{idx}"
                idx += 1
            groups.setdefault(current, []).append(line)
        elif not line.startswith("#"):
            current = line
    return groups


def _run_cmd(cmd: List[str], timeout_sec: Optional[int] = None) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout_sec,
        )
        return p.returncode, p.stdout or ""
    except Exception as e:
        return 1, str(e)


def _clean_json_text(text: str) -> str:
    """Làm sạch JSON triệt để (xóa markdown, comment, dấu phẩy thừa)."""
    text = (text or "").strip()

    # Trích JSON object/array "lớn nhất" gần đúng
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    # Xóa comment kiểu //
    text = re.sub(r"//.*", "", text)
    # Xóa dấu phẩy thừa trước ] hoặc }
    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text.strip()


def unidecode(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _bin_slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", unidecode(s)).upper()


# ======================================================
# DEDUPE HELPERS
# ======================================================
def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    # giữ chữ VN + số
    s = re.sub(r"[^a-z0-9\u00C0-\u1EF9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _jaccard_tokens(a: str, b: str) -> float:
    ta = set(_norm_text(a).split())
    tb = set(_norm_text(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    uni = len(ta | tb)
    return inter / max(1, uni)


def _overlap_ratio(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    if inter <= 0:
        return 0.0
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / max(1e-6, union)


def _dedupe_segments(
    segs: List[Dict[str, Any]],
    *,
    iou_thr: float,
    text_sim_thr: float,
    max_keep: int,
) -> List[Dict[str, Any]]:
    """Dedupe theo: dedupe_group (nếu có) + NMS overlap + text similarity."""
    def score(s: Dict[str, Any]) -> float:
        q = float(s.get("quality_score", 6) or 6)
        u = float(s.get("uniqueness_score", 6) or 6)
        return q * 0.75 + u * 0.25

    cleaned = []
    for s in segs or []:
        try:
            st = float(s.get("start_sec", 0))
            en = float(s.get("end_sec", 0))
            if en > st:
                cleaned.append(s)
        except Exception:
            continue

    cleaned.sort(key=score, reverse=True)

    # 1) Best per dedupe_group (nếu AI trả)
    best_by_group: Dict[int, Dict[str, Any]] = {}
    nongroup: List[Dict[str, Any]] = []
    for s in cleaned:
        g = s.get("dedupe_group", None)
        if isinstance(g, int):
            if g not in best_by_group or score(s) > score(best_by_group[g]):
                best_by_group[g] = s
        else:
            nongroup.append(s)

    candidates = list(best_by_group.values()) + nongroup
    candidates.sort(key=score, reverse=True)

    # 2) NMS overlap + dedupe theo notes/action_tag
    final: List[Dict[str, Any]] = []
    for s in candidates:
        s0, e0 = float(s["start_sec"]), float(s["end_sec"])
        notes0 = s.get("script_notes", "") or s.get("action_tag", "") or ""
        ok = True
        for t in final:
            s1, e1 = float(t["start_sec"]), float(t["end_sec"])
            if _overlap_ratio(s0, e0, s1, e1) >= iou_thr:
                ok = False
                break
            notes1 = t.get("script_notes", "") or t.get("action_tag", "") or ""
            if _jaccard_tokens(notes0, notes1) >= text_sim_thr:
                ok = False
                break
        if ok:
            final.append(s)
        if len(final) >= max_keep:
            break

    # 3) talking-head: chỉ giữ 1 clip tốt nhất
    talking = [x for x in final if str(x.get("shot_type", "")).upper() == "TALKING_HEAD"]
    if len(talking) > 1:
        talking.sort(key=score, reverse=True)
        best = talking[0]
        final = [x for x in final if str(x.get("shot_type", "")).upper() != "TALKING_HEAD"]
        final.insert(0, best)
        final = final[:max_keep]

    final.sort(key=lambda x: float(x["start_sec"]))
    return final


# ======================================================
# VIDEO PROCESSING
# ======================================================
def _download_proxy_video(video_url: str, out_dir: Path) -> Optional[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    proxy_path = out_dir / "%(id)s_proxy.%(ext)s"

    # Check cache
    found = (
        list(out_dir.glob("*_proxy.mp4"))
        + list(out_dir.glob("*_proxy.webm"))
        + list(out_dir.glob("*_proxy.mkv"))
    )
    if found:
        if found[0].stat().st_size > 1024:
            return found[0]
        try:
            os.remove(found[0])
        except Exception:
            pass

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "-f",
        "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "-o",
        str(proxy_path),
        "--extractor-args",
        f"youtube:player_client={CFG.player_client}",
        video_url,
    ]
    if CFG.cookies_file and Path(CFG.cookies_file).exists():
        cmd.extend(["--cookies", CFG.cookies_file])

    _vinfo("[DL] Downloading proxy (<=480p) for analysis...")
    code, out = _run_cmd(cmd, timeout_sec=600)
    if code != 0:
        LOG.warning("[DL] yt-dlp failed: %s", (out or "").strip()[:500])

    found = (
        list(out_dir.glob("*_proxy.mp4"))
        + list(out_dir.glob("*_proxy.webm"))
        + list(out_dir.glob("*_proxy.mkv"))
    )
    return found[0] if found else None


def _upload_and_wait_file(file_path: Path):
    _ensure_gemini_setup()
    size_mb = file_path.stat().st_size / 1024 / 1024
    _vinfo("[UPLOAD] Uploading %s (%.2f MB)...", file_path.name, size_mb)

    try:
        video_file = genai.upload_file(path=file_path)

        # Wait with timeout (max 6 minutes)
        t0 = time.time()
        while getattr(video_file, "state", None) and video_file.state.name == "PROCESSING":
            if time.time() - t0 > 360:
                LOG.error("[UPLOAD] Processing timeout.")
                return None
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if getattr(video_file, "state", None) and video_file.state.name == "FAILED":
            LOG.error("[UPLOAD] Failed.")
            return None

        return video_file
    except Exception as e:
        LOG.error("[UPLOAD] Error: %s", e)
        return None


# ======================================================
# GEMINI INTELLIGENT ANALYSIS
# ======================================================
def _gemini_analyze_video_content(video_file, keyword: str, max_segments: int) -> List[Dict[str, Any]]:
    if genai is None:
        return []

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    prompt_smart = f"""
TASK: Act as a senior video editor. Extract the BEST, MOST DISTINCT clips of: "{keyword}".

HARD RULES:
- Return at most {max_segments} clips.
- Clips MUST be NON-OVERLAPPING (no time overlap between any two clips).
- Each clip must be a DIFFERENT MOMENT (different action / expression / camera angle / context).
- If you see near-duplicate moments (same shot/scene), keep ONLY the best one.

QUALITY FILTER (reject):
- blurry / shaky / too dark
- "{keyword}" too small / too far / barely visible
- intro/outro/logo/b-roll unrelated

TALKING HEAD RULE:
- If it's mostly a static interview/talking-head, return ONLY 1 best quote (3–6s), not multiple.

DURATION:
- Prefer 2–10 seconds.

OUTPUT:
JSON only. Provide concise notes. Also provide a dedupe group id for near-duplicates.
""".strip()

    response_schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_sec": {"type": "number"},
                        "end_sec": {"type": "number"},
                        "shot_type": {"type": "string"},
                        "action_tag": {"type": "string"},
                        "script_notes": {"type": "string"},
                        "quality_score": {"type": "number", "description": "1-10 visual quality"},
                        "uniqueness_score": {"type": "number", "description": "1-10 how different from other clips"},
                        "dedupe_group": {"type": "integer", "description": "same number = near-duplicate moment"},
                    },
                    "required": ["start_sec", "end_sec", "script_notes"],
                },
            }
        },
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(model_name=CFG.gemini_model)
            response = model.generate_content(
                [video_file, prompt_smart],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.2,
                ),
                safety_settings=safety_settings,
                request_options={"timeout": 600},
            )

            raw_text = getattr(response, "text", "") or ""
            clean_text = _clean_json_text(raw_text)
            data = json.loads(clean_text)
            segs = data.get("segments") or []

            # Filter cơ bản
            valid: List[Dict[str, Any]] = []
            for s in segs:
                try:
                    st = float(s.get("start_sec", 0))
                    en = float(s.get("end_sec", 0))
                    dur = en - st
                    q = float(s.get("quality_score", 6) or 6)
                    if dur >= CFG.min_seg_dur and q >= 4:
                        valid.append(s)
                except Exception:
                    continue

            # Dedupe để tránh lặp + limit max_segments
            valid = _dedupe_segments(
                valid,
                iou_thr=CFG.dedupe_iou_thr,
                text_sim_thr=CFG.dedupe_text_sim_thr,
                max_keep=max_segments,
            )

            if not valid:
                LOG.warning("[GEMINI] No high-quality distinct clips found after filtering/dedupe.")
            return valid

        except json.JSONDecodeError:
            LOG.error("[GEMINI] JSON Error. Retrying...")
            time.sleep(2)
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                wait = 15 * (attempt + 1)
                LOG.warning("[GEMINI] Rate Limit. Waiting %ss...", wait)
                time.sleep(wait)
            elif "400" in err:
                LOG.error("[GEMINI] Bad Request / Safety Blocked.")
                return []
            else:
                LOG.error("[GEMINI] Error: %s", err)
                time.sleep(5)

    return []


# ======================================================
# Main Logic
# ======================================================
def analyze_video_production_standard(video_url: str, keyword: str, max_segments: int = 8) -> List[Dict[str, Any]]:
    vid_id = re.sub(r"\W+", "_", video_url.split("v=")[-1] if "v=" in video_url else video_url)[-40:]
    cache_dir = ROOT_DIR / "data" / ".cache" / "analysis_videos" / vid_id

    video_path = _download_proxy_video(video_url, cache_dir)
    if not video_path:
        return []

    gemini_file = _upload_and_wait_file(video_path)
    if not gemini_file:
        return []

    _vinfo("[GEMINI] Analyzing VIDEO content for '%s'...", keyword)
    raw_segments = _gemini_analyze_video_content(gemini_file, keyword, max_segments)

    try:
        genai.delete_file(gemini_file.name)
    except Exception:
        pass

    final_segments: List[Dict[str, Any]] = []
    for item in raw_segments:
        try:
            s = float(item.get("start_sec", 0))
            e = float(item.get("end_sec", 0))

            # pad để cắt “đẹp”
            s = max(0.0, s - CFG.pad_sec)
            e = e + CFG.pad_sec

            dur = e - s
            if dur < CFG.min_seg_dur:
                continue
            if dur > CFG.max_seg_dur:
                e = s + CFG.max_seg_dur

            q = float(item.get("quality_score", 8) or 8)
            conf = max(0.1, min(1.0, q / 10.0))

            final_segments.append(
                {
                    "start_sec": s,
                    "end_sec": e,
                    "confidence": conf,
                    "type": item.get("shot_type", item.get("type", "CONTENT")),
                    "reason": f"[VISUAL] {item.get('script_notes', '')}".strip(),
                }
            )
        except Exception:
            continue

    final_segments.sort(key=lambda x: float(x["start_sec"]))
    return final_segments


def run_genmini_project(dl_links_path: str, segments_path: str, max_segments: int = 8):
    _ensure_logging_ready()
    groups = read_dl_links(dl_links_path)

    all_results: List[Dict[str, Any]] = []
    video_map: List[Dict[str, Any]] = []
    global_idx = 0

    # Dedupe xuyên nhiều video cùng keyword
    seen_by_kw: Dict[str, List[str]] = {}

    for keyword, urls in groups.items():
        kw_clean = keyword.replace("Group_", "").replace("_", " ").strip()
        LOG.info("Processing: %s (%d videos)", kw_clean, len(urls))

        for idx, url in enumerate(urls):
            try:
                segs = analyze_video_production_standard(url, kw_clean, max_segments)

                # Cross-video dedupe (tránh farm giống nhau)
                if CFG.cross_video_dedupe and segs:
                    kept = []
                    for s in segs:
                        sig = _norm_text((s.get("reason", "") or "") + " " + (s.get("type", "") or ""))
                        dup = False
                        for old in seen_by_kw.get(kw_clean, []):
                            if _jaccard_tokens(sig, old) >= CFG.cross_video_text_sim_thr:
                                dup = True
                                break
                        if not dup:
                            kept.append(s)
                            seen_by_kw.setdefault(kw_clean, []).append(sig)
                    segs = kept

                video_map.append(
                    {
                        "video_global_index": global_idx,
                        "keyword": kw_clean,
                        "video_url": url,
                        "video_index_in_keyword": idx,
                        "found_clips": len(segs),
                    }
                )

                if segs:
                    all_results.append(
                        {
                            "keyword": kw_clean,
                            "video_url": url,
                            "video_global_index": global_idx,
                            "video_index": idx,
                            "segments": segs,
                        }
                    )
                    _vinfo(" -> Found %d valid clips.", len(segs))
                else:
                    _vinfo(" -> No valid clips found.")

            except Exception as e:
                LOG.error("Error %s: %s", url, e)

            global_idx += 1

    Path(segments_path).write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    Path(segments_path).with_name("video_map.json").write_text(
        json.dumps(video_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return all_results


def build_production_timeline(segments_json: str, output_csv: str):
    data = json.loads(Path(segments_json).read_text(encoding="utf-8"))
    csv_lines = ["scene_index,character,bin_name,video_index,src_start,src_end,duration,type,notes"]
    scene_idx = 0
    for entry in data:
        kw = entry["keyword"]
        for item in entry["segments"]:
            dur = float(item["end_sec"]) - float(item["start_sec"])
            notes = (item.get("reason", "") or "").replace(",", ";")
            csv_lines.append(
                f"{scene_idx},{kw},{_bin_slug(kw)},{entry['video_global_index']},"
                f"{float(item['start_sec']):.3f},{float(item['end_sec']):.3f},{dur:.3f},"
                f"{item.get('type','CLIP')},{notes}"
            )
            scene_idx += 1
    Path(output_csv).write_text("\n".join(csv_lines), encoding="utf-8")


def run_genmini_for_project(dl_links_path, segments_json_path, **kwargs):
    return len(run_genmini_project(dl_links_path, segments_json_path, kwargs.get("max_segments_per_video", 8)))


def build_timeline_csv_from_segments(segments_json_path, timeline_csv_path, **kwargs):
    build_production_timeline(segments_json_path, timeline_csv_path)
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dl_links", default=str(ROOT_DIR / "data" / "dl_links.txt"))
    parser.add_argument("--segments", default=str(ROOT_DIR / "data" / "segments_genmini.json"))
    parser.add_argument("--timeline", default=str(ROOT_DIR / "data" / "timeline_export_merged.csv"))
    parser.add_argument("--max_clips", type=int, default=8)
    args = parser.parse_args()

    _ensure_logging_ready()
    run_genmini_project(args.dl_links, args.segments, args.max_clips)
    build_production_timeline(args.segments, args.timeline)
