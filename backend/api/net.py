import os
import json
import base58
from datetime import datetime as dt
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

from utils.db import database, get_db
from utils.log import log as logger
from utils.local import *
from utils.web import *
from config import *


router = APIRouter()


## net


## name
@router.get("/get_name/{code_name}")
async def get_net_video(code_name: str, cursor=Depends(get_db)):
    """获取code信息"""
    logger.info(f"/api/get_name - code_name: {code_name}")

    try:
        # 获取code信息
        check_query = "SELECT code,name,date,studio,director,series,genre,websites,actors,images,score FROM dav_web WHERE code=%s"
        values = (code_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        code_info = await cursor.fetchone()
        if code_info is None:
            if code_name.upper().startswith('FC2-'):
                code_info = get_123av_title(code_name)
            else:
                code_info = get_javbus_title(code_name)
            logger.debug(f"code_info: {code_info}")
            if code_info is None:
                return {
                    "code": 404,
                    "success": False,
                    "msg": "Code not found",
                }
            # Insert web
            insert_query = "INSERT INTO dav_web (code,name,date,studio,director,series,genre,websites,actors,images) SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM dav_web WHERE code=%s)"
            values = (code_info['code'], code_info['name'], code_info['date'], code_info['studio'], code_info['director'], code_info['series'], json.dumps(code_info['genre'], ensure_ascii=False),  json.dumps(code_info['websites']), json.dumps(code_info['actors'], ensure_ascii=False), json.dumps(code_info['images'], ensure_ascii=False), code_info['code'],)
            if DB_ENGINE == "sqlite": insert_query = insert_query.replace('%s','?')
            # logger.debug(f"insert_query: {insert_query} values: {values}")
            await cursor.execute(insert_query, values)
            if DB_ENGINE == "sqlite": cursor.connection.commit()
            else: await cursor.connection.commit()
        # 如果是元组，转换为字典
        if isinstance(code_info, tuple):
            code_info = dict(zip([desc[0] for desc in cursor.description], code_info))
        logger.debug(f"code_info: {code_info}")

        # # base58 加密
        # base_bytes = base58.b58encode(json.dumps(codeinfo).encode())
        # # logger.debug(f"path_bytes: {base_bytes}")
        # base_str = bytes.decode(base_bytes)
        # # logger.debug(f"base_str: {base_str}")

        logger.success(f"Get code successful! code: {code_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": code_info,
        }
    except Exception as e:
        logger.error(f"/api/get_name - code_name: {code_name} - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}

