# -*- coding: UTF8 -*-
import re
import os
import sys
import time
import datetime
import asyncio
import hashlib
import subprocess
import requests
import shlex
import ssl
from zlib import crc32
from pathlib import Path
from datetime import timedelta
from fastapi.responses import StreamingResponse
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import web_headers, web_proxies

"""
替换图片URL前缀
"""
def replace_images_url(old_list, prefix):
    prefix = prefix.rstrip('/')
    new_list = []
    for image in old_list:
        if not image.startswith(('https://', 'http://')):
            # 如果是相对路径，添加前缀
            new_image = f"{prefix}{image}"
            logger.debug(f"new_image: {new_image}")
        else:
            # 如果已经是完整URL，保持不变
            new_image = image
            logger.debug(f"old_image: {new_image}")
        new_list.append(new_image)
    return new_list

def get_javbus_title(code_name):
    try:
        if len(code_name) == 0:
            logger.error(f"Not Code")
            return None
        code_name = code_name.upper() if code_name.find('-') > 0 else code_name.lower()
        baseurl = 'https://www.javbus.com/'
        code_url = baseurl + code_name
        logger.info(f"code_url: {code_url}")
        if web_proxies.get('https','') == '':
            response = requests.get(code_url, headers=web_headers, allow_redirects=False, timeout=10, verify=False)
        else:
            response = requests.get(code_url, headers=web_headers, proxies=web_proxies, allow_redirects=False, timeout=10, verify=False)
        response.encoding="UTF-8"
        response = response.text
        # logger.debug(f"response: {response}")
        # logger.debug(f"response.find('Page Not Found'): {response.find('Page Not Found')}")
        if response.find('Page Not Found') > 0:
            logger.error(f"404 Page Not Found")
            return None
        
        # # temp_log
        # log_message = f"{datetime.datetime.now()} {code_name} - response: {response}\n"
        # with open(f'jav_{code_name}_log.txt', 'w') as log_file:
        #     log_file.write(log_message)

        code_title=re.findall('<h3>(.+)</h3>',response)[0].strip()
        logger.debug(f"title: {code_title}")

        if code_title.lower().find(code_name.lower()) == -1:
            logger.error(f"title is None: {code_title}")
            return None

        date=re.findall('發行日期:</span>(.+)</p>',response)
        logger.debug(f"date: {date}")

        pattern = r'<a href="https://www.javbus.com/studio/\w+">(.*?)</a>'
        studio = re.findall(pattern,response)
        logger.debug(f"studio: {studio}")

        pattern = r'<a href="https://www.javbus.com/director/\w+">(.*?)</a>'
        director = re.findall(pattern,response)
        logger.debug(f"director: {director}")

        pattern = r'<a href="https://www.javbus.com/series/\w+">(.*?)</a>'
        series = re.findall(pattern,response)
        logger.debug(f"series: {series}")

        pattern = r'<a href="https://www.javbus.com/genre/\w+">(.*?)</a></label></span>'
        genre = re.findall(pattern,response)
        logger.debug(f"genre: {genre}")

        pattern = r'<a href="https://www.javbus.com/star/\w+">([^<]+)</a>'
        actors = re.findall(pattern,response)
        logger.debug(f"actors: {actors}")

        pattern = r'<a class="sample-box" href="([^"]+)">'
        images = re.findall(pattern,response)
        logger.debug(f"old images: {images}")
        images = replace_images_url(images, baseurl)
        logger.debug(f"new images: {images}")

        code_info = {
            "code": code_name,
            "name": code_title,
            "date": date[0].strip() if len(date) > 0 else '',
            "studio": studio[0].strip() if len(studio) > 0 else '',
            "director": director[0].strip() if len(director) > 0 else '',
            "series": series[0].strip() if len(series) > 0 else '',
            "genre": genre if len(genre) > 0 else [],
            "websites": [code_url],
            "actors": actors if len(actors) > 0 else [],
            "images": images if len(images) > 0 else [],
            "score": 0,
        }

        if code_title.lower().find(code_name.lower()) != -1:
            return code_info
        else:
            logger.error(f"title is None: {code_title}")
            return None
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return None

def get_123av_title(code_name):
    try:
        if len(code_name) == 0:
            logger.error(f"Not Code")
            return None
        code_name = code_name.upper() if code_name.find('-') > 0 else code_name.lower()
        baseurl = 'https://123av.com/ja/v/'
        code_url = baseurl + code_name
        logger.info(f"code_url: {code_url}")
        if web_proxies.get('https','') == '':
            response = requests.get(code_url, headers=web_headers, allow_redirects=False, timeout=10, verify=False)
        else:
            response = requests.get(code_url, headers=web_headers, proxies=web_proxies, allow_redirects=False, timeout=10, verify=False)
        response.encoding="UTF-8"
        response = response.text
        # logger.debug(f"response: {response}")
        # logger.debug(f"response.find('Page Not Found'): {response.find('Page Not Found')}")
        if response.find('Page Not Found') > 0:
            logger.error(f"404 Page Not Found")
            return None
        
        # temp_log
        log_message = f"{datetime.datetime.now()} {code_name} - response: {response}\n"
        with open(f'123_{code_name}_log.txt', 'w') as log_file:
            log_file.write(log_message)

        code_title=re.findall('<h1>(.+)</h1>',response)[0].strip().replace(' - 123AV','').replace('オンライン視聴, , ','').replace('オンライン視聴, ', '')
        # code_title=re.findall('<title>(.+)</title>',response)[0].strip().replace(' - 123AV','').replace('オンライン視聴, , ','').replace('オンライン視聴, ', '')
        logger.debug(f"title: {code_title}")
        
        if code_title.lower().find(code_name.lower()) == -1:
            logger.error(f"title is None: {code_title}")
            return None

        date=re.findall('リリース日:</span>(.+)</p>',response)
        logger.debug(f"date: {date}")

        pattern = r'<a href="https://www.123av.com/studio/\w+">(.*?)</a>'
        studio = re.findall(pattern,response)
        logger.debug(f"studio: {studio}")

        pattern = r'<a href="https://www.123av.com/director/\w+">(.*?)</a>'
        director = re.findall(pattern,response)
        logger.debug(f"director: {director}")

        pattern = r'<a href="https://www.123av.com/series/\w+">(.*?)</a>'
        series = re.findall(pattern,response)
        logger.debug(f"series: {series}")

        pattern = r'<a href="https://www.123av.com/genre/\w+">(.*?)</a></label></span>'
        genre = re.findall(pattern,response)
        logger.debug(f"genre: {genre}")

        pattern = r'<a href="https://www.123av.com/star/\w+">([^<]+)</a>'
        actors = re.findall(pattern,response)
        logger.debug(f"actors: {actors}")

        pattern = r'<a class="sample-box" href="([^"]+)">'
        images = re.findall(pattern,response)
        logger.debug(f"old images: {images}")
        images = replace_images_url(images, baseurl)
        logger.debug(f"new images: {images}")

        code_info = {
            "code": code_name,
            "name": code_title,
            "date": date[0].strip() if len(date) > 0 else '',
            "studio": studio[0].strip() if len(studio) > 0 else '',
            "director": director[0].strip() if len(director) > 0 else '',
            "series": series[0].strip() if len(series) > 0 else '',
            "genre": genre if len(genre) > 0 else [],
            "websites": [code_url],
            "actors": actors if len(actors) > 0 else [],
            "images": images if len(images) > 0 else [],
            "score": 0,
        }

        if code_title.lower().find(code_name.lower()) != -1:
            return code_info
        else:
            logger.error(f"title is None: {code_title}")
            return None
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return None
