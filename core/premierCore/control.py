from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from time import sleep
import pyperclip
import os


def copy_paste(path):
    '''function that change the download path of YT Downloader'''
    #giả lập thay tác ctrl + c bằng các lưu
    pyperclip.copy(path)
    send_keys('^v')


def run_jsx_in_vscode(jsx_file_path, premiere_version="Adobe Premiere Pro 2022"):
    """
    Tự động chạy file JSX trong VS Code với ExtendScript Debugger.

    Args:
        jsx_file_path: Đường dẫn đầy đủ đến file .jsx
        premiere_version: Tên version Premiere (default: "Adobe Premiere Pro 2022")

    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    try:
        # Tìm và focus VS Code
        vscode_found = False
        for w in Desktop(backend="uia").windows():
            if "Visual Studio Code" in w.window_text():
                w.set_focus()
                vscode_found = True
                break

        if not vscode_found:
            print("ERROR: VS Code không đang chạy")
            return False

        sleep(0.3)

        # Mở file JSX bằng Ctrl+P (Quick Open)
        send_keys('^p')
        sleep(0.3)

        # Paste đường dẫn file
        pyperclip.copy(jsx_file_path)
        send_keys('^v')
        sleep(0.3)
        send_keys('{ENTER}')
        sleep(0.5)

        # Chạy lệnh ExtendScript: Evaluate Script in Attached Host
        send_keys('^+p')  # Command Palette
        sleep(0.3)

        pyperclip.copy('ExtendScript: Evaluate Script in Attached Host')
        send_keys('^v')
        sleep(0.3)
        send_keys('{ENTER}')
        sleep(0.5)

        # Chọn Premiere Pro
        pyperclip.copy(premiere_version)
        send_keys('^v')
        sleep(0.3)
        send_keys('{ENTER}')

        print(f"✓ Đã gửi lệnh chạy: {jsx_file_path}")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def focus_premiere():
    """Focus vào cửa sổ Premiere Pro"""
    for w in Desktop(backend="uia").windows():
        if "Adobe Premiere Pro" in w.window_text():
            w.set_focus()
            return True
    return False


#hàm này thực hiện mở vscode và chạy file runAll.jsx tự động
def run_premier_script(premier_path, project_path, idx):
    os.system('taskkill /IM "Adobe Premiere Pro.exe" /F')
    app = None
    for w in Desktop(backend="uia").windows():
        if "Adobe Premiere Pro" in w.window_text():
            app = Application(backend="uia").connect(title_re=".*Adobe Premiere Pro.*")
            w.set_focus()
            send_keys('^s')
            break
    if not app:
        print("Premiere Pro is not running.")
        app = Application(backend="uia").start(
            r'"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"',
        )
    sleep(10)  # Chờ một chút để Premiere Pro khởi động hoàn toàn
    send_keys('^o')
    sleep(2)  # Chờ một chút để cửa sổ mở project xuất hiện
    #gõ đường dẫn project
    copy_paste(project_path)
    send_keys('{ENTER}')
    sleep(5)  # Chờ một chút để project được mởpremierepro
    send_keys('{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}')
    sleep(5)
    send_keys('{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}')
    sleep(2)
    #tab sang cửa sổ vscode, tab cho đến khi thấy cửa sổ vscode hiện lên
    for w in Desktop(backend="uia").windows():
        if "Visual Studio Code" in w.window_text():
            w.set_focus()
            break


    #bấm ctrl+e mở go to file
    send_keys('^e')
    send_keys('runAll.jsx')
    send_keys('{ENTER}')

    send_keys('^+p')
    sleep(1)
    copy_paste('ExtendScript: Evaluate Script in Attached Host')
    sleep(0.5)
    send_keys('{ENTER}')  # Nhấn Enter để chọn lệnh
    sleep(0.5)
    copy_paste('Adobe Premiere Pro 2022')
    sleep(0.5)
    send_keys('{ENTER}')  # Nhấn Enter để chọn lệnh

    #quay lại cửa sổ premier
    for w in Desktop(backend="uia").windows():
        if "Adobe Premiere Pro" in w.window_text():
            w.set_focus()
            break

    #liên tục spam nút esc để tắt hết các popup
    while True:
        #nếu premier đã bị tắt thì thoát khỏi vòng lặp
        if not app.is_process_running():
            print("Premiere Pro has been closed.")
            break
        try:
            send_keys('{ENTER}')
            sleep(5)
        except Exception as e:
            print("No more popups to close.")
            break
    print("Script execution completed.")

    #dọn dẹp tài nguyên
    for w in Desktop(backend="uia").windows():
        if "Visual Studio Code" in w.window_text():
            w.set_focus()
            break

    #đóng session premier
    if app:
        app.close()
        print("Premiere Pro session closed.")

#test
if __name__ == "__main__":
    premier_path = r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"
    project_path = r"C:\Users\phamp\Downloads\Copied_3638\Copied_3638\3638.prproj"
    run_premier_script(premier_path, project_path, 1)