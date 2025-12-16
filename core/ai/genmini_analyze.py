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

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None

LOG = logging.getLogger("genmini")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    for name in ("httpx", "httpcore", "urllib3", "google", "grpc", "numba", "absl"):
        try:
            logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass


def _ensure_logging_ready() -> None:
    if not logging.getLogger().handlers:
        _setup_logging(os.environ.get("GENMINI_LOG", "INFO"))


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


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name, str(default)) or str(default)).strip())
    except Exception:
        return default


def _safe_float_env(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name, str(default)) or str(default)).strip())
    except Exception:
        return default


_RE_LEADING_INDEX = re.compile(r"^\s*(\d+)[\.\)\-:_\s]+(.+?)\s*$")


def _clean_keyword_line(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    m = _RE_LEADING_INDEX.match(s)
    if m:
        return (m.group(2) or "").strip()
    return s


@dataclass(frozen=True)
class Cfg:
    gemini_api_key: str = (os.environ.get("GEMINI_API_KEY") or "").strip()
    gemini_model: str = (os.environ.get("GENMINI_MODEL") or "gemini-2.0-flash").strip()

    cookies_file: str = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    player_client: str = (os.environ.get("YTDLP_PLAYER_CLIENT", "android") or "android").strip().lower()

    pad_sec: float = _safe_float_env("GENMINI_PAD_SEC", 0.10)
    min_seg_dur: float = _safe_float_env("GENMINI_MIN_SEG_DUR", 1.0)
    max_seg_dur: float = _safe_float_env("GENMINI_MAX_SEG_DUR", 12.0)

    strict_quality_min: float = _safe_float_env("GENMINI_STRICT_QUALITY_MIN", 2.0)
    lenient_quality_min: float = _safe_float_env("GENMINI_LENIENT_QUALITY_MIN", 1.0)

    dedupe_iou_thr: float = _safe_float_env("GENMINI_DEDUPE_IOU_THR", 0.90)
    dedupe_text_sim_thr: float = _safe_float_env("GENMINI_DEDUPE_TEXT_SIM_THR", 0.92)

    cross_video_dedupe: bool = _env_bool("GENMINI_CROSS_VIDEO_DEDUPE", "1")
    cross_video_text_sim_thr: float = _safe_float_env("GENMINI_CROSS_VIDEO_TEXT_SIM_THR", 0.92)

    retry_lenient: bool = _env_bool("GENMINI_RETRY_LENIENT", "1")
    # nếu strict < min_keep_per_video => sẽ chạy lenient để bù
    min_keep_per_video: int = _safe_int_env("GENMINI_MIN_KEEP_PER_VIDEO", 1)
    keep_first_if_empty: bool = _env_bool("GENMINI_KEEP_FIRST_IF_EMPTY", "1")
    lenient_disable_dedupe: bool = _env_bool("GENMINI_LENIENT_DISABLE_DEDUPE", "1")

    timeline_round_robin: bool = _env_bool("GENMINI_TIMELINE_ROUND_ROBIN", "1")
    timeline_per_video_limit: int = _safe_int_env("GENMINI_TIMELINE_PER_VIDEO_LIMIT", 0)
    timeline_max_scenes_per_keyword: int = _safe_int_env("GENMINI_TIMELINE_MAX_SCENES_PER_KEYWORD", 0)
    timeline_sort_by_score: bool = _env_bool("GENMINI_TIMELINE_SORT_BY_SCORE", "1")

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
            current = _clean_keyword_line(line)
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
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL) or re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        text = m.group(0)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text.strip()


def unidecode(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _bin_slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", unidecode(s)).upper()


def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\u00C0-\u1EF9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _jaccard_tokens(a: str, b: str) -> float:
    ta = set(_norm_text(a).split())
    tb = set(_norm_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


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

    final.sort(key=lambda x: float(x["start_sec"]))
    return final


def _download_proxy_video(video_url: str, out_dir: Path) -> Optional[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    proxy_path = out_dir / "%(id)s_proxy.%(ext)s"

    found = list(out_dir.glob("*_proxy.mp4")) + list(out_dir.glob("*_proxy.webm")) + list(out_dir.glob("*_proxy.mkv"))
    if found and found[0].stat().st_size > 1024:
        return found[0]

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

    found = list(out_dir.glob("*_proxy.mp4")) + list(out_dir.glob("*_proxy.webm")) + list(out_dir.glob("*_proxy.mkv"))
    return found[0] if found else None


def _upload_and_wait_file(file_path: Path):
    _ensure_gemini_setup()
    size_mb = file_path.stat().st_size / 1024 / 1024
    _vinfo("[UPLOAD] Uploading %s (%.2f MB)...", file_path.name, size_mb)

    try:
        video_file = genai.upload_file(path=file_path)

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


def _gemini_analyze_video_content(video_file, keyword: str, max_segments: int, *, strict: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    return: (filtered_segments, raw_segments)
    """
    if genai is None:
        return [], []

    keyword = _clean_keyword_line(keyword)
    if not keyword:
        return [], []

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    if strict:
        quality_min = CFG.strict_quality_min
        temperature = 0.2
        prompt = f"""
TASK: Act as a senior video editor. Extract the BEST, MOST DISTINCT clips of: "{keyword}".

HARD RULES:
- Return at most {max_segments} clips.
- Clips MUST be NON-OVERLAPPING.
- Each clip should be a DIFFERENT moment (action/angle/context).

DURATION:
- Prefer 1–12 seconds.

OUTPUT:
JSON only. Provide concise notes. Provide dedupe_group for near-duplicates.
""".strip()
    else:
        quality_min = CFG.lenient_quality_min
        temperature = 0.35
        prompt = f"""
TASK: Find clips that MOST LIKELY contain: "{keyword}" (LENIENT PASS).

RULES:
- Return at most {max_segments} clips.
- Clips MUST be NON-OVERLAPPING.
- If uncertain, still pick best-guess moments related to "{keyword}".

DURATION:
- Prefer 1–12 seconds.

OUTPUT:
JSON only. Provide concise notes. Provide dedupe_group for near-duplicates.
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
                        "quality_score": {"type": "number"},
                        "uniqueness_score": {"type": "number"},
                        "dedupe_group": {"type": "integer"},
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
                [video_file, prompt],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=temperature,
                ),
                safety_settings=safety_settings,
                request_options={"timeout": 600},
            )

            raw_text = getattr(response, "text", "") or ""
            data = json.loads(_clean_json_text(raw_text))
            raw_segs = data.get("segments") or []

            filtered: List[Dict[str, Any]] = []
            for s in raw_segs:
                try:
                    st = float(s.get("start_sec", 0))
                    en = float(s.get("end_sec", 0))
                    if en <= st:
                        continue
                    dur = en - st
                    q = float(s.get("quality_score", 6) or 6)
                    if dur >= CFG.min_seg_dur and q >= quality_min:
                        filtered.append(s)
                except Exception:
                    continue

            # strict -> dedupe, lenient -> (tuỳ) bỏ dedupe để khỏi "lọc gắt"
            if strict or (not CFG.lenient_disable_dedupe):
                filtered = _dedupe_segments(
                    filtered,
                    iou_thr=CFG.dedupe_iou_thr,
                    text_sim_thr=CFG.dedupe_text_sim_thr,
                    max_keep=max_segments,
                )
            else:
                # vẫn giới hạn số lượng
                filtered = filtered[:max_segments]

            if not filtered:
                LOG.warning("[GEMINI] No valid clips after filter (%s pass).", "STRICT" if strict else "LENIENT")
            return filtered, raw_segs

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
                return [], []
            else:
                LOG.error("[GEMINI] Error: %s", err)
                time.sleep(5)

    return [], []


def analyze_video_production_standard(video_url: str, keyword: str, max_segments: int = 8) -> List[Dict[str, Any]]:
    keyword = _clean_keyword_line(keyword)
    vid_id = re.sub(r"\W+", "_", video_url.split("v=")[-1] if "v=" in video_url else video_url)[-40:]
    cache_dir = ROOT_DIR / "data" / ".cache" / "analysis_videos" / vid_id

    video_path = _download_proxy_video(video_url, cache_dir)
    if not video_path:
        return []

    gemini_file = _upload_and_wait_file(video_path)
    if not gemini_file:
        return []

    _vinfo("[GEMINI] Analyzing VIDEO content for '%s'...", keyword)

    strict_segs, strict_raw = _gemini_analyze_video_content(gemini_file, keyword, max_segments, strict=True)
    use_segs = strict_segs
    use_raw = strict_raw

    if CFG.retry_lenient and len(use_segs) < max(0, CFG.min_keep_per_video):
        _vinfo("[GEMINI] Strict too few (%d). Retrying LENIENT...", len(use_segs))
        lenient_segs, lenient_raw = _gemini_analyze_video_content(gemini_file, keyword, max(3, min(max_segments, 6)), strict=False)
        if len(lenient_segs) > len(use_segs):
            use_segs = lenient_segs
            use_raw = lenient_raw

    try:
        genai.delete_file(gemini_file.name)
    except Exception:
        pass

    final_segments: List[Dict[str, Any]] = []

    def push_from_item(item: Dict[str, Any]) -> None:
        nonlocal final_segments
        s = float(item.get("start_sec", 0))
        e = float(item.get("end_sec", 0))

        s = max(0.0, s - CFG.pad_sec)
        e = e + CFG.pad_sec

        if e <= s:
            return

        dur = e - s
        if dur < CFG.min_seg_dur:
            # ép tối thiểu cho đỡ bị rớt
            e = s + CFG.min_seg_dur
        if (e - s) > CFG.max_seg_dur:
            e = s + CFG.max_seg_dur

        q = float(item.get("quality_score", 6) or 6)
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

    # normal: từ use_segs (đã lọc)
    for it in use_segs:
        try:
            push_from_item(it)
        except Exception:
            continue

    # fallback mạnh: nếu vẫn rỗng nhưng AI có trả raw -> lấy 1 cái đầu
    if (not final_segments) and CFG.keep_first_if_empty and use_raw:
        for it in use_raw:
            try:
                st = float(it.get("start_sec", 0))
                en = float(it.get("end_sec", 0))
                if en > st:
                    push_from_item(it)
                    break
            except Exception:
                continue

    final_segments.sort(key=lambda x: float(x["start_sec"]))
    return final_segments


def _seg_score(seg: Dict[str, Any]) -> float:
    try:
        conf = float(seg.get("confidence", 0.0) or 0.0)
    except Exception:
        conf = 0.0
    try:
        dur = float(seg.get("end_sec", 0.0)) - float(seg.get("start_sec", 0.0))
    except Exception:
        dur = 0.0
    return conf * 1000.0 + dur


def run_genmini_project(dl_links_path: str, segments_path: str, max_segments: int = 8):
    _ensure_logging_ready()
    groups = read_dl_links(dl_links_path)

    all_results: List[Dict[str, Any]] = []
    video_map: List[Dict[str, Any]] = []
    global_idx = 0

    seen_by_kw: Dict[str, List[str]] = {}

    for keyword, urls in groups.items():
        kw_clean = _clean_keyword_line(keyword.replace("Group_", "").replace("_", " ").strip())
        LOG.info("Processing: %s (%d videos)", kw_clean, len(urls))

        for idx, url in enumerate(urls):
            try:
                segs = analyze_video_production_standard(url, kw_clean, max_segments)
                original = list(segs)

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

                if (not segs) and original:
                    segs = original[:1]

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

    Path(segments_path).write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(segments_path).with_name("video_map.json").write_text(json.dumps(video_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return all_results


def build_production_timeline(segments_json: str, output_csv: str) -> int:
    data = json.loads(Path(segments_json).read_text(encoding="utf-8"))

    round_robin = CFG.timeline_round_robin
    per_video_limit = CFG.timeline_per_video_limit
    max_scenes_per_keyword = CFG.timeline_max_scenes_per_keyword
    sort_by_score = CFG.timeline_sort_by_score

    csv_lines = ["scene_index,character,bin_name,video_index,src_start,src_end,duration,type,notes"]
    scene_idx = 0

    by_kw: Dict[str, List[Dict[str, Any]]] = {}
    kw_order: List[str] = []
    for entry in data:
        kw = _clean_keyword_line(entry.get("keyword") or "UNKNOWN")
        if kw not in by_kw:
            by_kw[kw] = []
            kw_order.append(kw)
        by_kw[kw].append(entry)

    for kw in kw_order:
        entries = by_kw.get(kw, [])
        if not entries:
            continue

        videos: List[Dict[str, Any]] = []
        for e in entries:
            segs = e.get("segments") or []
            if sort_by_score:
                segs = sorted(segs, key=_seg_score, reverse=True)
            videos.append(
                {"video_global_index": int(e.get("video_global_index", 0)), "segments": segs}
            )

        total_used_kw = 0
        if not round_robin:
            for v in videos:
                used = 0
                for item in v["segments"]:
                    if per_video_limit > 0 and used >= per_video_limit:
                        break
                    if max_scenes_per_keyword > 0 and total_used_kw >= max_scenes_per_keyword:
                        break
                    dur = float(item["end_sec"]) - float(item["start_sec"])
                    notes = (item.get("reason", "") or "").replace(",", ";")
                    csv_lines.append(
                        f"{scene_idx},{kw},{_bin_slug(kw)},{v['video_global_index']},"
                        f"{float(item['start_sec']):.3f},{float(item['end_sec']):.3f},{dur:.3f},"
                        f"{item.get('type','CLIP')},{notes}"
                    )
                    scene_idx += 1
                    used += 1
                    total_used_kw += 1
            continue

        ptrs = [0] * len(videos)
        used_per_video = [0] * len(videos)

        while True:
            progressed = False
            for i, v in enumerate(videos):
                if per_video_limit > 0 and used_per_video[i] >= per_video_limit:
                    continue
                if max_scenes_per_keyword > 0 and total_used_kw >= max_scenes_per_keyword:
                    break

                segs = v["segments"]
                if ptrs[i] >= len(segs):
                    continue

                item = segs[ptrs[i]]
                ptrs[i] += 1
                used_per_video[i] += 1
                total_used_kw += 1

                dur = float(item["end_sec"]) - float(item["start_sec"])
                notes = (item.get("reason", "") or "").replace(",", ";")
                csv_lines.append(
                    f"{scene_idx},{kw},{_bin_slug(kw)},{v['video_global_index']},"
                    f"{float(item['start_sec']):.3f},{float(item['end_sec']):.3f},{dur:.3f},"
                    f"{item.get('type','CLIP')},{notes}"
                )
                scene_idx += 1
                progressed = True

            if not progressed:
                break
            if max_scenes_per_keyword > 0 and total_used_kw >= max_scenes_per_keyword:
                break

    Path(output_csv).write_text("\n".join(csv_lines), encoding="utf-8")
    return scene_idx


def run_genmini_for_project(dl_links_path, segments_json_path, **kwargs):
    return len(run_genmini_project(dl_links_path, segments_json_path, kwargs.get("max_segments_per_video", 8)))


def build_timeline_csv_from_segments(segments_json_path, timeline_csv_path, **kwargs):
    return build_production_timeline(segments_json_path, timeline_csv_path)


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
