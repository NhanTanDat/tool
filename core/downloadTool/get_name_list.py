
# filepath: p:\coddd\autotool\core\download Tool\get_name_list.py
'''This module is to get name list from premier pro project file (.prproj) to txt file
   (improved: also extract start/end time for each text if possible)
'''
import gzip
import os
import xml.etree.ElementTree as ET

import re

def _sanitize_keyword(name: str) -> str:
    """Remove special characters from keyword before adding to list."""
    if not isinstance(name, str):
        name = str(name)
    # remove control characters
    name = ''.join(ch for ch in name if ord(ch) >= 32)
    # remove straight + curly quotes
    name = re.sub(r'[\"\'“”‘’]', '', name)
    # collapse whitespace and trim
    name = ' '.join(name.split()).strip()
    return name

def _read_prproj_xml(path: str) -> ET.Element:
    with gzip.open(path, "rb") as f:
        xml_data = f.read().decode("utf-8", errors="replace")
    return ET.fromstring(xml_data)

def _build_parent_map(root: ET.Element):
    return {child: parent for parent in root.iter() for child in parent}

def _get_timebase(root: ET.Element) -> int:
    # Premiere thường có Sequence/Rate/Timebase
    seq = root.find(".//Sequence")
    if seq is not None:
        tb = seq.find(".//Rate/Timebase")
        if tb is not None and tb.text and tb.text.isdigit():
            return int(tb.text)
    # fallback
    return 25

def _text_or_none(elem: ET.Element, tag_name: str):
    if elem is None:
        return None
    t = elem.find(tag_name)
    if t is not None and t.text and t.text.strip().isdigit():
        return int(t.text.strip())
    return None

def _extract_start_end(clip_item: ET.Element):
    # Ưu tiên Start / End; nếu thiếu dùng InPoint / OutPoint
    start = _text_or_none(clip_item, "Start")
    end = _text_or_none(clip_item, "End")
    if start is not None and end is not None:
        return start, end
    in_p = _text_or_none(clip_item, "InPoint")
    out_p = _text_or_none(clip_item, "OutPoint")
    if in_p is not None and out_p is not None:
        return in_p, out_p
    return None, None

def extract_text_instances_with_timing(path: str, save_txt: str = "list_names.txt"):
    """
    Trả về danh sách dict:
      {
        name: str,
        start_frame: int | None,
        end_frame: int | None,
        start_seconds: float | None,
        end_seconds: float | None
      }

    Ghi file nếu save_txt != None (mỗi dòng: name|start_frame|end_frame|start_seconds|end_seconds)
    """
    root = _read_prproj_xml(path)
    parent_map = _build_parent_map(root)
    timebase = _get_timebase(root)

    results = []
    for comp in root.findall(".//VideoFilterComponent"):
        inst = comp.find("Component/InstanceName")
        if inst is None or not inst.text:
            continue
        name = inst.text.strip()
        name = _sanitize_keyword(name)
        if not name:
            continue
        # Lần lên ClipItem gần nhất
        current = comp
        clip_item = None
        while current in parent_map:
            current = parent_map[current]
            if current.tag == "ClipItem":
                clip_item = current
                break
        if clip_item is not None:
            start, end = _extract_start_end(clip_item)
        else:
            start = end = None

        if start is not None and end is not None and end < start:
            # Trường hợp dữ liệu bất thường
            end = None

        if start is not None and end is not None:
            start_sec = round(start / timebase, 4)
            end_sec = round(end / timebase, 4)
        else:
            start_sec = end_sec = None

        results.append({
            "name": name,
            "start_frame": start,
            "end_frame": end,
            "start_seconds": start_sec,
            "end_seconds": end_sec
        })

    if save_txt:
        with open(save_txt, "w", encoding="utf-8") as f:
            f.write("")
            for r in results:
                f.write(
                    f"{r['name']}|{r['start_frame']}|{r['end_frame']}|{r['start_seconds']}|{r['end_seconds']}\n"
                )
    return results

# Giữ hàm cũ (backward compatibility)
def extract_instance_names(path, save_txt=None, project_name=None):
    '''Extract instance names from .prproj file to a list of names.
    Input: .prproj file path, optional save_txt to save names to txt file
    Output: List of instance names
    '''
    data = extract_text_instances_with_timing(path, save_txt=None)
    names = [d["name"] for d in data]
    if save_txt:
        with open(save_txt, "w", encoding="utf-8") as f:
            for n in names:
                #nếu n không bắt đầu bằng 1 kí tự đơn lẻ + " " thì ghi vào file vis dụ: "A bcd" thì bỏ
                if (len(n) >= 2 and n[0].isalpha() and n[1] == " "):
                    continue
                else:
                    f.write(n + "\n")
    return names
