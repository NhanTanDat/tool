from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
from contextlib import redirect_stdout
import pyperclip
from time import sleep
import os
import sys

"""
Lý do lỗi ImportError (attempted relative import with no known parent package):
  Khi chạy file trực tiếp bằng:
      python core/downloadTool/down_by_yt.py
  thì __package__ = None nên cú pháp "from .folder_handle import ..." không hợp lệ.

Giải pháp: Thử relative import trước (khi chạy bằng -m), nếu thất bại sẽ:
  1. Thêm thư mục gốc dự án (root) vào sys.path
  2. Dùng absolute import: from core.downloadTool.folder_handle import ...

Khuyến nghị chạy dạng module:
    python -m core.downloadTool.down_by_yt
"""

try:  # khi chạy bằng: python -m core.downloadTool.down_by_yt
    from .folder_handle import create_folder  # type: ignore
    from .init_sub_app import init_dlp  # type: ignore
except ImportError:
    # Fallback khi chạy trực tiếp file .py
    THIS_FILE = os.path.abspath(__file__)
    DOWNLOAD_TOOL_DIR = os.path.dirname(THIS_FILE)               # .../core/downloadTool
    CORE_DIR = os.path.dirname(DOWNLOAD_TOOL_DIR)                # .../core
    ROOT_DIR = os.path.dirname(CORE_DIR)                         # project root
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    try:
        from core.downloadTool.folder_handle import create_folder  # type: ignore
        from core.downloadTool.init_sub_app import init_dlp  # type: ignore
    except ImportError as e:
        raise ImportError("Không thể import module phụ trợ. Kiểm tra cấu trúc thư mục. Chi tiết: " + str(e))

yt_dlp_path = r"C:\Program Files (x86)\YT Helper\YT Downloader\YTDownloader.exe"
TITLE_RE = ".*YT Downloader.*"
# ...existing code...
def _as_spec(ctrl):
    '''convert control to WindowSpecification'''
    d = Desktop(backend="uia")
    if hasattr(ctrl, "handle"):
        return d.window(handle=ctrl.handle)
    if hasattr(ctrl, "element_info"):
        return d.window(handle=ctrl.element_info.handle)
    return ctrl


def get_popup_coords(btn):
    """
    Tính tọa độ trung tâm của vùng 1/5 bên phải trên button (split popup).
    btn: control button (pywinauto element)
    return: (x_offset, y_offset) để dùng với btn.click_input(coords=...)
    """
    rect = btn.rectangle()
    width = rect.width()
    height = rect.height()

    # 1/5 bên phải
    popup_width = width // 5
    popup_left = width - popup_width
    popup_right = width

    # Tọa độ trung tâm của vùng popup (tương đối theo button)
    x_offset = popup_left + popup_width // 2
    y_offset = height // 2

    return (x_offset, y_offset)


def click_button(dlg, btn_spec, notInvoke = True):
    '''function that click the button'''
    btn_spec.wait("exists enabled visible", timeout=10)
    btn = btn_spec.wrapper_object()
    coors = get_popup_coords(btn)

    # Click/Invoke nút để mở menu
    if notInvoke:
        btn.click_input(coords=coors)
        return
    try:
        btn.invoke()
    except Exception:
        btn.click_input(coords=coors)


def open_popup_menu(dlg):
    '''function that open the popup menu by click the button have auto_id=32861'''
    # Tìm nút theo tree: Pane(auto_id=100) -> Button(auto_id=32861)
    pane = dlg.child_window(auto_id="100", control_type="Pane")
    btn_spec = pane.child_window(auto_id="32861", control_type="Button")
    click_button(dlg, btn_spec)
    popup = None
    
    d = Desktop(backend="uia")
    # Ghi nhận các menu/window hiện có trước khi click
    before_menus = {w.handle for w in d.windows(control_type="Menu", visible_only=False)}
    before_windows = {w.handle for w in d.windows(control_type="Window", visible_only=False)}
    for _ in range(200):  # ~10s
        # Ưu tiên control_type=Menu (UIA)
        for w in d.windows(control_type="Menu", visible_only=True):
            if w.handle not in before_menus:
                popup = w
                break
        if popup:
            break
        # Fallback: một số app hiện popup là Window trống
        for w in d.windows(control_type="Window", visible_only=True):
            if w.handle not in before_windows and not w.window_text():
                popup = w
                break
    if not popup:
        raise RuntimeError("Không tìm thấy popup menu sau khi click.")
    # Trả về WindowSpecification để dùng được print_control_identifiers
    return Desktop(backend="uia").window(handle=popup.handle)


def open_add_download_popup(dlg):
    '''function that open the Add Download popup by click the button have auto_id=32860'''
    pane = dlg.child_window(auto_id="1000", control_type="Pane")
    btn_spec = pane.child_window(auto_id="32779", control_type="Button")
    click_button(dlg, btn_spec, notInvoke=True)
    popup = None

    #lấy menu có  control_type = menu, visible_only = True, title = Context
    d = Desktop(backend="uia")
    for _ in range(200):  # ~10s
        for w in d.windows(control_type="Menu", visible_only=True, title="Context"):
            popup = w
            break
        if popup:
            break
    if not popup:
        raise RuntimeError("Không tìm thấy popup menu sau khi click.")
    return Desktop(backend="uia").window(handle=popup.handle)


def dump_menu(popup, filename="menu_identifiers.txt"):
    spec = _as_spec(popup)
    out_path = os.path.join(os.path.dirname(__file__), filename)
    with open(out_path, "w", encoding="utf-8") as f:
        with redirect_stdout(f):
            spec.print_control_identifiers()
    return out_path

def list_menu_items(popup):
    '''list all menu items in the popup menu'''
    spec = _as_spec(popup)
    items = []
    for it in spec.descendants(control_type="MenuItem"):
        try:
            if it.is_visible():
                txt = it.window_text()
                if txt:
                    items.append(txt)
        except Exception:
            pass
    # Fallback cho menu tuỳ biến
    if not items:
        for ct in ("ListItem", "Button"):
            for it in spec.descendants(control_type=ct):
                try:
                    if it.is_visible():
                        txt = it.window_text()
                        if txt:
                            items.append(txt)
                except Exception:
                    pass
    return items

def click_menu_item(popup, title):
    '''click menu item by its title'''
    spec = _as_spec(popup)
    item = spec.child_window(title=title, control_type="MenuItem")
    if not item.exists(timeout=0.5):
        item = spec.child_window(title=title, control_type="Button")
    item.wait("visible enabled", timeout=5)
    try:
        item.select()
    except Exception:
        item.wrapper_object().click_input()



def parse_links_from_txt(file_path):
    """Parse links definition file into {group: [links...]}

    Accepted header line formats:
      1) "<number><space><name>"  -> group name = remainder after first space
      2) Plain text (no https)     -> whole line is group name
    Link lines start with https:// and are appended to the current group.
    If a link appears before any group, a synthetic group is created.
    No character is forcibly removed from the beginning now.
    """
    groups = {}
    current = None
    synthetic_index = 1
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('https://'):
                if current is None:
                    current = f"group_{synthetic_index}"
                    groups[current] = []
                    synthetic_index += 1
                groups[current].append(line)
                continue
            # header line
            if ' ' in line and line.split(' ', 1)[0].isdigit():
                # split only once, keep full remainder
                _, remainder = line.split(' ', 1)
                name = remainder
            else:
                name = line
            name = "_".join(name.split())  # normalize spaces
            current = name
            groups.setdefault(current, [])
    return groups


def copy_paste(path):
    '''function that change the download path of YT Downloader'''
    #giả lập thay tác ctrl + c bằng các lưu
    pyperclip.copy(path)
    send_keys('^v')


def download_batch(dlg, links_dict, parent_folder, type = "mp4"):
    '''function that download a batch of links'''
    
    for name, links in links_dict.items():

        create_folder(parent_folder, name)

        popup = open_add_download_popup(dlg)
        click_menu_item(popup, "Batch Download...")
        text_links = ""
        for link in links:
            text_links += link + "\n\n"

        copy_paste(text_links)
        sleep(1)  # Chờ GUI ổn định sau mỗi lần paste
        num = 11
        if type == "mp3":
            num = 12
        i = 1
        while i <= num:
            send_keys('{TAB}')
            if(i == 4 ):
                if type == "mp4":
                    send_keys('{LEFT} {LEFT}')
                elif type == "mp3":
                    send_keys('{RIGHT} {RIGHT}')
            i += 1

        path = parent_folder + "\\" + name
        print(f"Changing download path to: {path}")
        copy_paste(path)
        send_keys('{ENTER}')  # Xác nhận thêm link


def download_all(dlg, links_dict, parent_folder):
    '''function that download all links in the links_dict'''
    popup = open_popup_menu(dlg)
    click_menu_item(popup, "Settings...")
    
    print(f"Changing download path to: {parent_folder}")
    copy_paste(parent_folder)
    send_keys('{ENTER}')

    for name, links in links_dict.items():
        num_links = len(links)
        # Thay copy path
        for link in links:
            copy_paste(link)
        sleep(0.5)  # Chờ GUI ổn định sau mỗi lần paste



    
def download_main(parent_folder, txt_name, _type = "mp4"):
    app, dlg = init_dlp(yt_dlp_path, TITLE_RE)
    #luuw lai control_identifiers
    # dump_menu(dlg, filename="dlp_menu.txt")
    try:
        send_keys('^p'); send_keys('^a'); send_keys('{DEL}')
    except Exception:
        pass
    links_dict = parse_links_from_txt(txt_name)
    if not links_dict:
        print(f"[WARN] No groups parsed from {txt_name}")
    download_batch(dlg, links_dict, parent_folder, type = _type)


    
if __name__ == "__main__":
    import os, sys
    THIS_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
    DATA_DIR = os.path.join(ROOT_DIR, 'data')
    if not os.path.isdir(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
    parent_folder = r"P:\ppp"  # chỉnh theo nhu cầu
    txt_name = os.path.join(DATA_DIR, 'dl_links.txt')
    download_main(parent_folder, txt_name, _type = "mp4")