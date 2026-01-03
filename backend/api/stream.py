import re
import os
import sys
import time
import base58
import signal
import ffmpeg
import asyncio
import mimetypes
import aiofiles
import subprocess
from datetime import datetime as dt
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

from utils.db import database, get_db
from utils.log import log as logger
from utils.local import *
from config import *


router = APIRouter()


## play


global_processes=[]

# stream 206
@router.get("/stream/{id_name}/{base_name}")
async def stream_video(request: Request, id_name: str, base_name: str):
    """请求视频流 206"""
    logger.info(f"/api/stream/{id_name}/{base_name[:20]} - id_name: {id_name}")

    try:
        # base58 解密
        # logger.debug(f"base_name: {base_name}")
        path_bytes = base58.b58decode(base_name)
        # logger.debug(f"path_bytes: {path_bytes}")
        path = bytes.decode(path_bytes)
        logger.debug(f"path: {path}")

        video_path = Path(path)
        # logger.debug(f"video_path: {video_path}")
        if not video_path.is_file():
            logger.warning(f"Invalid or unsafe path: {video_path}")
            return HTMLResponse("Invalid or unsafe path", status_code=403)
        if not video_path.exists():
            logger.warning(f"Video not found for streaming: {id_name}")
            return HTMLResponse("Video not found for streaming", status_code=404)

        mime_type, _ = mimetypes.guess_type(video_path)
        mime_type = mime_type or 'application/octet-stream'
        # mime_type = 'video/mp2t'
        logger.debug(f"mime_type: {mime_type}")
        file_size = video_path.stat().st_size
        logger.debug(f"file_size: {file_size}")

        headers = {}
        content_range = request.headers.get('range')
        if content_range:
            content_range = content_range.strip().lower()
            range_match = re.match(r'bytes=(\d+)-(\d*)', content_range)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                if start >= file_size or end >= file_size:
                    logger.warning(f"Invalid request range: {content_range}")
                    return HTMLResponse("Invalid request range", status_code=404)

                logger.debug(f"start: {start} end: {end}")

                async def interfile():
                    async with aiofiles.open(video_path, 'rb') as f:
                        await f.seek(start)
                        bytes_to_send = end - start + 1
                        chunk_size = 1024 * 1024
                        logger.debug(f"bytes_to_send: {bytes_to_send}")
                        while bytes_to_send > 0:
                            read_bytes = min(chunk_size, bytes_to_send)
                            data = await f.read(read_bytes)
                            if not data:
                                break
                            yield data
                            bytes_to_send -= len(data)

                headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                return StreamingResponse(interfile(), status_code=206, headers=headers, media_type=mime_type)
        else:
            return FileResponse(video_path, media_type=mime_type)
    except Exception as e:
        logger.error(f"/api/stream/{id_name}/{base_name[:20]} - except ERROR: {str(e)}")
        return HTMLResponse("Server error", status_code=500)
        # return {"code": 500, "success": False, "msg": "Server error"}


# convert 206
@router.get("/convert/{id_name}/{base_name}")
async def convert_video(request: Request, id_name: str, base_name: str):
    """请求转码后的视频流 206"""
    logger.info(f"/api/convert/{id_name}/{base_name[:20]} - id_name: {id_name}")

    global global_process
    try:
        # base58 解密
        # logger.debug(f"base_name: {base_name}")
        path_bytes = base58.b58decode(base_name)
        # logger.debug(f"path_bytes: {path_bytes}")
        path = bytes.decode(path_bytes)
        logger.debug(f"path: {path}")

        video_path = Path(path)
        # logger.debug(f"video_path: {video_path}")
        if not video_path.is_file():
            logger.warning(f"Invalid or unsafe path: {video_path}")
            return HTMLResponse("Invalid or unsafe path", status_code=403)
        if not video_path.exists():
            logger.warning(f"Video not found for streaming: {id_name}")
            return HTMLResponse("Video not found for streaming", status_code=404)

        # 关闭未结束的进程
        for process_one in global_processes:
            if process_one.returncode is None:
                process_one.send_signal(signal.SIGKILL)
                logger.info(f"kill process: {process_one.pid}")
            global_processes.remove(process_one)

        start_time=0
        ## 使用 FFmpeg 进行实时转码
        command = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),  # 指定起始时间
            '-f', 'mp4',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-tune', 'zerolatency',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof+faststart',
            '-reset_timestamps', '1',
            '-fflags', '+genpts',
            '-avoid_negative_ts', '1',
            '-'
        ]
        # process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        global_processes.append(process)

        async def generate():
            try:
                while True:
                    data = await asyncio.wait_for(process.stdout.read(1024*1024), timeout=10)
                    if not data:
                        break
                    yield data
            except asyncio.TimeoutError:
                logger.error("FFmpeg process timed out")
                process.send_signal(signal.SIGKILL)
                yield b""

        return StreamingResponse(generate(), media_type='video/mp4')
        
    except Exception as e:
        logger.error(f"/api/convert/{id_name}/{base_name[:20]} - except ERROR: {str(e)}")
        return HTMLResponse("Server error", status_code=500)


# stream convert 206
@router.get("/stream/convert/{id_name}/{base_name}")
async def stream_and_convert_video(request: Request, id_name: str, base_name: str):
    """请求转码后的视频流 206"""
    logger.info(f"/api/stream/convert/{id_name}/{base_name[:20]} - id_name: {id_name}")

    global global_process
    try:
        # base58 解密
        # logger.debug(f"base_name: {base_name}")
        path_bytes = base58.b58decode(base_name)
        # logger.debug(f"path_bytes: {path_bytes}")
        path = bytes.decode(path_bytes)
        # logger.debug(f"path: {path}")

        video_path = Path(path)
        # logger.debug(f"video_path: {video_path}")
        if not video_path.is_file():
            logger.warning(f"Invalid or unsafe path: {video_path}")
            return HTMLResponse("Invalid or unsafe path", status_code=403)
        if not video_path.exists():
            logger.warning(f"Video not found for streaming: {id_name}")
            return HTMLResponse("Video not found for streaming", status_code=404)

        # 关闭未结束的进程
        for process_one in global_processes:
            if process_one.returncode is None:
                process_one.send_signal(signal.SIGKILL)
                logger.info(f"kill process: {process_one}")
            global_processes.remove(process_one)
        
        # 后缀检测
        file_ext = os.path.splitext(path)[1]
        if file_ext.lower() in ['.avi','.wmv','.rmvb','.ts', '.mpg']: # 使用ffmpeg转码后再返回文件流
            start_time = 0
            ## 使用 FFmpeg 进行实时转码
            command = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(start_time),
                '-f', 'mp4',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-tune', 'zerolatency',
                '-movflags', 'frag_keyframe+empty_moov+default_base_moof+faststart',
                '-reset_timestamps', '1',
                '-fflags', '+genpts',
                '-avoid_negative_ts', '1',
                '-'
            ]
            # process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            global_processes.append(process)

            async def generate():
                try:
                    while True:
                        data = await asyncio.wait_for(process.stdout.read(1024*1024), timeout=10)
                        if not data:
                            break
                        yield data
                except asyncio.TimeoutError:
                    logger.error("FFmpeg process timed out")
                    process.send_signal(signal.SIGKILL)
                    yield b""

            return StreamingResponse(generate(), media_type='video/mp4')
        
        else: # 直接返回文件流
            mime_type, _ = mimetypes.guess_type(video_path)
            mime_type = mime_type or 'application/octet-stream'
            # mime_type = 'video/mp2t'
            logger.debug(f"mime_type: {mime_type}")
            file_size = video_path.stat().st_size
            # logger.debug(f"file_size: {file_size}")

            headers = {}
            content_range = request.headers.get('range')
            if content_range:
                content_range = content_range.strip().lower()
                range_match = re.match(r'bytes=(\d+)-(\d*)', content_range)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    if start >= file_size or end >= file_size:
                        logger.warning(f"Invalid request range: {content_range}")
                        return HTMLResponse("Invalid request range", status_code=404)
                    logger.debug(f"start: {start} end: {end}")

                    async def interfile():
                        async with aiofiles.open(video_path, 'rb') as f:
                            await f.seek(start)
                            bytes_to_send = end - start + 1
                            chunk_size = 1024 * 1024
                            logger.debug(f"bytes_to_send: {bytes_to_send}")
                            while bytes_to_send > 0:
                                read_bytes = min(chunk_size, bytes_to_send)
                                data = await f.read(read_bytes)
                                if not data:
                                    break
                                yield data
                                bytes_to_send -= len(data)

                    headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    return StreamingResponse(interfile(), status_code=206, headers=headers, media_type=mime_type)
            else:
                return FileResponse(video_path, media_type=mime_type)
        
    except Exception as e:
        logger.error(f"/api/stream/convert/{id_name}/{base_name[:20]} - except ERROR: {str(e)}")
        return HTMLResponse("Server error", status_code=500)

