#using selenium to download video and image  by search keyword
from lib2to3.pgen2 import driver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys
import json

from time import sleep

def init_driver():
    #read chrome driver path from file
    driver  = webdriver.Chrome()
    return driver

def close_driver(driver):
    driver.quit()


def read_keywords_from_file(file_path):
    with open(file_path, 'r') as f:
        #read all line to list and strip \n, if line is empty, ignore, if keyword duplicate, ignore
        keywords = list(set([line.strip() for line in f if line.strip()]))
    return keywords


def get_dl_link_video(driver, keyword):
    #find in youtube
    search_url = f"https://www.youtube.com/results?search_query={keyword}"
    driver.get(search_url)
    driver.implicitly_wait(10)
    # Wait until at least one video element is present instead of using arbitrary sleep
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, 'video-title'))
        )
    except Exception as e:
        print(f"Timeout waiting for video elements: {e}")
    # Scroll once to load more results (YouTube lazy loads additional items on scroll)
    try:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        sleep(2)  # small wait for new elements to render
    except Exception as e:
        print(f"Scroll attempt failed (continuing): {e}")

    # get up all link
    video_elements = driver.find_elements(By.ID, 'video-title')[:20]  # limit to first 20 results
    video_links = []
    for elem in video_elements:
        #get attribute href if the title text include keyword, else pass
        href = elem.get_attribute('href')
        if 'start_radio=1' in href:
            href = href.split('&start_radio=1')[0]
        if '&pp=ygU' in href:
            href = href.split('&pp=ygU')[0]
        video_links.append(href)
            
    print(f"Found {len(video_links)} video links for keyword: {keyword}")
    return video_links



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

def get_links_main(keywords_file, output_txt):
    driver = init_driver()
    keywords = read_keywords_from_file(keywords_file)
    txt_name = output_txt
    txt_image = output_txt.replace('.txt', '_images.txt')
    stt = 0
    num_vd = 0
    #save to  txt file
    with open(txt_name, 'w') as f:
        f.write("")  # clear file
    with open(txt_image, 'w') as f:
        f.write("")  # clear file
    
    for keyword in keywords:
        video_links = get_dl_link_video(driver, keyword)
        # image_links = get_dl_link_image(driver, keyword)
        print(f"Keyword: {keyword}")
        print("Video Links:")
        stt += 1
        with open(txt_name, 'a') as f:
            f.write(f"{stt}")
            f.write(" ")
            f.write(f"{keyword}\n")
            for link in video_links:
                num_vd += 1
                f.write(f"{link}\n")
                print(link)
        # with open(txt_image, 'a') as f:
        #     f.write(f"{stt}")
        #     f.write(" ")
        #     f.write(f"{keyword}\n")
        #     for link in image_links:
        #         f.write(f"{link}\n")
        # print("Image Links:")
        # for link in image_links:
            # print(link)
    print(f"Total Video Links Downloaded: {num_vd}")
    close_driver(driver)


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