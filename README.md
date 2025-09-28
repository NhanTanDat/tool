Autotool – Python + Adobe Premiere Pro Automation Toolkit
=========================================================

Ngôn ngữ: Vietnamese (có thể chuyển sang English nếu cần). Đây là bộ công cụ tự động hỗ trợ:

1. Thu thập link video YouTube theo danh sách từ khóa (Selenium).
2. Import tài nguyên media hàng loạt vào Premiere (ExtendScript `.jsx`).
3. Xuất metadata timeline (clip start/end) từ Premiere ra CSV.
4. Đọc CSV timeline và tự động cắt – chèn subclip vào sequence.
5. Chạy các script `.jsx` trực tiếp từ Python thông qua COM (`run_jsx.py`).

Thư mục chính quan trọng:
- `core/downloadTool/` – công cụ lấy link (`get_link.py`).
- `core/premierCore/` – các script Premiere: `getTimeline.jsx`, `cutAndPush.jsx`, `importResource.jsx`, `run_jsx.py`.
- `data/` – nơi tập trung input/output (tự tạo nếu chưa có).

------------------------------------------------------------
YÊU CẦU HỆ THỐNG / DEPENDENCIES
------------------------------------------------------------

Phần mềm bắt buộc:
1. Windows 10/11.
2. Python 3.10+.
3. Google Chrome (bản mới).
4. ChromeDriver (thường Selenium Manager tự xử lý khi dùng Selenium 4, nếu cần thủ công thì tải phù hợp version Chrome và để trong PATH).
5. Adobe Premiere Pro (phiên bản hỗ trợ ExtendScript – các bản CC vẫn hỗ trợ). Premiere phải đang mở khi chạy các lệnh liên quan `.jsx`.

Tạo môi trường ảo (khuyến nghị):
```
python -m venv venv
.\venv\Scripts\activate
```

Python packages (cài qua pip):
```
pip install -r requirements.txt
```
Tùy chọn thêm (nếu mở rộng):
```
pip install watchdog rich
```

------------------------------------------------------------
CẤU TRÚC DỮ LIỆU & THƯ MỤC `data/`
------------------------------------------------------------

`data/` được dùng để:
- Input từ khóa: `list_name.txt` (mỗi dòng 1 keyword).
- Output link đã thu thập: `dl_links.txt`.
- Các file export timeline: `timeline_export.csv`, `timeline_export.json` (từ `getTimeline.jsx`).
- File timeline đã merge hoặc đã xử lý: `timeline_export_merged.csv` (hoặc tên bạn đặt – script cắt đọc CSV).

Nếu chưa có thư mục `data/`, các script sẽ tự tạo (ở cấp root repo hoặc cạnh script tùy logic dynamic path).

------------------------------------------------------------
1. THU THẬP LINK YOUTUBE (`get_link.py`)
------------------------------------------------------------

chạy GUI:
parent_folder là thư mục sẽ chứa video
project_path là đường dẫn đến file proprej
link_list_path là nơi lưu link thu thập
```
Ghi chú:
- Script tự scroll 1 lần để lấy thêm kết quả.
- Giới hạn ~20 link đầu mỗi keyword (có thể chỉnh trong mã: lát cắt `[:20]`).

------------------------------------------------------------
2. IMPORT MEDIA VÀO PREMIERE (`importResource.jsx`)
------------------------------------------------------------

Mục tiêu: mỗi thư mục con bên trong một thư mục cha -> tạo một Bin trùng tên và import toàn bộ file trực tiếp (không đệ quy sâu hơn).

Ví dụ bạn có cấu trúc:
```
E:\mediaTopics\
	Amber_Portwood_tiktok\  (chứa nhiều .mp4)
	cat_clips\
	tutorial_segments\
```

Sửa cuối file `importResource.jsx` (hoặc inject thủ công) đường dẫn test:
```jsx
importMultipleFolders("E:/mediaTopics");
```

Chạy trong Premiere:
1. Mở Premiere + Project mong muốn.
2. Mở ExtendScript Toolkit / hoặc bảng Scripts / hoặc dùng công cụ khác cho phép chạy JSX.
3. Load và chạy file `importResource.jsx`.
4. Kiểm tra Project Panel: mỗi thư mục con -> một Bin, file mới được thêm (file trùng tên bỏ qua).

Chạy qua Python (tùy chọn) dùng tiện ích `run_jsx.py` (xem phần 5).

------------------------------------------------------------
3. XUẤT TIMELINE RA CSV (`getTimeline.jsx`)
------------------------------------------------------------

Script thực hiện:
- Tìm các video track có clip đang được chọn.
- Lấy track có index lớn nhất (ở trên cùng trong UI) trong số đó.
- Thu thập metadata clip: name, startSeconds, endSeconds, in/out...
- Ghi ra `data/timeline_export.csv` và `data/timeline_export.json`.

Chuẩn bị trước khi chạy:
1. Mở sequence đúng.
2. Chọn ít nhất một clip trên track mong muốn (script dựa vào selection để xác định track).
3. Chạy `getTimeline.jsx`.

Output CSV (ví dụ cột chính):
```
name,startSeconds,endSeconds,inPointSeconds,outPointSeconds,textContent
Clip A,0.0,5.2,0.0,5.2,
Clip B,5.2,9.7,0.0,4.5,
```

------------------------------------------------------------
4. TỰ ĐỘNG CẮT & CHÈN CLIP (`cutAndPush.jsx`)
------------------------------------------------------------

Chức năng:
- Đọc một file CSV timeline (hiện tại hỗ trợ duy nhất CSV).
- Với mỗi entry có textContent -> coi đó là tên Bin (space chuyển thành `_`).
- Lặp chèn subclip ngẫu nhiên (3–4 giây) để phủ kín khoảng thời gian của entry.
- Sử dụng strictly thời gian dạng giây (không dùng ticks).

Cấu hình mặc định cuối file:
```jsx
var csvDef = joinPath(DATA_FOLDER, 'timeline_export_merged.csv');
cutAndPushAllTimeline(csvDef);
```
Bạn có thể đổi thành `timeline_export.csv` nếu muốn dùng trực tiếp mà không merge.

Yêu cầu trước khi chạy:
1. Các Bin phải tồn tại (tên khớp textContent đã được chuẩn hóa thành `_`).
2. Đã import media.
3. Đã có `timeline_export_merged.csv` hoặc `timeline_export.csv` trong `data/`.

Nếu muốn chạy thủ công:
1. Mở Premiere + sequence.
2. Chạy `cutAndPush.jsx`.
3. Quan sát track trên cùng được chèn clip.

------------------------------------------------------------
5. CHẠY JSX TỪ PYTHON (`run_jsx.py`)
------------------------------------------------------------

Tiện ích tổng quát chạy một hoặc nhiều file `.jsx` trong Premiere (qua COM):

Ví dụ chạy đơn:
```
python core/premierCore/run_jsx.py core/premierCore/getTimeline.jsx
```

Chạy nhiều file nối tiếp:
```
python core/premierCore/run_jsx.py core/premierCore/importResource.jsx core/premierCore/getTimeline.jsx core/premierCore/cutAndPush.jsx
```

Inject return expression (lấy biến nội bộ):
```
python core/premierCore/run_jsx.py core/premierCore/getTimeline.jsx --inject "JSON.stringify(timelineEntries)"
```

Dùng trong mã Python:
```python
from core.premierCore.run_jsx import run_jsx_file, run_multiple_jsx

run_jsx_file(r"p:/coddd/autotool/core/premierCore/getTimeline.jsx")
run_multiple_jsx([
		r"p:/coddd/autotool/core/premierCore/getTimeline.jsx",
		r"p:/coddd/autotool/core/premierCore/cutAndPush.jsx",
])
```

Lưu ý:
- Premiere phải mở trước.
- Nếu lỗi COM: kiểm tra đã cài `comtypes` và quyền truy cập.
- Muốn trả JSON: kết thúc file JSX bằng `JSON.stringify(obj);` hoặc dùng `--inject`.

------------------------------------------------------------
QUY TRÌNH LÀM VIỆC GỢI Ý (END-TO-END)
------------------------------------------------------------

1. Tạo / cập nhật từ khóa trong `data/list_name.txt`.
2. Thu thập link: `python core/downloadTool/get_link.py` (kết quả: `dl_links.txt`).
3. Chuẩn bị media thủ công (tải về theo link) vào các thư mục đặt tên khớp với textContent mong muốn (vd: `Amber_Portwood_tiktok`).
4. Import media: chạy `importResource.jsx` (hoặc qua Python với `run_jsx.py`).
5. Chọn clip trên track cần xuất -> chạy `getTimeline.jsx` để có `timeline_export.csv`.
6. (Tùy chọn) Merge / xử lý CSV thành `timeline_export_merged.csv` nếu cần đổi textContent.
7. Chạy `cutAndPush.jsx` để tạo sequence tự động.
8. Kiểm tra và tinh chỉnh thủ công trong Premiere.

------------------------------------------------------------
MẸO / TROUBLESHOOTING
------------------------------------------------------------

| Vấn đề | Nguyên nhân thường gặp | Cách xử lý |
|--------|------------------------|------------|
| Không chạy được JSX từ Python | Premiere chưa mở / sai ProgID COM | Mở Premiere trước, kiểm tra `comtypes` |
| Không tạo clip nào khi cutAndPush | Không tìm thấy Bin trùng tên | Kiểm tra textContent trong CSV & tên Bin (space -> `_`) |
| CSV rỗng | Không chọn clip trước khi export timeline | Chọn ít nhất 1 clip trên track muốn lấy |
| Lỗi codec khi import | File không hỗ trợ / hỏng | Bật whitelist hoặc bỏ file lỗi |
| Lỗi tiếng Việt đường dẫn | Ký tự Unicode trong path | Dùng ổ đĩa / thư mục không dấu nếu gặp vấn đề |

------------------------------------------------------------
MỞ RỘNG TƯƠNG LAI (IDEAS)
------------------------------------------------------------
- Thêm bridge file-based command queue (đã có ý tưởng) để trigger action mà không chạy full script.
- Thêm GUI Python hợp nhất (trigger export, cut, import). 
- Tự động tạo Bin nếu thiếu khi cutAndPush.
- Thêm tham số số lần scroll YouTube.
- Logging đẹp (rich) / progress bar.

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

