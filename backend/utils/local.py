# -*- coding: UTF8 -*-
import re
import os
import sys
import cv2
import time
import ffmpeg
import asyncio
import hashlib
import subprocess
import shlex
import shutil
import ssl
from zlib import crc32
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.responses import StreamingResponse
from loguru import logger

from utils.db import get_db, get_db_app, format_query_for_db, convert_row_to_dict, format_datetime_fields
from config import BASE_DIR, DB_ENGINE, SSL_CERTFILE, SSL_KEYFILE
from config import TEMP_PATH, TEMP2_PATH, THUMBNAIL_TIME, THUMBNAIL_COMPRESSION, THUMBNAIL_CLEAR # THUMBNAIL
from config import APP_PAGE_LIMIT, SCAN_CODE, SCAN_EXT_LIST, PATH_FILTER_LIST # PATH

# 2FA
import pyotp
secret_key = 'UTVVO2XNK3PD525OFQUQCQYL5DRU5SOA'

# colorama
from colorama import Fore, Style, init
init(autoreset=True)
red = Fore.LIGHTRED_EX
blue = Fore.LIGHTBLUE_EX
green = Fore.LIGHTGREEN_EX
black = Fore.LIGHTBLACK_EX
magenta = Fore.LIGHTMAGENTA_EX
reset = Style.RESET_ALL

# ------------------------------------------------------

def is_mobile(request):
    user_agent = request.headers.get('User-Agent')
    # logger.debug(f"user_agent: {user_agent}")
    mobile_keywords = ['Android', 'webOS', 'iPhone', 'iPad', 'iPod', 'BlackBerry', 'IEMobile', 'Opera Mini']
    return any(keyword in user_agent for keyword in mobile_keywords)

def check_ssl_files(certfile, keyfile):
    if not os.path.exists(certfile):
        certfile = os.path.join(BASE_DIR, certfile)
    if not os.path.exists(keyfile):
        keyfile = os.path.join(BASE_DIR, keyfile)
    if os.path.exists(certfile) and os.path.exists(keyfile):
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(certfile=SSL_CERTFILE, keyfile=SSL_KEYFILE)
        except ssl.SSLError as e:
            logger.error(f"Failed to load SSL cert or key: {e}")
            certfile=''
            keyfile=''
        except FileNotFoundError as e:
            logger.info(f"SSL cert or key file not found: {e}")
            certfile=''
            keyfile=''
    else:
        certfile=''
        keyfile=''
    return certfile, keyfile

def check_2fa(pwd: str):
    """
    2FA校验
    """
    ## 无效PWD
    if len(pwd) != 6:
        logger.error(f"STATUS: 400 ERROR: Invalid pwd")
        return False

    ## 生成当前的2FA密码
    totp = pyotp.TOTP(secret_key)
    current_password = totp.now()
    logger.info(f"current_password: {green}{current_password} {black}pwd: {green}{pwd}")
    ## 密码校验
    if current_password != pwd:
        logger.error(f"STATUS: 400 ERROR: Password verification failed")
        return False
    logger.success(f"STATUS: 200 INFO: Password verification successful")
    return True

def duration_to_hms(duration):
    """
    时长转换为时分秒
    """
    td = timedelta(seconds=duration)
    remainder = td.total_seconds()  # 获取 时、分、秒
    hours, remainder = divmod(remainder, 3600)
    minutes, remainder = divmod(remainder, 60)
    seconds, milliseconds = divmod(remainder, 1)
    milliseconds = milliseconds * 1000  # 获取 毫秒
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{int(milliseconds):03d}"

def contains_alpha_numeric_symbol(text):
    """
    字符串含有英文/数字/_-
    """
    return re.match('^[A-Za-z0-9_-]*$', text) is not None

def contains_chinese(text):
    """
    字符串含有中文
    """
    return re.search(r'[\u4e00-\u9fff]', text) is not None

def delete_dir_file(dir_path):
    """
    递归删除文件夹下文件
    """
    if not THUMBNAIL_CLEAR:
        return
    if not os.path.exists(dir_path):
        return
    # 判断是不是一个文件路径，并且存在
    if os.path.isfile(dir_path) and os.path.exists(dir_path):
        # 删除文件
        try:
            os.remove(dir_path)
            logger.info(f"File {dir_path} remove successfully.")
        except OSError as e:
            logger.error(f"File remove Error: {e}")
    else:
        file_list = os.listdir(dir_path)
        for file_name in file_list:
            delete_dir_file(os.path.join(dir_path, file_name))
    # 递归删除空文件夹
    if os.path.exists(dir_path):
        os.rmdir(dir_path)

def delete_file(dir_path, id):
    """
    删除文件夹下单个文件
    """
    if not os.path.exists(dir_path):
        return
    # 遍历目录中的文件
    for file_name in os.listdir(dir_path):
        if file_name.startswith(f"{id}_"):
            file_path = os.path.join(dir_path, file_name)
            # 删除文件
            try:
                os.remove(file_path)
                logger.info(f"File {file_path} removed successfully.")
            except OSError as e:
                logger.error(f"Error removing file {file_path}: {e}")

def run_command(cmd):
    """
    执行命令
    """
    output = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #rst = output.stdout.read().decode("UTF8").strip()
    rst = output.stdout.readlines()
    return rst

# ------------------------------------------------------

def get_file_createtime(filepath):
    """
    获取文件创建时间
    """
    timestamp = os.path.getctime(filepath)
    time_struct = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', time_struct)

def get_file_size(filepath):
    """
    获取文件大小(MB,保留两位小数点)
    """
    fsize = os.path.getsize(filepath)
    fsize = fsize / float(1024 * 1024)
    return round(fsize, 2)

def get_file_md5(filepath):
    """
    获取文件md5
    """
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

def get_file_crc(filepath):
    """
    获取文件crc
    """
    with open(filepath, "rb") as f:
        crc = hex(crc32(f.read()))[2:].upper()
    return crc

# ------------------------------------------------------

def get_video_fps(filepath):
    """
    获取视频帧率(秒,保留3位小数点)
    """
    # 读取视频
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        cap.release()
        return 0.0
    # 视频帧率
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return round(fps, 3)

def get_video_resolution(filepath):
    """
    获取视频分辨率大小
    """
    # 读取视频
    cap = cv2.VideoCapture(filepath)
    # 视频高度
    frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if frame_height == 0:
        cap.release()
        return '0'
    # 视频宽度
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    cap.release()
    logger.debug(f"frame_width: {int(frame_width)} frame_height: {int(frame_height)}")
    return f'{int(frame_height)}p'
    # return f"{int(frame_width)}x{int(frame_height)}"

def get_video_aspectratio(filepath):
    """
    获取视频宽高比例
    """
    # 读取视频
    cap = cv2.VideoCapture(filepath)
    # 视频高度
    frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if frame_height == 0:
        cap.release()
        return '0'
    # 视频宽度
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    cap.release()
    logger.debug(f"frame_width: {int(frame_width)} frame_height: {int(frame_height)}")
    aspectratio = frame_height/frame_width
    logger.debug(f"aspectratio: {aspectratio}")
    return round(aspectratio, 5)

def get_video_duration(filepath):
    """
    获取视频时长(秒,保留3位小数点)
    """
    # 读取视频
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        cap.release()
        return 0.0
    # 视频帧率
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0.0:
        cap.release()
        return 0.0
    # 视频帧数
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count < 0:
        cap.release()
        return 0.0
    # 视频时长
    duration = frame_count / fps
    cap.release()
    logger.debug(f"frame_count: {frame_count} / fps: {fps} = duration: {duration}")
    return round(duration, 3)

def get_video_info(filepath):
    """
    获取视频信息
    """
    info = {
        "width": 0,
        "height": 0,
        "aspectratio": 0,
        "fps": 0,
        "frame": 0,
        "duration": 0,
    }
    # 读取视频
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        cap.release()
        return info
    
    # 视频高度
    frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if frame_height == 0:
        cap.release()
        return info
    info['height'] = int(frame_height)
    # 视频宽度
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    info['width'] = int(frame_width)
    # logger.debug(f"frame_height: {int(frame_height)} / frame_width: {int(frame_width)}")
    # 高宽比
    aspectratio = frame_height/frame_width
    info['aspectratio'] = round(aspectratio, 5)
    # logger.debug(f"frame_height: {int(frame_height)} / frame_width: {int(frame_width)} = aspectratio: {round(aspectratio, 5)}")
    
    # 视频帧率
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0.0:
        cap.release()
        return info
    info['fps'] = round(fps, 3)
    # 视频帧数
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count < 0:
        cap.release()
        return info
    info['frame'] = round(frame_count, 3)
    # logger.debug(f"frame_count: {frame_count} / fps: {fps}")
    # 视频时长
    duration = frame_count / fps
    info['duration'] = round(duration, 3)
    # logger.debug(f"frame_count: {frame_count} / fps: {fps} = duration: {round(duration, 3)}")

    cap.release()
    return info

def get_crf_value(filepath):
    """
    根据文件扩展名和大小返回相应的CRF值 0无损 23默认 51最差 8 10 12 15
    如果是avi结尾crf为12 如果size大于4GB,crf为15
    """
    file_ext = os.path.splitext(filepath)[1].lower()
    file_size_gb = get_file_size(filepath) / 1024  # 转换为GB
    
    if file_ext == '.avi':
        return '10'
    elif file_size_gb > 4:  # 大于4GB
        return '15'
    else:
        return '12'  # 默认值
# ------------------------------------------------------

def check_ffmpeg_processes():
    try:
        # 使用 ps 命令查找 ffmpeg 进程
        result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"Error running ps command: {result.stderr}")
            return []
        # 检查输出中是否包含 ffmpeg & vcodec
        processes = []
        for line in result.stdout.splitlines():
            if 'ffmpeg' in line and 'vcodec' in line and 'ps aux' not in line and 'grep' not in line:
                processes.append(line.strip())
        return processes
    except Exception as e:
        logger.error(f"Error checking ffmpeg processes: {e}")
        return []

# ------------------------------------------------------

# /api/cut 视频截取
def sync_file_cut(ss, tt, frompath, topath, id):
    """
    视频截取
    """
    # cut
    ## 获取视频时长
    file_duration = get_video_duration(frompath)
    logger.debug(f"duration: {file_duration}")
    if file_duration == 0.0:
        logger.error(f"Duration parsing error: Invalid sample size - {frompath}")
        return {"code": 400, "success": False, "msg": "Duration parsing error: Invalid sample size"}

    ## 截取视频
    # cmd = 'ffmpeg -y -i "{}" -ss {} -t {} -vcodec copy -acodec copy "{}" -loglevel quiet '.format(frompath, ss, file_duration - ss, topath)
    # logger.debug(f"cmd: {cmd}")
    # rst = run_command(cmd)
    ## 截取视频2
    command = [
        'ffmpeg', '-y',
        '-i', str(frompath),
        '-ss', str(ss),
        '-t', str(file_duration - ss - tt),
        '-vcodec', 'copy',
        '-acodec', 'copy',
        str(topath),
        '-loglevel', 'quiet'
    ]
    logger.debug(f"command: {command}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # rst = process.stdout.readlines()
    # rst = [r.decode("UTF8").strip() for r in rst]
    # process.wait()

    rst, _ = process.communicate()
    rst = [r.decode("UTF8").strip() for r in rst.splitlines()]

    ## 替换原视频
    if os.path.exists(frompath):
        # 删除文件
        try:
            os.remove(frompath)
            logger.info(f"File {frompath} remove successfully.")
        except OSError as e:
            logger.error(f"File remove Error: {e}")
    if os.path.exists(topath):
        # 重命名
        try:
            os.rename(topath, frompath)
            logger.info(f"File {frompath} rename successfully.")
        except OSError as e:
            logger.error(f"File rename Error: {e}")

    ## 删除缩略图
    # delete_file(TEMP_PATH, id)
    video_hash = hashlib.sha256(frompath.encode()).hexdigest()
    old_thumbnail_path = f"{TEMP_PATH}/{video_hash}.png"
    if os.path.exists(old_thumbnail_path):
        os.remove(old_thumbnail_path)

    logger.success(f"File cut successfully! id: {id} second: {ss}")

# /api/transcode 视频转码
def sync_file_transcode(frompath, topath, id):
    """
    视频转码为mp4
    """
    # cut
    ## 获取视频时长
    file_duration = get_video_duration(frompath)
    logger.debug(f"duration: {file_duration}")
    if file_duration == 0.0:
        logger.error(f"Duration parsing error: Invalid sample size - {frompath}")
        return {"code": 400, "success": False, "msg": "Duration parsing error: Invalid sample size"}

    crf_value = get_crf_value(frompath)
    ## 视频转码
    command = [
        'ffmpeg', '-y',
        '-i', str(frompath),
        '-c:v', 'libx264',  # 使用 libx264 编码器
        '-c:a', 'aac',      # 使用 aac 编码器
        '-preset', 'slow',  # 编码速度 ultrafast superfast veryfast faster fast medium slow slower veryslow
        '-crf', str(crf_value),    # 质量  0无损 23默认 51最差 8 10 12 15
        '-movflags', 'faststart',  # 视频快速启动，将视频元数据(moov atom)移到文件开头
        '-loglevel', 'quiet',
        str(topath)
    ]
    logger.debug(f"command: {command}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    rst, _ = process.communicate()
    rst = [r.decode("UTF8").strip() for r in rst.splitlines()]

    ## 替换原视频
    if os.path.exists(frompath):
        # 删除文件
        try:
            os.remove(frompath)
            logger.info(f"File {frompath} remove successfully.")
        except OSError as e:
            logger.error(f"File remove Error: {e}")
    # if os.path.exists(topath):
    #     # 重命名
    #     try:
    #         os.rename(topath, frompath)
    #         logger.info(f"File {frompath} rename successfully.")
    #     except OSError as e:
    #         logger.error(f"File rename Error: {e}")

    ## 删除缩略图
    # delete_file(TEMP_PATH, id)
    video_hash = hashlib.sha256(frompath.encode()).hexdigest()
    old_thumbnail_path = f"{TEMP_PATH}/{video_hash}.png"
    if os.path.exists(old_thumbnail_path):
        os.remove(old_thumbnail_path)

    logger.success(f"File transcode successfully! id: {id}")

# /api/scan 扫描路径
def sync_scan_path(localpaths):
    async def run_async_scan():
        async with get_db_app() as cursor:
            for localpath in localpaths:
                logger.info(f"scan path: {localpath}")
                for fpathe, dirs, files in os.walk(localpath):
                    # 路径关键字在过滤列表里
                    if any(filter in fpathe for filter in PATH_FILTER_LIST):
                        logger.trace(f"The path keywords are in the filter list - fpathe: {fpathe}")
                        continue

                    files.sort()
                    for file in files:
                        # logger.debug(f"file: {file}")
                        # 合成文件路径
                        file_full = os.path.join(fpathe, file)
                        # logger.debug(f"file_full: {file_full}")

                        # 过滤mac垃圾文件
                        if file.startswith(".DS_Store") or file.startswith("._"):
                            if os.path.isfile(file_full):
                                # 删除文件
                                try:
                                    os.remove(file_full)
                                    logger.info(f"File {file_full} remove successfully.")
                                except OSError as e:
                                    logger.error(f"File remove Error: {e}")
                            continue

                        # Check if file already exists
                        check_query = "SELECT id FROM dav_local WHERE path=%s and file=%s and status=0"
                        values = (fpathe, file,)
                        check_query = format_query_for_db(check_query)
                        logger.debug(f"check_query: {check_query} values: {values}")
                        await cursor.execute(check_query, values)
                        exist_file = await cursor.fetchone()
                        # logger.debug(f"exist_file: {exist_file}")
                        exist_file = convert_row_to_dict(exist_file, cursor.description)  # 转换字典
                        logger.debug(f"exist_file: {exist_file}")
                        if exist_file:
                            # traceLog.add(f"File has been added - {file}")
                            logger.trace(f"File has been added - {file}")
                            continue
                        else:  # 数据库没有，开始入库逻辑
                            # 获取 文件名 后缀
                            file_name = os.path.splitext(file)[0]
                            file_ext = os.path.splitext(file)[1]
                            # logger.debug(f"file_path: {fpathe} / file_name: {file_name} / file_ext: {file_ext}")

                            # 文件后缀不在支持数组列表里
                            if not file_ext.lower() in SCAN_EXT_LIST:
                                logger.trace(f"Unknown extension: {file_ext.lower()} - {file_full}")
                                continue

                            # 文件名过滤luan/small
                            if '-luan' in file_name or '-small' in file_name or '-good' in file_name:
                                file_name = file_name.rsplit('-', 1)[0]
                                logger.debug(f"2 file_path: {fpathe} / file_name: {file_name} / file_ext: {file_ext}")

                            if SCAN_CODE:
                                # 获取识别码
                                file_code = file_name.split(' ')[0]
                                # logger.debug(f"file_code: {file_code}")
                                # 识别码含有未知字符
                                if not contains_alpha_numeric_symbol(file_code):
                                    logger.error(f"The code contains unknown characters: {file_code} - {file_full}")
                                    continue
                                # 识别码含有中文字符
                                if contains_chinese(file_code):
                                    logger.error(f"The code contains Chinese characters: {file_code} - {file_full}")
                                    continue
                                # 识别码超长
                                if len(file_code) > 48:
                                    logger.error(f"The code is too long: {file_code} - {file_full}")
                                    continue
                            else:
                                file_code = ""

                            # 获取文件大小 MB
                            file_size = get_file_size(file_full)
                            # logger.debug(f"size: {file_size} MB")
                            if file_size < 1:
                                logger.debug(f"Abnormal file size: < 1 MB - {file_full}")
                                continue

                            # 获取文件创建时间
                            file_createtime = get_file_createtime(file_full)
                            # logger.debug(f"time: {file_createtime}")
                            # # 获取文件crc
                            # file_crc = get_file_crc(file_full)
                            # logger.debug(f"crc: {file_crc}")

                            # 获取视频信息
                            file_info = get_video_info(file_full)
                            file_resolution = f"{int(file_info['height'])}p"
                            file_aspectratio = file_info['aspectratio']
                            file_duration = file_info['duration']
                            file_fps = file_info['fps']
                            if file_resolution == '0p':
                                logger.error(f"Resolution parsing error: moov atom not found - {file_full}")
                                continue
                            if file_aspectratio == 0:
                                logger.error(f"Aspectratio parsing error: moov atom not found - {file_full}")
                                continue
                            if file_duration == 0.0:
                                logger.error(f"Duration parsing error: Invalid sample size - {file_full}")
                                continue
                            if file_fps == 0.0:
                                logger.error(f"fps parsing error: Invalid fps size - {file_full}")
                                continue
                            # 视频时长 转 时分秒
                            file_hms = duration_to_hms(file_duration)
                            # logger.debug(f"duration: {file_duration} => hms: {file_hms}")

                            logger.debug(f"code: {file_code} / file: {file_full} / size: {file_size} MB / duration: {file_hms} / resolution: {file_resolution} / fps: {file_fps}")

                            # 使用 ffmpeg 获取视频信息
                            video_format_name = ""
                            # try:
                            #     filepath = os.path.join(fpathe, file)
                            #     probe = ffmpeg.probe(filepath)
                            #     video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                            #     logger.debug(f"video_info: {video_info}")
                            #     video_format = probe['format']
                            #     logger.debug(f"video_format: {video_format}")
                            #     video_format_name = video_format['format_name']
                            #     logger.debug(f"video_format_name: {video_format_name}")
                            # except ffmpeg.Error as e:
                            #     video_format_name = ""
                            #     logger.error(f"FFmpeg error: {e.stderr.decode()}")
                            # logger.debug(f"video_format_name: {video_format_name}")

                            update_id = 0
                            if file_code != "":
                                # Check if code already exists
                                check_query = "SELECT id FROM dav_local WHERE path=%s and UPPER(code)=%s and size=%s and duration=%s and status=0"
                                values = (fpathe, file_code, file_size, file_duration,)
                                check_query = format_query_for_db(check_query)
                                logger.debug(f"check_query: {check_query} values: {values}")
                                await cursor.execute(check_query, values)
                                exist_code = await cursor.fetchone()
                                # logger.debug(f"exist_code: {exist_code}")
                                exist_code = convert_row_to_dict(exist_code, cursor.description)  # 转换字典
                                logger.debug(f"exist_code: {exist_code}")
                                update_id = exist_code['id'] if exist_code else 0
                            
                            if update_id > 0:
                                # Update File
                                update_query = "UPDATE dav_local SET code=%s, name=%s, file=%s WHERE id=%s and status=0"
                                values = (file_code, file_name, file, update_id,)
                                update_query = format_query_for_db(update_query)
                                logger.debug(f"update_query: {update_query} values: {values}")
                                await cursor.execute(update_query, values)
                            else:
                                # Insert File
                                insert_query = "INSERT INTO dav_local (code, name, path, file, size, created, duration, aspectratio, resolution, format, fps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                                values = (file_code, file_name, fpathe, file, file_size, file_createtime, file_duration, file_aspectratio, file_resolution, video_format_name, file_fps,)
                                insert_query = format_query_for_db(insert_query)
                                logger.debug(f"insert_query: {insert_query} values: {values}")
                                await cursor.execute(insert_query, values)
                            if DB_ENGINE == "sqlite": cursor.connection.commit()
                            else: await cursor.connection.commit()
                logger.info(f"scan path: {localpath} end")
            logger.success(f"Folder scan successful! localpaths: {localpaths}")

    # 运行异步逻辑
    return asyncio.run(run_async_scan())

# /api/syncthumbnail 批量生成缩略图
def sync_generate_thumbnails(local_files):
    """
    批量生成缩略图
    """
    thumbnail_urls = {}
    cpu_count = os.cpu_count() or 1
    if cpu_count > APP_PAGE_LIMIT: cpu_count=APP_PAGE_LIMIT
    logger.debug(f"max_workers: {cpu_count}")
    with ThreadPoolExecutor(max_workers=cpu_count) as executor:  # 设置最大线程数
        future_to_local_file = {
            executor.submit(generate_thumbnail, local_file['id'], local_file['code'], os.path.join(local_file['path'], local_file['file'])): local_file
            for local_file in local_files
        }
        for future in as_completed(future_to_local_file):
            local_file = future_to_local_file[future]
            try:
                thumbnail_url = future.result()
                # logger.debug(f"thumbnail_url: {thumbnail_url}")
                local_file['thumbnail_url'] = thumbnail_url
                thumbnail_urls[local_file['id']] = thumbnail_url
            except Exception as e:
                logger.error(f"Error generating thumbnail for {local_file['id']}: {str(e)}")
    logger.success(f"Thumbnail sync successful! len: {len(thumbnail_urls)}")

# /index.html 批量获取缩略图
async def generate_thumbnails(local_files, isShow=True):
    """
    批量获取缩略图
    """
    thumbnail_urls = {}
    cpu_count = os.cpu_count() or 1
    if cpu_count > APP_PAGE_LIMIT: cpu_count=APP_PAGE_LIMIT
    # logger.debug(f"max_workers: {cpu_count}")
    with ThreadPoolExecutor(max_workers=cpu_count) as executor:  # 设置最大线程数
        future_to_local_file = {
            executor.submit(generate_thumbnail, local_file['id'], local_file['code'], os.path.join(local_file['path'], local_file['file']), isShow): local_file
            for local_file in local_files
        }
        for future in as_completed(future_to_local_file):
            local_file = future_to_local_file[future]
            try:
                thumbnail_url = future.result()
                # logger.debug(f"thumbnail_url: {thumbnail_url}")
                local_file['thumbnail_url'] = thumbnail_url
                thumbnail_urls[local_file['id']] = thumbnail_url
            except Exception as e:
                logger.error(f"Error generating thumbnail for {local_file['id']}: {str(e)}")
    logger.debug(f"thumbnail_urls: {thumbnail_urls}")
    return thumbnail_urls

def generate_thumbnail(id_name: str, code_name: str, video_name: str, isShow=True):
    """
    获取缩略图
    """
    if not isShow:
        return "/frontend/static/images/video.png"
    # 文件存在检测
    if not os.path.exists(video_name):
        logger.error(f"The file does not exist - {video_name}")
        return "/frontend/static/images/video.png"
    # 后缀检测iso
    if Path(video_name).suffix.lower() in ['.iso']:
        logger.error(f"Unsupported file extension - {video_name}")
        return "/frontend/static/images/video.png"
    
    if not os.path.exists(TEMP_PATH): os.mkdir(TEMP_PATH)
    
    # thumbnail_path = f"{TEMP_PATH}/{id_name}_{code_name}.png" if code_name else f"{TEMP_PATH}/{id_name}.png"
    video_hash = hashlib.sha256(video_name.encode()).hexdigest()
    thumbnail_path = f"{TEMP_PATH}/{video_hash}.png"
    thumbnail2_path = f"{TEMP2_PATH}/{video_hash}.png"
    # logger.debug(f"thumbnail_path: {thumbnail_path}")
    # logger.debug(f"thumbnail2_path: {thumbnail2_path}")
    if os.path.exists(thumbnail_path):
        return thumbnail_path
    if os.path.exists(thumbnail2_path):
        shutil.move(thumbnail2_path, thumbnail_path)
        logger.debug(f"Move file: {thumbnail_path}")
        return thumbnail_path
    if not os.path.exists(thumbnail_path):
        try:
            ## cv2截图
            # 读取视频
            cap = cv2.VideoCapture(video_name)
            # 视频能否打开
            if not cap.isOpened():
                logger.error(f"The file cannot be opened - {video_name}")
                return "/frontend/static/images/video.png"
            # 视频帧率
            fps = cap.get(cv2.CAP_PROP_FPS)
            # 视频帧数
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                logger.error(f"The video is too short - {video_name}")
                return "/frontend/static/images/video.png"
            duration = frame_count / fps
            # 截图时间
            screenshot_time = int(duration) if duration < THUMBNAIL_TIME else THUMBNAIL_TIME
            # 设置帧数
            frame_id = screenshot_time * fps
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            # 读帧
            result, frame = cap.read()
            if not result:
                logger.error(f"Failed to read frame. ERROR: {str(result).splitlines()[0]} - {video_name} - {screenshot_time}")
                return "/frontend/static/images/video.png"
            
            # 获取原始图像的宽度和高度
            original_height, original_width = frame.shape[:2]
            # 目标宽度和高度
            target_width = 640
            target_height = 360
            # 计算缩放比例
            if original_width > original_height:
                scale = target_width / original_width
            else:
                scale = target_height / original_height
            # 计算新的宽度和高度
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            # 调整图像尺寸
            frame = cv2.resize(frame, (new_width, new_height))
            
            # 设置压缩参数
            compression_params = [cv2.IMWRITE_PNG_COMPRESSION, THUMBNAIL_COMPRESSION]  # 压缩度: 0-9
            # 编码图像
            result, encoded_image = cv2.imencode('.png', frame, compression_params)
            if not result:
                logger.error(f"Failed to imencode frame. ERROR: {str(result).splitlines()[0]} - {video_name}")
                return "/frontend/static/images/video.png"
            # 保存图片
            encoded_image.tofile(thumbnail_path)
            logger.debug(f"id_name: {id_name} thumbnail_path: {thumbnail_path}")
        except FileNotFoundError as e:
            logger.error(f"FileNotFoundError ERROR: {str(e).splitlines()[0]} - {video_name}")
            return "/frontend/static/images/video.png"
        except Exception as e:
            logger.error(f"Exception ERROR: {str(e).splitlines()[0]} - {video_name}")
            return "/frontend/static/images/video.png"
        finally:
            # 确保视频文件被释放
            if cap.isOpened():
                cap.release()
    if not os.path.exists(thumbnail_path):
        logger.warning(f"The thumbnail not found: {thumbnail_path}")
        return "/frontend/static/images/video.png"
    return thumbnail_path

# ------------------------------------------------------
