"""
core.data.models - Type-safe data classes

Defines data structures for:
- track3_keywords.json
- cut_list.json
- markers.json
- scene_matches.json
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Keyword:
    """A single keyword/marker from Track 3."""

    keyword: str
    index: int = 0
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    duration_seconds: float = 0.0
    start_timecode: str = ""
    end_timecode: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "index": self.index,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "start_timecode": self.start_timecode,
            "end_timecode": self.end_timecode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Keyword":
        return cls(
            keyword=data.get("keyword", ""),
            index=data.get("index", 0),
            start_seconds=data.get("start_seconds", 0.0),
            end_seconds=data.get("end_seconds", 0.0),
            duration_seconds=data.get("duration_seconds", 0.0),
            start_timecode=data.get("start_timecode", ""),
            end_timecode=data.get("end_timecode", ""),
        )


@dataclass
class Marker:
    """A sequence marker (from readMarkers.jsx)."""

    name: str
    index: int = 0
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    duration_seconds: float = 0.0
    color: str = ""
    comments: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "index": self.index,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "color": self.color,
            "comments": self.comments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Marker":
        return cls(
            name=data.get("name", data.get("keyword", "")),
            index=data.get("index", 0),
            start_seconds=data.get("start_seconds", 0.0),
            end_seconds=data.get("end_seconds", 0.0),
            duration_seconds=data.get("duration_seconds", 0.0),
            color=data.get("color", ""),
            comments=data.get("comments", ""),
        )


@dataclass
class VideoSegment:
    """A segment within a video identified by AI analysis."""

    start_time: float
    end_time: float
    description: str = ""
    quality_score: float = 0.0
    video_path: str = ""
    video_name: str = ""

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "description": self.description,
            "quality_score": self.quality_score,
            "video_path": self.video_path,
            "video_name": self.video_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoSegment":
        return cls(
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", 0.0),
            description=data.get("description", ""),
            quality_score=data.get("quality_score", 0.0),
            video_path=data.get("video_path", ""),
            video_name=data.get("video_name", ""),
        )


@dataclass
class CutClip:
    """A single clip to be placed on the timeline."""

    video_path: str
    video_name: str
    clip_start: float  # Source IN point (seconds)
    clip_end: float    # Source OUT point (seconds)
    timeline_pos: float  # Timeline position (seconds)
    duration: float    # Duration on timeline
    source: str = "ai_matched"  # "ai_matched" or "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_path": self.video_path,
            "video_name": self.video_name,
            "clip_start": self.clip_start,
            "clip_end": self.clip_end,
            "timeline_pos": self.timeline_pos,
            "duration": self.duration,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CutClip":
        return cls(
            video_path=data.get("video_path", ""),
            video_name=data.get("video_name", ""),
            clip_start=data.get("clip_start", 0.0),
            clip_end=data.get("clip_end", 0.0),
            timeline_pos=data.get("timeline_pos", 0.0),
            duration=data.get("duration", 0.0),
            source=data.get("source", "ai_matched"),
        )


@dataclass
class CutEntry:
    """A cut entry for a single marker (may contain multiple clips)."""

    index: int
    keyword: str
    timeline_start: float
    timeline_end: float
    timeline_duration: float
    clips: List[CutClip] = field(default_factory=list)
    clip_count: int = 0

    def __post_init__(self):
        self.clip_count = len(self.clips)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "keyword": self.keyword,
            "timeline_start": self.timeline_start,
            "timeline_end": self.timeline_end,
            "timeline_duration": self.timeline_duration,
            "clips": [c.to_dict() for c in self.clips],
            "clip_count": len(self.clips),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CutEntry":
        clips = [CutClip.from_dict(c) for c in data.get("clips", [])]
        return cls(
            index=data.get("index", 0),
            keyword=data.get("keyword", ""),
            timeline_start=data.get("timeline_start", 0.0),
            timeline_end=data.get("timeline_end", 0.0),
            timeline_duration=data.get("timeline_duration", 0.0),
            clips=clips,
        )


@dataclass
class Track3Keywords:
    """Container for track3_keywords.json data."""

    keywords: List[Keyword] = field(default_factory=list)
    sequence_name: str = ""
    count: int = 0
    version: str = "1.0"

    def __post_init__(self):
        self.count = len(self.keywords)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_name": self.sequence_name,
            "count": len(self.keywords),
            "keywords": [k.to_dict() for k in self.keywords],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track3Keywords":
        keywords = [Keyword.from_dict(k) for k in data.get("keywords", [])]
        return cls(
            keywords=keywords,
            sequence_name=data.get("sequence_name", ""),
            version=data.get("version", "1.0"),
        )


@dataclass
class CutList:
    """Container for cut_list.json data."""

    cuts: List[CutEntry] = field(default_factory=list)
    count: int = 0
    total_clips: int = 0
    markers_with_clips: int = 0
    ai_clips: int = 0
    version: str = "1.0"

    def __post_init__(self):
        self.count = len(self.cuts)
        self.total_clips = sum(len(c.clips) for c in self.cuts)
        self.markers_with_clips = sum(1 for c in self.cuts if c.clips)
        self.ai_clips = sum(
            sum(1 for clip in c.clips if clip.source == "ai_matched")
            for c in self.cuts
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": len(self.cuts),
            "total_clips": self.total_clips,
            "markers_with_clips": self.markers_with_clips,
            "ai_clips": self.ai_clips,
            "cuts": [c.to_dict() for c in self.cuts],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CutList":
        cuts = [CutEntry.from_dict(c) for c in data.get("cuts", [])]
        return cls(
            cuts=cuts,
            version=data.get("version", "1.0"),
        )


@dataclass
class SceneMatch:
    """A scene match result from AI analysis."""

    keyword: str
    video_path: str
    video_name: str
    suggested_scenes: List[VideoSegment] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "video_path": self.video_path,
            "video_name": self.video_name,
            "suggested_scenes": [s.to_dict() for s in self.suggested_scenes],
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneMatch":
        scenes = [VideoSegment.from_dict(s) for s in data.get("suggested_scenes", [])]
        return cls(
            keyword=data.get("keyword", ""),
            video_path=data.get("video_path", ""),
            video_name=data.get("video_name", ""),
            suggested_scenes=scenes,
            confidence=data.get("confidence", 0.0),
        )
