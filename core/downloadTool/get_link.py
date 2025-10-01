"""YouTube link gathering utilities (improved).

Fixes / Enhancements:
 - Giữ nguyên thứ tự keyword (trước đây dùng set() làm mất thứ tự & có thể gây hiểu nhầm).
 - Thêm logging rõ ràng cho từng bước để kiểm tra vì sao chỉ chạy được dòng đầu tiên.
 - Thêm try/except per-keyword để nếu 1 keyword lỗi không dừng toàn bộ vòng lặp.
 - Làm sạch & chuẩn hoá link (loại bỏ tham số thừa, chuyển /watch?v= dạng đầy đủ nếu cần).
 - Giới hạn kết quả & loại bỏ trùng link.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from typing import List
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


def get_dl_link_video(driver, keyword: str, max_results: int = 2) -> List[str]:
    search_url = f"https://www.youtube.com/results?search_query={keyword}".replace(' ', '+')
    print(f"[get_link] Navigate: {search_url}")
    driver.get(search_url)
    # Wait for video title elements
    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'video-title')))
    except Exception as e:
        print(f"[get_link] WARNING: Timeout loading results for '{keyword}': {e}")
    # Scroll once to encourage lazy load
    try:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        sleep(1.2)
    except Exception as e:
        print(f"[get_link] Scroll error (ignored): {e}")

    elements = driver.find_elements(By.ID, 'video-title')
    links = []
    for el in elements[:max_results]:
        try:
            href = _clean_href(el.get_attribute('href'))
            if href and href.startswith('https://www.youtube.com/watch') and href not in links:
                links.append(href)
        except Exception:
            continue
    print(f"[get_link] Keyword '{keyword}' -> {len(links)} links")
    if not links:
        #add default link to avoid empty 
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

def get_links_main(keywords_file, output_txt, project_name=None, headless=False):
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
            video_links = get_dl_link_video(driver, keyword)
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