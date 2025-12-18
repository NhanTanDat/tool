# Quick Start: AI Auto V4 Workflow

## 🚀 Bắt đầu nhanh trong 5 phút

### 1️⃣ Cài đặt thêm dependencies

```bash
pip install google-generativeai yt-dlp
```

### 2️⃣ Setup Premiere Project

**Cấu trúc folder:**
```
MyProject/
├── MyProject.prproj
└── resource/
    ├── video1.mp4
    ├── video2.mp4
    └── video3.mp4
```

**Trong Premiere:**
1. Tạo Sequence với **4 video tracks** (V1, V2, V3, V4)
2. Thêm **Text Clips** vào **Track 3 (V3)**:
   - Mỗi text clip = 1 keyword
   - Tên clip = keyword bạn muốn tìm
   - Vị trí & độ dài = timeline bạn mong muốn

**Ví dụ Track 3:**
```
┌─────────────────────────────────────┐
│ V3: [cat playing][dog swim][sunset] │ ← Text clips với keywords
├─────────────────────────────────────┤
│ V1: [Main footage...              ] │
└─────────────────────────────────────┘
     0s        10s       20s       30s
```

### 3️⃣ Chạy AutoTool

```bash
python GUI/mainGUI.py
```

1. Tab **"Auto Premier"**
2. Thêm file `.prproj`
3. Click **"🤖 AI Auto V4"**
4. Nhập Gemini API key (hoặc bỏ qua)
5. Làm theo hướng dẫn trên màn hình

### 4️⃣ Chạy JSX Scripts

#### Bước 1: Extract Keywords
1. Mở **VS Code**
2. Mở file `core/premierCore/extractTrack3Keywords.jsx`
3. Nhấn **Ctrl+Shift+P** → "ExtendScript: Evaluate Script"
4. Chọn **"Adobe Premiere Pro"**

→ Output: `data/[project]/track3_keywords.json`

#### Bước 2: AI Analyze (Tự động)
Tool sẽ tự động phân tích videos trong `resource/`

#### Bước 3: Auto Cut & Push
1. Mở file `core/premierCore/autoCutAndPushV4.jsx`
2. Nhấn **Ctrl+Shift+P** → "ExtendScript: Evaluate Script"
3. Chọn **"Adobe Premiere Pro"**

→ Kết quả: **Track V4 được fill tự động!**

---

## 🎯 Ví dụ cụ thể

### Input (Track V3):
```
[0-10s]  Text: "cat playing"
[10-25s] Text: "dog running"
[25-40s] Text: "sunset beach"
```

### Resource folder:
```
resource/funny_cats.mp4      (10 phút, nhiều cảnh mèo)
resource/dogs_compilation.mp4 (15 phút, nhiều cảnh chó)
resource/nature_4k.mp4        (20 phút, cảnh thiên nhiên)
```

### Output (Track V4):
```
[0-10s]  funny_cats.mp4 (từ 2:15 đến 2:25)      ← AI chọn cảnh mèo đẹp nhất
[10-25s] dogs_compilation.mp4 (từ 5:30 đến 5:45) ← AI chọn cảnh chó chạy
[25-40s] nature_4k.mp4 (từ 12:00 đến 12:15)     ← AI chọn cảnh sunset
```

---

## ⚡ Tips nhanh

### ✅ Để AI hoạt động tốt nhất:
1. **Videos có metadata đầy đủ** (title, description)
2. **Keywords rõ ràng** (e.g., "cat playing" thay vì "cute animal")
3. **Dùng Gemini API** để AI thông minh hơn

### 🔧 Nếu gặp lỗi:
1. Check **Premiere có đủ 4 tracks** chưa
2. Check **resource/ có videos** chưa
3. Xem **log trong GUI** để debug
4. Đọc file `AI_AUTO_V4_WORKFLOW.md` để biết chi tiết

---

## 🆓 Không có Gemini API?

**Vẫn hoạt động!** Tool sẽ dùng **simple matching**:
- Match keyword với title: OK ✓
- Match keyword với description: OK ✓
- Match keyword với tags: OK ✓

→ Chất lượng: **70-80% accuracy** (tùy metadata videos)

---

## 📹 Video Demo

*(Thêm link video demo nếu có)*

---

**Có vấn đề?** Xem [Troubleshooting](AI_AUTO_V4_WORKFLOW.md#troubleshooting)

**Muốn tùy chỉnh?** Xem [Advanced Usage](AI_AUTO_V4_WORKFLOW.md#advanced-usage)
