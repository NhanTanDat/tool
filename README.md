Autotool – Python + Adobe Premiere Pro Automation Toolkit
=========================================================

Ngôn ngữ: Vietnamese (có thể chuyển sang English nếu cần). Đây là bộ công cụ tự động hỗ trợ:

1. Thu thập link video YouTube theo danh sách từ khóa (Selenium).
2. Import tài nguyên media hàng loạt vào Premiere (ExtendScript `.jsx`).
3. Xuất metadata timeline (clip start/end) từ Premiere ra CSV.
4. Đọc CSV timeline và tự động cắt – chèn subclip vào sequence.
5. Chạy các script `.jsx` trực tiếp từ Python thông qua COM.

Thư mục chính quan trọng:
- `core/downloadTool/` – công cụ lấy link (`get_link.py`).
- `core/premierCore/` – các script Premiere: `getTimeline.jsx`, `cutAndPush.jsx`, `importResource.jsx`.
- `data/` – nơi tập trung input/output (tự tạo nếu chưa có).

------------------------------------------------------------
CÀI ĐẶT
------------------------------------------------------------

### Yêu cầu cần cài đặt

1. **Python 3.10**
   - Tải và cài đặt từ [python.org](https://www.python.org/downloads/)
   - Chọn phiên bản Python 3.10.x
   - Trong quá trình cài đặt, nhớ tích "Add Python to PATH"

2. **VS Code (Visual Studio Code)**
   - Tải và cài đặt từ [code.visualstudio.com](https://code.visualstudio.com/)
   - Khuyến nghị cài thêm extension: Python, Prettier

3. **Git**
   - Tải và cài đặt từ [git-scm.com](https://git-scm.com/downloads)
   - Git được dùng để lấy code mới và quản lý phiên bản

4. **Adobe Premiere Pro**
   - Cần phiên bản hỗ trợ ExtendScript (các bản CC đều hỗ trợ)

5. **Trình duyệt Chrome**
   - Dùng cho Selenium thu thập link YouTube

6. **ExtendScript Debugger for VS Code**
   - Cài từ [marketplace.visualstudio.com](https://marketplace.visualstudio.com/items?itemName=Adobe.extendscript-debug)
   - Dùng để debug các file `.jsx` trong VS Code
------------------------------------------------------------

### Các bước cài đặt

**Bước 1:** Mở PowerShell với quyền quản trị và chạy lệnh sau để cho phép chạy script:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Bước 2:** Clone repository (nếu chưa có):
```bash
git clone <repository-url>
cd autotool
```

**Bước 3:** Chạy file setup tự động:
```cmd
setup.bat
```

File `setup.bat` sẽ tự động:
- Tạo môi trường ảo Python (virtual environment)
- Cài đặt tất cả các thư viện cần thiết từ `requirements.txt`
- Thiết lập cấu trúc thư mục cần thiết

**Lưu ý:**
- Nếu gặp lỗi khi chạy `setup.bat`, hãy đảm bảo Python 3.10 đã được thêm vào PATH
- Kiểm tra bằng cách chạy: `python --version` trong Command Prompt

------------------------------------------------------------
SỬ DỤNG
------------------------------------------------------------

### 1. Thu thập link YouTube

Chạy GUI chính của ứng dụng:
```cmd
python GUI/mainGUI.py
```

Trong giao diện:
- `parent_folder`: thư mục sẽ chứa video
- `project_path`: đường dẫn đến file `.prproj` của Premiere
- `link_list_path`: nơi lưu link thu thập được

### 2. Import media vào Premiere

Script `importResource.jsx` sẽ tự động:
- Tạo Bin cho mỗi thư mục con
- Import toàn bộ file media vào Bin tương ứng

Ví dụ cấu trúc thư mục:
```
E:\mediaTopics\
    Amber_Portwood_tiktok\  (chứa nhiều .mp4)
    cat_clips\
    tutorial_segments\
```

### 3. Xuất timeline ra CSV

Script `getTimeline.jsx`:
- Xuất metadata của các clip đã chọn
- Lưu thành `timeline_export.csv` và `timeline_export.json`

Cách sử dụng:
1. Mở sequence trong Premiere
2. Chọn các clip cần xuất
3. Chạy script (tự động qua Python hoặc thủ công)

### 4. Tự động cắt & chèn clip

Script `cutAndPush.jsx`:
- Đọc file CSV timeline
- Tự động cắt và chèn subclip vào sequence
- Sử dụng clip ngẫu nhiên từ các Bin


------------------------------------------------------------
CẤU TRÚC DỮ LIỆU & THƯ MỤC `data/`
------------------------------------------------------------

Thư mục `data/` chứa:
- `list_name.txt` – danh sách từ khóa tìm kiếm (mỗi dòng 1 keyword)
- `dl_links.txt` – link video đã thu thập
- `timeline_export.csv` / `.json` – metadata timeline từ Premiere
- `timeline_export_merged.csv` – timeline đã xử lý (tùy chọn)

Thư mục sẽ tự động được tạo nếu chưa có.

------------------------------------------------------------
QUY TRÌNH LÀM VIỆC (END-TO-END)
------------------------------------------------------------

1. Tạo danh sách từ khóa trong `data/list_name.txt`
2. Chạy GUI để thu thập link: `python GUI/mainGUI.py`
3. Tải media về và sắp xếp vào các thư mục theo chủ đề
4. Mở Premiere Pro và project của bạn
5. Import media tự động (script sẽ chạy qua COM)
6. Chọn clip và xuất timeline
7. Chạy script tự động cắt & chèn clip
8. Kiểm tra và tinh chỉnh trong Premiere


------------------------------------------------------------
TROUBLESHOOTING (XỬ LÝ LỖI)
------------------------------------------------------------

| Vấn đề | Nguyên nhân | Cách xử lý |
|--------|-------------|------------|
| Không chạy được JSX | Premiere chưa mở / lỗi COM | Mở Premiere trước, kiểm tra Python 64-bit |
| "Invalid class string" | ProgID COM không đúng | Xem chi tiết lỗi để biết ProgID phù hợp |
| Không tạo clip nào | Không tìm thấy Bin | Kiểm tra tên Bin khớp với CSV (space → `_`) |
| CSV rỗng khi export | Chưa chọn clip | Chọn ít nhất 1 clip trước khi export |
| Lỗi tiếng Việt | Unicode trong path | Dùng đường dẫn không dấu |
| setup.bat không chạy | Python chưa có trong PATH | Cài lại Python, tích "Add to PATH" |

**Lưu ý về COM (Windows):**
- Đảm bảo Python 64-bit nếu Premiere là 64-bit
- Kiểm tra Python version: `python --version`
- Kiểm tra architecture: `python -c "import platform; print(platform.architecture())"`


------------------------------------------------------------
LICENSE
------------------------------------------------------------
Xem file `LICENSE` (nếu chưa có nội dung, thêm theo nhu cầu: MIT / Apache 2.0 / GPL...).

------------------------------------------------------------
LIÊN HỆ / GÓP Ý
------------------------------------------------------------
Bạn có thể mở issue hoặc gửi yêu cầu thêm chức năng.

---
Nếu cần bản tiếng Anh hoặc bổ sung phần nào, hãy yêu cầu thêm.

