"""YouTube/Google Images link gathering utilities (improved).

Tính năng:
 - Giữ nguyên thứ tự keyword.
 - Logging rõ ràng.
 - Bắt lỗi từng keyword, không dừng toàn bộ.
 - Chuẩn hoá link.
 - Giới hạn số video / keyword (max_per_keyword).
 - Lọc theo thời lượng tối đa (max_minutes) nếu cung cấp.
 - Lọc theo thời lượng tối thiểu (min_minutes) nếu cung cấp.

Luồng chính tách riêng:
 - get_links_main_video: Chỉ thu link video YouTube.
 - get_links_main_image: Chỉ thu link ảnh Google Images.
 - get_links_main: Giữ tương thích cũ, gọi lần lượt 2 luồng trên.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from typing import List, Optional
import re
import os
from pywinauto.keyboard import send_keys


def init_driver(headless: bool = False):
    opts = Options()
    if headless:
        opts.add_argument('--headless=new')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--lang=en-US')
    opts.add_argument('--disable-notifications')
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass


def read_keywords_from_file(file_path) -> List[str]:
    if not os.path.isfile(file_path):
        print(f"[get_link] Keywords file not found: {file_path}")
        return []
    ordered = []
    seen = set()
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # list_name.txt format expected: "<index> <keyword>" -> tách lấy phần sau index nếu phù hợp
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[0].isdigit():
                keyword = parts[1].strip()
            else:
                keyword = line
            if keyword and keyword not in seen:
                seen.add(keyword)
                ordered.append(keyword)
    print(f"[get_link] Loaded {len(ordered)} unique keywords (order preserved).")
    return ordered


def _clean_href(href: str) -> str:
    if not href:
        return ''
    if href.startswith('/watch'):  # relative path case
        href = 'https://www.youtube.com' + href
    # remove typical noise params
    cut_tokens = ['&pp=ygU', '&start_radio=1', '&list=']
    for token in cut_tokens:
        if token in href:
            href = href.split(token)[0]
    return href


def _parse_duration_to_seconds(txt: str) -> Optional[int]:
    if not txt:
        return None
    t = txt.strip().upper()
    if any(b in t for b in ['LIVE', 'TRỰC TIẾP', 'PREMIERE', 'UPCOMING']):
        return None
    parts = t.split(':')
    if not all(p.isdigit() for p in parts):
        return None
    if len(parts) == 2:
        m, s = parts
        return int(m)*60 + int(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h)*3600 + int(m)*60 + int(s)
    return None


def _parse_aria_duration(label: str) -> Optional[int]:
    """Parse aria-label like '1 hour, 56 minutes, 30 seconds' -> seconds."""
    if not label:
        return None
    text = label.lower()
    # quick reject for live-like labels
    if any(k in text for k in ['live', 'premiere', 'upcoming']):
        return None
    h = m = s = 0
    mh = re.search(r'(\d+)\s*hour', text)
    mm = re.search(r'(\d+)\s*minute', text)
    ms = re.search(r'(\d+)\s*second', text)
    if mh:
        h = int(mh.group(1))
    if mm:
        m = int(mm.group(1))
    if ms:
        s = int(ms.group(1))
    total = h*3600 + m*60 + s
    return total if total > 0 else None


def get_dl_link_video(
    driver,
    keyword: str,
    max_results: int,
    max_minutes: Optional[int] = None,
    min_minutes: Optional[int] = None,
    max_scrolls: int = 8,
) -> List[str]:
    search_url = f"https://www.youtube.com/results?search_query={keyword}".replace(' ', '+')
    print(f"[get_link] Navigate: {search_url}")
    driver.get(search_url)
    # Wait for video title elements
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'video-title')))
    except Exception as e:
        print(f"[get_link] WARNING: Timeout loading results for '{keyword}': {e}")
    want = max_results
    links: List[str] = []
    max_seconds = max_minutes * 60 if max_minutes else None
    min_seconds = min_minutes * 60 if min_minutes else None

    processed_ids = set()
    scroll_count = 0
    num_scroll = 6
    # Loop scroll until we have enough links or reach scroll cap
    while len(links) < want and scroll_count <= max_scrolls:
        try:
            elements = driver.find_elements(By.ID, 'video-title')
        except Exception:
            elements = []
        # process newly appeared elements
        for el in elements:
            if len(links) >= want:
                break
            try:
                vid_href_raw = el.get_attribute('href')
                href = _clean_href(vid_href_raw)
                if not href or href in links:
                    continue
                # generate a simple id (video id) to avoid re-processing
                vid_id = None
                if 'watch?v=' in href:
                    vid_id = href.split('watch?v=')[-1].split('&')[0]
                if vid_id and vid_id in processed_ids:
                    continue
                if vid_id:
                    processed_ids.add(vid_id)
                dur_seconds = None
                if max_seconds is not None or min_seconds is not None:
                    try:
                        container = el.find_element(By.XPATH, '(./ancestor::ytd-video-renderer | ./ancestor::ytd-rich-item-renderer)[1]')
                    except Exception:
                        container = None
                    if container is not None:
                        try:
                            time_nodes = container.find_elements(
                                By.XPATH,
                                ".//ytd-thumbnail-overlay-time-status-renderer//*[contains(@class,'badge-shape__text') or contains(@class,'yt-badge-shape__text')]"
                            )
                            for tn in time_nodes:
                                raw = (tn.text or '').strip()
                                if ':' in raw:
                                    dur_seconds = _parse_duration_to_seconds(raw)
                                    if dur_seconds is not None:
                                        break
                        except Exception:
                            pass
                        if dur_seconds is None:
                            try:
                                badge = container.find_element(By.XPATH, ".//ytd-thumbnail-overlay-time-status-renderer//badge-shape[@aria-label]")
                                aria = badge.get_attribute('aria-label') or ''
                                dur_seconds = _parse_aria_duration(aria)
                            except Exception:
                                pass
                    if dur_seconds is None:
                        continue
                    if max_seconds is not None and dur_seconds > max_seconds:
                        continue
                    if min_seconds is not None and dur_seconds < min_seconds:
                        continue
                links.append(href)
            except Exception:
                continue
        if len(links) >= want:
            break
        # Scroll further
        scroll_count += 1
        if(scroll_count > num_scroll):
            break
        try:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        except Exception as e:
            print(f"[get_link] Scroll exec error (ignored): {e}")
            break
        sleep(1.6 if scroll_count < 3 else 2.2)
    if len(links) < want:
        print(f"[get_link] Reached scroll limit ({scroll_count}/{max_scrolls}) with only {len(links)}/{want} links.")
    print(f"[get_link] Keyword '{keyword}' -> {len(links)} links (filtered)")
    if not links:
        # fallback 1 link mặc định để tránh rỗng hoàn toàn
        links.append("https://www.youtube.com/watch?v=WqQUvfsavO4")
    return links



def get_dl_link_image(driver, keyword, num_of_image=10):
    """Lấy danh sách link ảnh từ Google Images với các cải tiến:
    - Giữ thao tác phím RIGHT như bản gốc (di chuyển qua từng ảnh).
    - Loại bỏ ảnh có link bảo vệ: data:image/*, encrypted-tbn (thumbnail preview của Google).
    - Loại bỏ ảnh mờ / quá nhỏ theo kích thước hiển thị (naturalWidth/Height < 50).
    - Loại bỏ ảnh < 10KB nếu lấy được Content-Length (dùng requests nếu có, fallback bỏ qua kiểm tra này nếu không có).
    - Tự động scroll nếu chưa thu đủ số ảnh.
    """
    try:
        driver.maximize_window()
    except Exception:
        pass

    search_url = f"https://www.google.com/search?tbm=isch&q={keyword}".replace(' ', '+')
    driver.get(search_url)
    driver.implicitly_wait(10)
    sleep(3)

    # Focus để điều khiển phím
    try:
        actions = webdriver.ActionChains(driver)
        body = driver.find_element(By.TAG_NAME, "body")
        actions.move_to_element_with_offset(body, 50, 50).click().perform()
    except Exception:
        pass
    sleep(1)

    # Đưa selection về bên trái như logic cũ
    send_keys('{LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT}')

    # Tham số
    MIN_DIMENSION = 50  # tránh icon nhỏ / blur
    MIN_FILE_KB = 10
    MAX_SCROLL_ATTEMPTS = 20
    collected = []
    seen = set()
    scroll_attempts = 0
    right_moves = 0

    # Thử import requests để kiểm tra Content-Length
    try:
        import requests  # type: ignore
        _has_requests = True
    except Exception:
        _has_requests = False

    def is_protected(src: str) -> bool:
        if not src:
            return True
        if src.startswith('data:image/') or 'static.' in src or 'resizing.' in src:  # tránh ảnh tĩnh (icon, logo)
            return True
        if 'encrypted' in src:  # thumbnail preview
            return True
        return False

    def file_size_ok(src: str) -> bool:
        if not _has_requests:
            return True  # không kiểm tra nếu thiếu thư viện
        if not src.lower().startswith(('http://', 'https://')):
            return True
        try:
            head = requests.head(src, timeout=5, allow_redirects=True)
            cl = head.headers.get('Content-Length')
            if cl and cl.isdigit():
                return int(cl) >= MIN_FILE_KB * 1024
        except Exception:
            return True  # nếu lỗi HEAD thì bỏ qua lọc này
        return True

    while len(collected) < num_of_image and scroll_attempts <= MAX_SCROLL_ATTEMPTS:
        try:
            anchors = driver.find_elements(By.XPATH, '//a[@rel="noopener" and @target="_blank"]')
        except Exception:
            anchors = []
        if not anchors:
            # nếu không còn anchor, scroll thử
            scroll_attempts += 1
            try:
                driver.execute_script('window.scrollBy(0, document.body.scrollHeight);')
            except Exception:
                break
            sleep(1.2)
            continue

        # Lấy anchor đầu tiên (giống logic gốc) - giả định phím RIGHT sẽ thay đổi "focus" ảnh hiển thị đầu danh sách / vùng hiển thị
        try:
            image_element = anchors[1]
            img_tag = image_element.find_elements(By.TAG_NAME, 'img')[0]
            img_src = img_tag.get_attribute('src') or ''
        except Exception:
            img_src = ''

        accept = True
        if not img_src:
            accept = False
        if accept and is_protected(img_src):
            accept = False

        # Kiểm tra dimension
        if accept:
            try:
                w = int(img_tag.get_attribute('naturalWidth') or 0)
                h = int(img_tag.get_attribute('naturalHeight') or 0)
            except Exception:
                w = h = 0
            if w < MIN_DIMENSION or h < MIN_DIMENSION:
                accept = False

        # Kiểm tra kích thước file HEAD (nếu có)
        if accept and not file_size_ok(img_src):
            accept = False

        if accept and img_src not in seen:
            seen.add(img_src)
            collected.append(img_src)

        # Di chuyển sang ảnh kế (giữ nguyên thao tác RIGHT như yêu cầu)
        send_keys('{RIGHT}')
        right_moves += 1
        sleep(0.45)

        # Thỉnh thoảng scroll để load thêm (ví dụ mỗi 8 lần di chuyển)
        if len(collected) < num_of_image and right_moves % 8 == 0:
            scroll_attempts += 1
            try:
                driver.execute_script('window.scrollBy(0, document.body.scrollHeight);')
            except Exception:
                break
            sleep(1.0 if scroll_attempts < 5 else 1.6)

    return collected[:num_of_image]

def get_links_main_video(
    keywords_file,
    output_txt,
    project_name=None,
    headless=False,
    max_per_keyword: int = 2,
    max_minutes: Optional[int] = None,
    min_minutes: Optional[int] = None,
):
    """Thu link video theo từng keyword và ghi ra output_txt.

    Định dạng file:
    <stt> <keyword>
    <link 1>
    <link 2>
    ...
    """
    print("[get_link] === START get_links_main_video ===")
    print(f"[get_link] keywords_file = {keywords_file}")
    print(f"[get_link] output_txt    = {output_txt}")
    if project_name:
        print(f"[get_link] project_name  = {project_name}")

    keywords = read_keywords_from_file(keywords_file)
    if not keywords:
        print("[get_link] No keywords found -> abort.")
        return

    driver = init_driver(headless=headless)
    stt = 0
    num_vd = 0
    # clear file at start
    try:
        with open(output_txt, 'w', encoding='utf-8') as f:
            f.write('')
    except Exception as e:
        print(f"[get_link] ERROR: cannot clear output file: {e}")
        close_driver(driver)
        return

    for idx, keyword in enumerate(keywords, start=1):
        print(f"[get_link] --- ({idx}/{len(keywords)}) '{keyword}' ---")
        try:
            video_links = get_dl_link_video(
                driver,
                keyword,
                max_results=max_per_keyword,
                max_minutes=max_minutes,
                min_minutes=min_minutes,
            )
        except Exception as e:
            print(f"[get_link] ERROR collecting video links for '{keyword}': {e}")
            video_links = []

        stt += 1
        try:
            with open(output_txt, 'a', encoding='utf-8') as f:
                f.write(f"{stt} {keyword}\n")
                for link in video_links:
                    num_vd += 1
                    f.write(f"{link}\n")
        except Exception as e:
            print(f"[get_link] ERROR writing video links for '{keyword}': {e}")
        sleep(1.0)

    print(f"[get_link] TOTAL video links written: {num_vd}")
    close_driver(driver)
    print("[get_link] === END get_links_main_video ===")


def get_links_main_image(
    keywords_file,
    output_txt,
    project_name=None,
    headless=False,
    images_per_keyword: int = 10,
):
    """Thu link ảnh theo từng keyword và ghi ra output_txt.

    Lưu ý: output_txt là đường dẫn file ảnh (vd: dl_links_image.txt). Hàm này chỉ ghi ảnh.

    Định dạng file:
    <stt> <keyword>
    <link ảnh 1>
    <link ảnh 2>
    ...
    """
    print("[get_link] === START get_links_main_image ===")
    print(f"[get_link] keywords_file = {keywords_file}")
    print(f"[get_link] output_txt    = {output_txt}")
    if project_name:
        print(f"[get_link] project_name  = {project_name}")

    keywords = read_keywords_from_file(keywords_file)
    if not keywords:
        print("[get_link] No keywords found -> abort.")
        return

    driver = init_driver(headless=headless)
    stt = 0
    # clear file at start
    try:
        with open(output_txt, 'w', encoding='utf-8') as f:
            f.write('')
    except Exception as e:
        print(f"[get_link] ERROR: cannot clear output file: {e}")
        close_driver(driver)
        return

    for idx, keyword in enumerate(keywords, start=1):
        print(f"[get_link] --- ({idx}/{len(keywords)}) '{keyword}' ---")
        try:
            img_count = images_per_keyword if images_per_keyword and images_per_keyword > 0 else 10
            image_links = get_dl_link_image(driver, keyword, num_of_image=img_count)
        except Exception as e:
            print(f"[get_link] ERROR collecting image links for '{keyword}': {e}")
            image_links = []

        stt += 1
        try:
            with open(output_txt, 'a', encoding='utf-8') as f:
                f.write(f"{stt} {keyword}\n")
                for link in image_links:
                    f.write(f"{link}\n")
        except Exception as e:
            print(f"[get_link] ERROR writing image links for '{keyword}': {e}")
        sleep(1.0)

    close_driver(driver)
    print("[get_link] === END get_links_main_image ===")

def get_links_main(
    keywords_file,
    output_txt,
    project_name=None,
    headless=False,
    max_per_keyword: int = 2,
    max_minutes: Optional[int] = None,
    min_minutes: Optional[int] = None,
    images_per_keyword: int = 10,
):
    """Giữ tương thích cũ: chạy cả video và ảnh.

    - Video -> ghi vào output_txt.
    - Ảnh  -> ghi vào output_txt với hậu tố `_image.txt` nếu tên file kết thúc bằng .txt,
              ngược lại thêm hậu tố `_image`.
    """
    print("[get_link] === START get_links_main (compat) ===")
    # 1) Video
    get_links_main_video(
        keywords_file=keywords_file,
        output_txt=output_txt,
        project_name=project_name,
        headless=headless,
        max_per_keyword=max_per_keyword,
        max_minutes=max_minutes,
        min_minutes=min_minutes,
    )

    # 2) Image
    if isinstance(output_txt, str) and output_txt.lower().endswith('.txt'):
        img_output = output_txt[:-4] + '_image.txt'
    else:
        img_output = output_txt + '_image'
    get_links_main_image(
        keywords_file=keywords_file,
        output_txt=img_output,
        project_name=project_name,
        headless=headless,
        images_per_keyword=images_per_keyword,
    )
    print("[get_link] === END get_links_main (compat) ===")


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
    keywords_file = os.path.join(DATA_DIR, 'list_name.txt')
    output_txt = os.path.join(DATA_DIR, 'dl_links.txt')
    get_links_main(keywords_file, output_txt)