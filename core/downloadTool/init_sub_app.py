import psutil
from time import sleep
from pywinauto import Application, Desktop

def _pids_by_exe(exe_path):
    exe_lc = exe_path.lower()
    pids = []
    for p in psutil.process_iter(['exe']):
        try:
            ex = (p.info.get('exe') or '').lower()
            if ex == exe_lc:
                pids.append(p.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids

def _pick_main_window(cands, prefer_pids=None):
    """Chọn cửa sổ 'chính' khi còn nhiều ứng viên.
    Ưu tiên: visible & thuộc prefer_pids -> visible -> diện tích lớn nhất.
    """
    prefer_pids = set(prefer_pids or [])
    def rect_area(w):
        try:
            r = w.rectangle()
            return max(0, (r.right - r.left) * (r.bottom - r.top))
        except Exception:
            return 0

    # 1) visible + pid ưu tiên
    tier = [w for w in cands if w.is_visible() and getattr(w.element_info, 'process_id', None) in prefer_pids]
    if tier:
        return max(tier, key=rect_area)

    # 2) visible
    tier = [w for w in cands if w.is_visible()]
    if tier:
        return max(tier, key=rect_area)

    # 3) bất kỳ, chọn cái to nhất
    return max(cands, key=rect_area)

def init_dlp(yt_dlp_path, title_re, timeout=30):
    """Start/Connect YT Downloader và trả về (app, main_dlg) ổn định, tránh lỗi '2 elements match'."""
    # 1) Connect nếu đã chạy, nếu chưa thì start
    try:
        app = Application(backend='uia').connect(path=yt_dlp_path)
    except Exception:
        app = Application(backend='uia').start(f'"{yt_dlp_path}"')

    # 2) Lấy pid thuộc exe_path (đợi tối đa vài giây sau khi start)
    pids = []
    for _ in range(50):  # ~2.5s
        pids = _pids_by_exe(yt_dlp_path)
        if pids:
            break
        sleep(0.05)

    d = Desktop(backend='uia')

    # 3) Chờ xuất hiện ít nhất một top-level window khớp title_re
    cands = []
    for _ in range(int(timeout * 20)):  # bước 50ms -> timeout giây
        cands = d.windows(title_re=title_re,
                          control_type='Window',
                          top_level_only=True)
        if cands:
            break
        sleep(0.05)
    if not cands:
        raise TimeoutError(f"Không tìm thấy cửa sổ khớp '{title_re}' trong {timeout}s")

    # 4) Ưu tiên visible trước
    vis = [w for w in cands if w.is_visible()]
    if vis:
        cands = vis

    # 5) Nếu vẫn nhiều, chọn theo pid + diện tích
    dlg_item = _pick_main_window(cands, prefer_pids=pids)

    # 6) Chuẩn hoá về WindowSpecification theo handle
    dlg = d.window(handle=dlg_item.handle)

    # 7) Đợi sẵn sàng + focus
    dlg.wait('visible', timeout=timeout)
    dlg.wait('ready', timeout=timeout)
    try:
        dlg.set_focus()
    except Exception:
        pass  # đôi khi focus bị chặn bởi system toast/UAC

    sleep(0.5)  # ổn định UI nhẹ
    return app, dlg
