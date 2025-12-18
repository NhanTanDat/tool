# AI Auto V4 Workflow - Hướng dẫn sử dụng

## 🎯 Tổng quan

**AI Auto V4 Workflow** là tính năng mới cho phép tool **tự động đọc keywords từ Track 3** trong Premiere Pro, sử dụng **AI để tìm video phù hợp**, và **tự động cắt + đẩy vào Track V4** đúng timeline.

### Workflow cũ (Manual):
```
User → Nhập keywords thủ công → Download videos → Chỉnh sửa manual
```

### Workflow mới (AI-Powered):
```
Track 3 (Keywords) → AI Analyze → Auto Cut → Track V4 (Matched Scenes)
```

---

## 🔧 Cấu trúc Premiere Project

### Yêu cầu Sequence:
Sequence của bạn cần có **ít nhất 4 video tracks**:

```
V4 (Track 4) ← Sẽ được fill tự động bởi AI
V3 (Track 3) ← Chứa TEXT CLIPS với keywords + timing
V2 (Track 2)
V1 (Track 1) ← Main footage
```

### Cách setup Track 3:
1. Tạo **Text Clips** trong Track 3
2. Mỗi clip = 1 keyword
3. Đặt **vị trí và độ dài** của text clip theo timeline mong muốn

**Ví dụ:**
```
Track 3:
[0s---10s]  "cat playing"
[10s---25s] "dog running"
[25s---40s] "sunset beach"
```

→ Tool sẽ tìm video về "cat playing" và đẩy vào V4 từ 0s-10s
→ Tool sẽ tìm video về "dog running" và đẩy vào V4 từ 10s-25s
→ ...

---

## 📋 Quy trình sử dụng

### Bước 1: Chuẩn bị
1. **Tạo Premiere Project** với folder `resource/` chứa videos
2. **Tạo Sequence** với ít nhất 4 video tracks
3. **Thêm Text Clips vào Track 3** với keywords

### Bước 2: Chạy trong AutoTool GUI
1. Mở `mainGUI.py`
2. Chuyển sang tab **"Auto Premier"**
3. Thêm file `.prproj` vào danh sách
4. Nhấn nút **"🤖 AI Auto V4"**

### Bước 3: Nhập Gemini API Key (optional)
- Nếu có **Gemini API key** → nhập để dùng AI thông minh
- Nếu **không có** → tool sẽ dùng fallback method (simple keyword matching)

**Lấy API key tại:** https://makersuite.google.com/app/apikey

### Bước 4: Workflow tự động
Tool sẽ thực hiện **3 bước tự động**:

#### Step 1: Extract Keywords từ Track 3
- Chạy `extractTrack3Keywords.jsx`
- Output: `data/[project_slug]/track3_keywords.json`

**File JSON mẫu:**
```json
{
  "version": "1.0",
  "count": 3,
  "keywords": [
    {
      "index": 0,
      "keyword": "cat playing",
      "start_seconds": 0.0,
      "end_seconds": 10.0,
      "duration_seconds": 10.0,
      "start_timecode": "00:00:00.000",
      "end_timecode": "00:00:10.000"
    },
    ...
  ]
}
```

#### Step 2: AI Analyze Videos
- Python script phân tích videos trong `resource/`
- AI match keyword với video metadata (title, description, tags)
- Tìm scenes phù hợp nhất
- Output: `data/[project_slug]/scene_matches.json`

**File JSON mẫu:**
```json
{
  "keywords": [...],
  "matches": {
    "cat playing": [
      {
        "video_path": "/path/to/video1.mp4",
        "confidence": 0.95,
        "reason": "Video title contains 'cat playing'",
        "suggested_scenes": [
          {
            "start_time": 5.0,
            "end_time": 15.0,
            "description": "Cat playing with ball"
          }
        ]
      }
    ]
  }
}
```

#### Step 3: Auto Cut và Push vào V4
- Chạy `autoCutAndPushV4.jsx`
- Import videos vào bin "AI_Matched_Scenes"
- Cắt đúng scene từ video
- Đẩy vào V4 đúng timing của keyword

---

## 🤖 Cơ chế AI Matching

### 1. Gemini AI Mode (với API key)
```python
AI Prompt:
"Phân tích video này và xác định có liên quan đến keyword '{keyword}' không?
Title: ...
Description: ...
Tags: ...

Trả về: {relevant, confidence, suggested_scenes}"
```

**Ưu điểm:**
- Hiểu ngữ nghĩa sâu
- Có thể phân tích nội dung phức tạp
- Gợi ý scenes chính xác

### 2. Fallback Mode (không có API key)
```python
Simple keyword matching:
- Check keyword in title: +0.5 score
- Check keyword in description: +0.3 score
- Check keyword in tags: +0.2 score

If score > 0.3 → relevant
```

**Ưu điểm:**
- Miễn phí
- Không cần API
- Vẫn hoạt động với metadata tốt

---

## 📁 Cấu trúc File Output

```
project_root/
├── my_project.prproj
├── resource/              ← Videos nguồn
│   ├── video1.mp4
│   ├── video2.mp4
│   └── ...
└── data/
    └── my_project/
        ├── track3_keywords.json      ← Keywords extracted
        ├── track3_keywords.csv
        ├── scene_matches.json        ← AI analysis results
        └── path.txt                  ← Project config
```

---

## 🎬 Ví dụ thực tế

### Scenario: Tạo video compilation về động vật

**Track 3 setup:**
```
[00:00 - 00:10] "cat playing"
[00:10 - 00:20] "dog swimming"
[00:20 - 00:30] "bird flying"
```

**Resource folder:**
```
resource/
├── funny_cat_compilation.mp4
├── dogs_at_beach.mp4
├── nature_birds.mp4
├── random_video1.mp4
└── random_video2.mp4
```

**Kết quả sau khi chạy AI Auto V4:**

**V4 Track:**
```
[00:00 - 00:10] funny_cat_compilation.mp4 [clip from 0:15 to 0:25]
[00:10 - 00:20] dogs_at_beach.mp4 [clip from 1:20 to 1:30]
[00:20 - 00:30] nature_birds.mp4 [clip from 0:05 to 0:15]
```

---

## 🔍 Troubleshooting

### Vấn đề 1: "ERROR: Sequence không có Video Track 4"
**Giải pháp:** Thêm track mới trong Premiere (Sequence → Add Tracks)

### Vấn đề 2: "No matches found for keyword"
**Nguyên nhân:**
- Videos không có metadata liên quan
- Keyword quá cụ thể

**Giải pháp:**
- Thêm videos phù hợp vào `resource/`
- Dùng keywords tổng quát hơn
- Cung cấp Gemini API key để AI phân tích tốt hơn

### Vấn đề 3: "Cannot import video"
**Nguyên nhân:**
- File path không hợp lệ
- Video format không được Premiere hỗ trợ

**Giải pháp:**
- Check đường dẫn file
- Convert video về MP4/MOV

### Vấn đề 4: Scene không khớp timeline
**Nguyên nhân:**
- Scene ngắn hơn required duration
- Scene dài hơn required duration

**Xử lý:**
- Nếu scene dài hơn → auto crop
- Nếu scene ngắn hơn → warning trong log

---

## 🚀 Advanced Usage

### Tùy chỉnh AI Prompt
Edit file `core/ai/video_scene_matcher.py`, method `ai_analyze_video_for_keyword()`:

```python
prompt = f"""
Phân tích video và tìm scenes phù hợp với "{keyword}".

[Tùy chỉnh prompt của bạn ở đây]

Return JSON format...
"""
```

### Chạy từ Command Line
```bash
# Step 1: Extract keywords
python -c "from core.ai.auto_v4_workflow import *; ..."

# Step 2: AI Match
python core/ai/video_scene_matcher.py \
  --keywords-json data/project/track3_keywords.json \
  --video-folder resource/ \
  --output data/project/scene_matches.json \
  --gemini-key YOUR_API_KEY

# Step 3: Auto cut (chạy JSX trong Premiere)
```

### Batch Processing
Trong GUI, có thể thêm nhiều projects và loop qua từng project.

---

## 📊 Performance Tips

### Tối ưu tốc độ:
1. **Giảm số videos** trong resource/ (chỉ giữ videos liên quan)
2. **Dùng fallback mode** nếu không cần AI phức tạp
3. **Pre-organize videos** theo topic folders

### Tối ưu chất lượng:
1. **Dùng Gemini AI** với API key
2. **Videos có metadata tốt** (title, description, tags đầy đủ)
3. **Keywords rõ ràng, cụ thể**

---

## 📚 Tham khảo Code

### JSX Scripts:
- `core/premierCore/extractTrack3Keywords.jsx` - Đọc Track 3
- `core/premierCore/autoCutAndPushV4.jsx` - Auto cut và push

### Python Modules:
- `core/ai/video_scene_matcher.py` - AI matching logic
- `core/ai/auto_v4_workflow.py` - Workflow orchestrator

### GUI Integration:
- `GUI/mainGUI.py` - Method `run_ai_v4_workflow()`

---

## 🎓 Best Practices

### ✅ DO:
- Đặt keywords rõ ràng, dễ hiểu
- Organize videos theo topic trong resource/
- Dùng Text Clips có màu khác nhau cho Track 3
- Backup project trước khi chạy automation

### ❌ DON'T:
- Dùng keywords quá dài hoặc phức tạp
- Mix nhiều ngôn ngữ trong 1 keyword
- Để Track V4 có clips trước khi chạy (sẽ bị overwrite)
- Chạy trên project quan trọng mà chưa backup

---

## 🔮 Roadmap & Future Features

### Planned:
- [ ] Multi-language support (Vietnamese, English, etc.)
- [ ] Scene detection using computer vision
- [ ] Auto color grading based on keyword mood
- [ ] Speech-to-text để match với audio content
- [ ] Export report PDF về matched scenes

### Ideas:
- Timeline preview trong GUI
- Drag-and-drop keywords vào timeline
- Live preview của matched scenes

---

## 📞 Support

Nếu gặp vấn đề hoặc có câu hỏi:
1. Check **Troubleshooting** section
2. Xem log trong GUI tab "Auto Premier"
3. Mở issue trên GitHub repository

---

## 📄 License

Xem file `LICENSE` trong project root.

---

**Happy Editing! 🎬✨**
