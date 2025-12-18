"""
control_jsx.py

Module để tự động chạy JSX scripts trong Premiere Pro
Sử dụng pywinauto để automation VS Code + ExtendScript
"""

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from time import sleep
import pyperclip
import os
import subprocess


def copy_paste(text):
    """Copy text to clipboard và paste"""
    pyperclip.copy(text)
    sleep(0.3)
    send_keys('^v')
    sleep(0.3)


def ensure_premiere_running():
    """Đảm bảo Premiere Pro đang chạy"""
    for w in Desktop(backend="uia").windows():
        if "Adobe Premiere Pro" in w.window_text():
            print("[control_jsx] Premiere Pro đã chạy")
            return True

    print("[control_jsx] Khởi động Premiere Pro...")
    try:
        subprocess.Popen([
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"
        ])
        sleep(15)  # Đợi Premiere khởi động
        return True
    except Exception as e:
        print(f"[control_jsx] ERROR: Không khởi động được Premiere: {e}")
        return False


def ensure_vscode_running():
    """Đảm bảo VS Code đang chạy"""
    for w in Desktop(backend="uia").windows():
        if "Visual Studio Code" in w.window_text():
            print("[control_jsx] VS Code đã chạy")
            return True

    print("[control_jsx] Khởi động VS Code...")
    try:
        # Thử các path phổ biến
        vscode_paths = [
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
            r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(
                os.environ.get('USERNAME', '')
            ),
        ]

        for path in vscode_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                sleep(5)
                return True

        # Fallback: thử chạy bằng command
        subprocess.Popen(["code"])
        sleep(5)
        return True
    except Exception as e:
        print(f"[control_jsx] ERROR: Không khởi động được VS Code: {e}")
        return False


def focus_window(window_title_pattern):
    """Focus vào window theo pattern"""
    for w in Desktop(backend="uia").windows():
        if window_title_pattern.lower() in w.window_text().lower():
            try:
                w.set_focus()
                sleep(0.5)
                return True
            except Exception:
                pass
    return False


def run_jsx_in_premiere(jsx_path, premiere_version="2022", wait_seconds=10):
    """
    Tự động chạy JSX script trong Premiere Pro thông qua VS Code ExtendScript

    Args:
        jsx_path: Đường dẫn tuyệt đối đến file .jsx
        premiere_version: Phiên bản Premiere Pro (2022, 2023, 2024, 2025)
        wait_seconds: Thời gian chờ script chạy xong

    Returns:
        bool: True nếu thành công
    """

    print(f"\n[control_jsx] === Chạy JSX: {os.path.basename(jsx_path)} ===")

    # 1. Đảm bảo Premiere đang chạy
    if not ensure_premiere_running():
        return False

    # 2. Đảm bảo VS Code đang chạy
    if not ensure_vscode_running():
        return False

    # 3. Focus VS Code
    print("[control_jsx] Focus VS Code...")
    if not focus_window("Visual Studio Code"):
        print("[control_jsx] ERROR: Không focus được VS Code")
        return False

    sleep(1)

    # 4. Mở file JSX trong VS Code (Ctrl+O)
    print(f"[control_jsx] Mở file: {jsx_path}")
    send_keys('^o')  # Ctrl+O
    sleep(1)

    # Paste đường dẫn file
    copy_paste(jsx_path)
    sleep(0.5)
    send_keys('{ENTER}')
    sleep(1)

    # 5. Chạy ExtendScript (Ctrl+Shift+P)
    print("[control_jsx] Chạy ExtendScript...")
    send_keys('^+p')  # Ctrl+Shift+P
    sleep(1)

    # Gõ command
    copy_paste("ExtendScript: Evaluate Script in Attached Host")
    sleep(0.5)
    send_keys('{ENTER}')
    sleep(1)

    # Chọn Premiere Pro
    premiere_text = f"Adobe Premiere Pro {premiere_version}"
    copy_paste(premiere_text)
    sleep(0.5)
    send_keys('{ENTER}')
    sleep(1)

    print(f"[control_jsx] Script đang chạy... (chờ {wait_seconds}s)")
    sleep(wait_seconds)

    # 6. Focus lại Premiere để xem kết quả
    print("[control_jsx] Focus Premiere Pro...")
    focus_window("Adobe Premiere Pro")
    sleep(1)

    # Spam ESC để đóng các popup nếu có
    for _ in range(5):
        send_keys('{ESC}')
        sleep(0.2)

    print("[control_jsx] ✓ Hoàn thành!")
    return True


def run_jsx_batch(jsx_files, premiere_version="2022", wait_per_script=10):
    """
    Chạy nhiều JSX scripts liên tiếp

    Args:
        jsx_files: List các đường dẫn JSX
        premiere_version: Phiên bản Premiere
        wait_per_script: Thời gian chờ mỗi script

    Returns:
        int: Số scripts chạy thành công
    """
    success_count = 0

    for jsx_path in jsx_files:
        if run_jsx_in_premiere(jsx_path, premiere_version, wait_per_script):
            success_count += 1
        else:
            print(f"[control_jsx] FAILED: {jsx_path}")
            break  # Dừng nếu có lỗi

    return success_count


# Test function
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python control_jsx.py <jsx_file_path> [premiere_version]")
        sys.exit(1)

    jsx_path = sys.argv[1]
    version = sys.argv[2] if len(sys.argv) > 2 else "2022"

    success = run_jsx_in_premiere(jsx_path, version)
    sys.exit(0 if success else 1)
