from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from contextlib import redirect_stdout
import pyperclip
from time import sleep
import os
import sys



#hàm này thực hiện mở vscode và chạy file runAll.jsx tự động
def run_premier_script(premier_path, project_path):
    # Mở Adobe Premiere Pro thông qua tìm kiếm trong start menu
    app = Application(backend="uia").start(
        r'"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"',
    )
    sleep(15)  # Chờ một chút để Premiere Pro khởi động hoàn toàn
    send_keys('^o')
    sleep(2)  # Chờ một chút để cửa sổ mở project xuất hiện
    #gõ đường dẫn project
    send_keys(project_path)
    send_keys('{ENTER}')
    sleep(10)  # Chờ một chút để project được mở hoàn toàn
    sleep(5)  # Chờ một chút để project được mởpremierepro
    send_keys('{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}')
    sleep(5)
    send_keys('{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}{ESC}')
    sleep(2)
    send_keys('%{TAB}') #quay lại vscode

    #bấm ctrl+e mở go to file
    send_keys('^e')
    send_keys('runAll.jsx')
    send_keys('{ENTER}')

    send_keys('^{F5}')  # Bấm F5 để chạy script
    sleep(5)
    send_keys('{ENTER}{ENTER}{ENTER}{ENTER}')
    send_keys('^z^z')

    #quay lại cửa sổ premier
    send_keys('%{TAB}')

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



#test
if __name__ == "__main__":
    premier_path = r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe"
    project_path = r"C:\Users\phamp\Downloads\Copied_3638\Copied_3638\3638.prproj"
    run_premier_script(premier_path, project_path)