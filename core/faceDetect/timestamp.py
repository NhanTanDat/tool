import os
# Giảm log TensorFlow: 0=ALL,1=INFO,2=WARNING,3=ERROR. Đặt 2 để tắt INFO (bao gồm oneDNN info)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
# Nếu vẫn còn dòng oneDNN có thể bổ sung dòng dưới (tắt tối ưu oneDNN) nhưng sẽ hơi giảm hiệu năng:
# os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import cv2
from deepface import DeepFace
import contextlib, io, sys

# Đường dẫn video và thư mục chứa ảnh nhân vật (database)
video_path = "core/faceDetect/input.mp4"
db_path = "core/faceDetect/faces_db"   # trong thư mục này bạn để 1 hoặc nhiều ảnh target, ví dụ: "faces_db/actor1.jpg"

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
frame_no = 0

timestamps = []

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Để tiết kiệm thời gian: chỉ check các frame cách nhau 10 seconds (tùy chỉnh)
    if frame_no % (10 * fps) == 0:
        try:
            # Chặn mọi stdout tạm thời để DeepFace không in ra mảng pixel "Searching [[[ ... ]]] ..."
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = DeepFace.find(
                    img_path=frame,
                    db_path=db_path,
                    enforce_detection=False,
                    silent=True  # thêm cờ silent nếu version hỗ trợ
                )
            
            if len(result) > 0 and len(result[0]) > 0:
                # Có khuôn mặt trùng trong database
                time_sec = frame_no / fps
                timestamps.append(time_sec)
                print(f"Nhân vật xuất hiện tại giây {time_sec:.2f}")
        except Exception as e:
            print("Lỗi xử lý frame:", e)

    frame_no += 1

cap.release()

print("Các timestamp nhân vật xuất hiện:", timestamps)
