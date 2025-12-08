import os
import sys
import runpy

"""
auto_cut_pipeline.py
--------------------
Phiên bản đơn giản: KHÔNG dùng core.ai.transcribe nữa.

Nhiệm vụ:
- Sau khi đã tải xong VIDEO (và ẢNH nếu có),
- Gọi lại script core/ai/gen_timeline_from_list.py
  để sinh file timeline_export_merged.csv trong thư mục data/<project_slug>.

Script gen_timeline_from_list.py vốn đã chạy ngon khi bạn chạy:
    py -3.12 gen_timeline_from_list.py

Ở đây ta chỉ tự động chạy nó trong cùng process, để log vẫn đổ về GUI
(thông qua logging_bridge nếu có).
"""


def auto_generate_timeline(resource_dir: str, project_slug: str) -> None:
    """
    Hàm được mainGUI gọi sau khi download xong.

    :param resource_dir: thư mục resource của project (hiện tại chỉ dùng để log / future use)
    :param project_slug: slug project (vd: 'naruto', 'hangcaotoluuban')
    """
    # Thư mục của file này (core/ai)
    this_dir = os.path.abspath(os.path.dirname(__file__))

    # Đường dẫn tới gen_timeline_from_list.py
    gen_script = os.path.join(this_dir, "gen_timeline_from_list.py")

    if not os.path.isfile(gen_script):
        raise RuntimeError(
            f"Không tìm thấy gen_timeline_from_list.py tại: {gen_script}\n"
            f"Hãy kiểm tra lại cấu trúc thư mục core/ai."
        )

    # Đảm bảo project root nằm trong sys.path để script con import được core.*
    root_dir = os.path.abspath(os.path.join(this_dir, "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Set một số biến môi trường cho script gen_timeline_from_list dùng nếu cần
    os.environ["AUTOTOOL_PROJECT_SLUG"] = project_slug
    os.environ["AUTOTOOL_RESOURCE_DIR"] = resource_dir

    # Chuyển CWD sang core/ai để mọi đường dẫn tương đối trong script con giống
    old_cwd = os.getcwd()
    try:
        os.chdir(this_dir)
        # Chạy script như thể chạy: py gen_timeline_from_list.py
        # run_name="__main__" để nó chạy nhánh if __name__ == "__main__":
        runpy.run_path(gen_script, run_name="__main__")
    finally:
        os.chdir(old_cwd)
