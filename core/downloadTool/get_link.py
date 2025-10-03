"""YouTube link gathering utilities (improved).

Tính năng:
 - Giữ nguyên thứ tự keyword.
 - Logging rõ ràng.
 - Bắt lỗi từng keyword, không dừng toàn bộ.
 - Chuẩn hoá link.
 - Giới hạn số video / keyword (max_per_keyword).
 - Lọc theo thời lượng tối đa (max_minutes) nếu cung cấp.
 - Lọc theo thời lượng tối thiểu (min_minutes) nếu cung cấp.
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



# def get_dl_link_image(driver, keyword, num_of_image=10):
#     #find in google image
#     #mở to cửa sổ trình duyệt
#     driver.maximize_window()

#     search_url = f"https://www.google.com/search?tbm=isch&q={keyword}"
#     driver.get(search_url)
#     driver.implicitly_wait(10)
#     sleep(4)

#     actions = webdriver.ActionChains(driver)
#     body = driver.find_element(By.TAG_NAME, "body")
#     actions.move_to_element_with_offset(body, 50, 50).click().perform()
#     sleep(5)

#     send_keys('{LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT} {LEFT}')
#     image_links = []
#     #lấy link ảnh: thẻ a, rel = "noopener", target="_blank"
#     for i in range(num_of_image):
#         image_element = driver.find_elements(By.XPATH, '//a[@rel="noopener" and @target="_blank"]')[0]
#         img_tag = image_element.find_element(By.TAG_NAME, 'img')
#         img_src = img_tag.get_attribute('src')
#         image_links.append(img_src)
#         send_keys('{RIGHT}')
#         sleep(0.5)
#     return image_links

def get_links_main(
    keywords_file,
    output_txt,
    project_name=None,
    headless=False,
    max_per_keyword: int = 2,
    max_minutes: Optional[int] = None,
    min_minutes: Optional[int] = None,
):
    print("[get_link] === START get_links_main ===")
    print(f"[get_link] keywords_file = {keywords_file}")
    print(f"[get_link] output_txt    = {output_txt}")
    if project_name:
        print(f"[get_link] project_name  = {project_name}")

    keywords = read_keywords_from_file(keywords_file)
    if not keywords:
        print("[get_link] No keywords found -> abort.")
        return

    driver = init_driver(headless=headless)
    txt_name = output_txt
    stt = 0
    num_vd = 0
    # clear file at start
    try:
        with open(txt_name, 'w', encoding='utf-8') as f:
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
            print(f"[get_link] ERROR collecting links for '{keyword}': {e}")
            video_links = []

        stt += 1
        try:
            with open(txt_name, 'a', encoding='utf-8') as f:
                f.write(f"{stt} {keyword}\n")
                for link in video_links:
                    num_vd += 1
                    f.write(f"{link}\n")
        except Exception as e:
            print(f"[get_link] ERROR writing links for '{keyword}': {e}")
        # nhỏ delay để tránh bị chặn (có thể điều chỉnh thấp hơn nếu cần)
        sleep(1.0)

    print(f"[get_link] TOTAL video links written: {num_vd}")
    close_driver(driver)
    print("[get_link] === END get_links_main ===")


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