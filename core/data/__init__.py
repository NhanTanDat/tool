"""
core.data - Data models and serialization

Provides:
- Type-safe data classes for JSON files
- Serialization/deserialization with validation
- Schema definitions
"""

from .models import (
    Keyword,
    Marker,
    VideoSegment,
    CutClip,
    CutEntry,
    Track3Keywords,
    CutList,
    SceneMatch,
)

from .serializers import (
    load_json,
    save_json,
    load_track3_keywords,
    save_track3_keywords,
    load_cut_list,
    save_cut_list,
    load_markers,
    save_markers,
)

__all__ = [
    # Models
    "Keyword",
    "Marker",
    "VideoSegment",
    "CutClip",
    "CutEntry",
    "Track3Keywords",
    "CutList",
    "SceneMatch",
    # Serializers
    "load_json",
    "save_json",
    "load_track3_keywords",
    "save_track3_keywords",
    "load_cut_list",
    "save_cut_list",
    "load_markers",
    "save_markers",
]
