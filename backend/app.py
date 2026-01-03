#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import random
import argparse
import asyncio
import datetime
import subprocess
from datetime import datetime as dt
from pathlib import Path

from utils.local import sync_file_cut, sync_file_transcode, check_ffmpeg_processes
from utils.local import get_file_size, get_file_createtime
from utils.log import log as logger
from utils.db import get_db_app
from config import DB_ENGINE

## app

"""
 - 处理剪切任务队列
 - 处理转码任务队列
"""

async def fetch_next_mission(cursor):
    query = "SELECT * FROM dav_missions WHERE status<2 limit 1"
    values = ()
    await cursor.execute(query, values)
    mission_info = await cursor.fetchone()
    
    # 如果是元组，转换为字典
    if isinstance(mission_info, tuple):
        mission_info = dict(zip([desc[0] for desc in cursor.description], mission_info))
    return mission_info

async def update_mission_status(cursor, mission_id, status):
    update_query = "UPDATE dav_missions SET status=%s WHERE id=%s"
    values = (status, mission_id,)
    if DB_ENGINE == "sqlite": 
        update_query = update_query.replace('%s', '?')
    logger.debug(f"update_query: {update_query} values: {values}")
    await cursor.execute(update_query, values)
    if DB_ENGINE == "sqlite": 
        cursor.connection.commit()
    else: 
        await cursor.connection.commit()

async def update_local_file(cursor, local_id, local_file):
    # 获取文件大小 MB
    file_size = get_file_size(local_file)
    # logger.debug(f"size: {file_size} MB")
    if file_size < 1:
        logger.debug(f"Abnormal file size: < 1 MB - {local_file}")
        # continue
    # 获取文件创建时间
    file_createtime = get_file_createtime(local_file)
    # logger.debug(f"time: {file_time}")
    logger.debug(f"file: {local_file} / size: {file_size} MB / create_time: {file_createtime}")
    # 获取文件名
    file_name = local_file.split('/')[-1]

    update_query = "UPDATE dav_local SET file=%s,size=%s,created=%s,updated_time=NOW() WHERE id=%s"
    values = (file_name, file_size, file_createtime, local_id,)
    if DB_ENGINE == "sqlite": 
        update_query = update_query.replace('%s', '?').replace('NOW()','CURRENT_TIMESTAMP')
    logger.debug(f"update_query: {update_query} values: {values}")
    await cursor.execute(update_query, values)
    if DB_ENGINE == "sqlite": 
        cursor.connection.commit()
    else: 
        await cursor.connection.commit()

async def process_mission(cursor, mission_info):
    type = mission_info['type']
    id_name = mission_info['localid']
    frompath = os.path.join(mission_info['path'], mission_info['file'])
    to_name = os.path.splitext(frompath)[0]
    to_extend = os.path.splitext(frompath)[1]
    logger.info(f"Mission {mission_info['id']} { 'cut' if type==1 else 'transcode' if type==2 else 'None' } is starting - {frompath}")
    if type == 1:
        topath = to_name + '-cut' + to_extend
        start_second = mission_info['start']
        end_second = mission_info['end']
        sync_file_cut(int(start_second), int(end_second), frompath, topath, id_name)
    elif type == 2:
        topath = to_name + '-transcode.mp4'  # topath = to_name + '-transcode' + to_extend
        sync_file_transcode(frompath, topath, id_name)
        if os.path.exists(topath):
            await update_local_file(cursor, id_name, topath)
    else:
        logger.error(f"Mission {mission_info['id']} unknown type error {type}")
        return
    logger.success(f"Mission {mission_info['id']} { 'cut' if type==1 else 'transcode' if type==2 else 'None' } completed")

# 定时线程
async def mission_all():
    try:
        id=0
        while True:
            # current_timestamp = int(time.time())
            # logger.debug(f"current_timestamp: {current_timestamp}")
            async with get_db_app() as cursor:
                mission_info = await fetch_next_mission(cursor)
                # logger.debug(f"mission_info: {mission_info}")
                
                id+=1
                if mission_info is None:
                    if id % 30 == 1:
                        logger.success(f"No task, waiting for the next check...")
                    else:
                        logger.debug(f"No task, waiting for the next check...")
                    await asyncio.sleep(60)
                    continue
                
                if mission_info['status'] == 1:
                    logger.info(f"Mission {mission_info['id']} is running")
                    await asyncio.sleep(60)
                    continue
                
                # 检测是否存在ffmpeg进程
                ffmpeg_processes = check_ffmpeg_processes()
                if ffmpeg_processes:
                    logger.info(f"Process exists: {ffmpeg_processes}")
                    await asyncio.sleep(60)
                    continue
                
                # 更新状态 status=1 剪切中
                await update_mission_status(cursor, mission_info['id'], 1)
                
                # 开始剪切
                await process_mission(cursor, mission_info)
                
                # 更新状态 status=2 剪切完成
                await update_mission_status(cursor, mission_info['id'], 2)
            
    except asyncio.CancelledError:
        logger.info("Task cancelled, exiting.")
        await cursor.close()
        raise
    except Exception as e:
        logger.error(f"Error in mission_all: {e}")
        # await asyncio.sleep(60)

if __name__ == "__main__":
    # 初始化参数
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', type=bool, default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    run_debug = bool(args.debug)

    # 日志级别
    log_level = "DEBUG" if run_debug else "INFO"
    logger.remove()
    logger.add(sys.stdout, level=log_level)

    try:
        asyncio.run(mission_all())
    except KeyboardInterrupt:
        logger.info("Exit")
