"""
core.data.serializers - JSON serialization with validation

Provides type-safe loading and saving of JSON files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Type, Union

from .models import (
    Keyword,
    Marker,
    Track3Keywords,
    CutList,
    CutEntry,
    VideoSegment,
)

import sys
_THIS_DIR = Path(__file__).parent.resolve()
_CORE_DIR = _THIS_DIR.parent
_ROOT_DIR = _CORE_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from core.utils.exceptions import ValidationError, FileOperationError


T = TypeVar("T")


def load_json(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load JSON file with proper encoding handling.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data as dict

    Raises:
        FileOperationError: If file not found or read error
        ValidationError: If JSON parsing fails
    """
    path = Path(path)

    if not path.exists():
        raise FileOperationError(
            f"File not found: {path}",
            file_path=str(path),
            operation="read"
        )

    # Try different encodings
    encodings = ["utf-8-sig", "utf-8", "latin-1"]

    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Invalid JSON format in {path.name}",
                details=str(e)
            )

    raise FileOperationError(
        f"Cannot read file with any encoding: {path}",
        file_path=str(path),
        operation="read"
    )


def save_json(
    path: Union[str, Path],
    data: Dict[str, Any],
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """
    Save data to JSON file.

    Args:
        path: Output path
        data: Data to save
        indent: JSON indentation
        ensure_ascii: If True, escape non-ASCII characters

    Returns:
        True if successful

    Raises:
        FileOperationError: If write fails
    """
    path = Path(path)

    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

        return True

    except Exception as e:
        raise FileOperationError(
            f"Cannot write to {path}",
            file_path=str(path),
            operation="write",
            details=str(e)
        )


# ==================== Track3 Keywords ====================

def load_track3_keywords(path: Union[str, Path]) -> Track3Keywords:
    """
    Load track3_keywords.json file.

    Args:
        path: Path to JSON file

    Returns:
        Track3Keywords object

    Raises:
        FileOperationError: If file not found
        ValidationError: If format invalid
    """
    data = load_json(path)

    if "keywords" not in data:
        raise ValidationError(
            f"Invalid track3_keywords.json: missing 'keywords' field",
            details=f"Keys found: {list(data.keys())}"
        )

    return Track3Keywords.from_dict(data)


def save_track3_keywords(path: Union[str, Path], keywords: Track3Keywords) -> bool:
    """
    Save Track3Keywords to JSON file.

    Args:
        path: Output path
        keywords: Track3Keywords object

    Returns:
        True if successful
    """
    return save_json(path, keywords.to_dict())


# ==================== Cut List ====================

def load_cut_list(path: Union[str, Path]) -> CutList:
    """
    Load cut_list.json file.

    Args:
        path: Path to JSON file

    Returns:
        CutList object

    Raises:
        FileOperationError: If file not found
        ValidationError: If format invalid
    """
    data = load_json(path)

    if "cuts" not in data:
        raise ValidationError(
            f"Invalid cut_list.json: missing 'cuts' field",
            details=f"Keys found: {list(data.keys())}"
        )

    return CutList.from_dict(data)


def save_cut_list(path: Union[str, Path], cut_list: CutList) -> bool:
    """
    Save CutList to JSON file.

    Args:
        path: Output path
        cut_list: CutList object

    Returns:
        True if successful
    """
    return save_json(path, cut_list.to_dict())


# ==================== Markers ====================

def load_markers(path: Union[str, Path]) -> List[Marker]:
    """
    Load markers.json file.

    Args:
        path: Path to JSON file

    Returns:
        List of Marker objects

    Raises:
        FileOperationError: If file not found
        ValidationError: If format invalid
    """
    data = load_json(path)

    # Support both formats:
    # 1. {"markers": [...]}
    # 2. [...]
    if isinstance(data, list):
        markers_data = data
    elif "markers" in data:
        markers_data = data["markers"]
    else:
        raise ValidationError(
            f"Invalid markers.json format",
            details=f"Expected list or dict with 'markers' key"
        )

    return [Marker.from_dict(m) for m in markers_data]


def save_markers(path: Union[str, Path], markers: List[Marker]) -> bool:
    """
    Save markers to JSON file.

    Args:
        path: Output path
        markers: List of Marker objects

    Returns:
        True if successful
    """
    data = {
        "count": len(markers),
        "markers": [m.to_dict() for m in markers],
    }
    return save_json(path, data)


# ==================== Generic loader ====================

def load_keywords_list(path: Union[str, Path]) -> List[Keyword]:
    """
    Load keywords from track3_keywords.json as a simple list.

    Args:
        path: Path to JSON file

    Returns:
        List of Keyword objects
    """
    track3 = load_track3_keywords(path)
    return track3.keywords


def load_cut_entries(path: Union[str, Path]) -> List[CutEntry]:
    """
    Load cut entries from cut_list.json as a simple list.

    Args:
        path: Path to JSON file

    Returns:
        List of CutEntry objects
    """
    cut_list = load_cut_list(path)
    return cut_list.cuts
