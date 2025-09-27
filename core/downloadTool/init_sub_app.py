from pywinauto import Application, Desktop
from time import sleep


def init_dlp(yt_dlp_path, title_re):
    '''function that start the YT Downloader application and return the app and its main dialog'''
    # 1) Đường dẫn tuyệt đối tới file thực thi của YT Downloader
    app = Application(backend='uia').start(yt_dlp_path)
    dlg = Desktop(backend='uia').window(title_re=title_re)
    dlg.wait('visible', timeout=20)
    dlg.wait('ready', timeout=20)
    dlg.set_focus()
    sleep(1)  # Chờ GUI ổn định
    return app, dlg