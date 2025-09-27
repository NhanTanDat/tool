#using selenium to download video and image  by search keyword
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

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
    sleep(5)
    #get 10 video link
    video_elements = driver.find_elements(By.ID, 'video-title')[:10]
    video_links = []
    for elem in video_elements:
        #get attribute href if the title text include keyword, else pass
        href = elem.get_attribute('href')
        if 'start_radio=1' in href:
            href = href.split('&start_radio=1')[0]
        video_links.append(href)
            
    print(f"Found {len(video_links)} video links for keyword: {keyword}")
    return video_links



# def get_dl_link_image(driver, keyword, num_of_image=10):
#     #find in google image
#     search_url = f"https://www.google.com/search?tbm=isch&q={keyword}"
#     driver.get(search_url)
#     driver.implicitly_wait(10)
#     sleep(10)
#     num = 0
#     image_links = []
#     #find  div have id="center_col" and role = "main"
#     images_group = driver.find_elements(By.XPATH, "//div[@id='center_col' and @role='main']")[0]
#     if images_group:
            
#         while num < num_of_image:
#             #find all by  tag a, extract image url starting from "imgurl ="
#             image_tags = images_group.find_elements(By.TAG_NAME, 'a')
#             for tag in image_tags:
#                 href = tag.get_attribute('href')
#                 if href and 'imgurl=' in href:
#                     start_index = href.index('imgurl=') + len('imgurl=')
#                     end_index = href.index('&', start_index)
#                     image_url = href[start_index:end_index]
#                     #decode url
#                     image_url = image_url.replace('%3A', ':').replace('%2F', '/').replace('%3F', '?').replace('%3D', '=').replace('%26', '&')
#                     print(f"Image URL: {image_url}")
#                     image_links.append(image_url)
#                     num += 1
#                     if num >= num_of_image:
#                         break
#     return image_links

def get_links_main(keywords_file, output_txt):
    driver = init_driver()
    keywords = read_keywords_from_file(keywords_file)
    txt_name = output_txt
    stt = 0
    num_vd = 0
    #save to  txt file
    with open(txt_name, 'a') as f:
        for keyword in keywords:

            f.write(f"{stt}")
            f.write(" ")
            f.write(f"{keyword}\n")
            video_links = get_dl_link_video(driver, keyword)
            # image_links = get_dl_link_image(driver, keyword)
            print(f"Keyword: {keyword}")
            print("Video Links:")
            stt += 1
            for link in video_links:
                num_vd += 1
                f.write(f"{link}\n")
                print(link)
            # print("Image Links:")
            # for link in image_links:
                # print(link)
    print(f"Total Video Links Downloaded: {num_vd}")
    close_driver(driver)


if __name__ == "__main__":
    keywords_file = "core/download Tool/output.txt"
    output_txt = "core/download Tool/dl_links.txt"
    get_links_main(keywords_file, output_txt)