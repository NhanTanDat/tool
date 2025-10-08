from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from time import sleep
import pyperclip


def copy_paste(path):
    '''function that change the download path of YT Downloader'''
    #giả lập thay tác ctrl + c bằng các lưu
    pyperclip.copy(path)
    send_keys('^v')


#hàm này thực hiện mở vscode và chạy file runAll.jsx tự động
def run_premier_script(premier_path, project_path, idx):
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

    send_keys('^{F5}')  # Bấm F5 để chạy script
    sleep(0.5)

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

    #đóng session premier
    if app:
        app.close()
        print("Premiere Pro session closed.")

#test
if __name__ == "__main__":
    premier_path = r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"
    project_path = r"C:\Users\phamp\Downloads\Copied_3638\Copied_3638\3638.prproj"
    run_premier_script(premier_path, project_path, 1)