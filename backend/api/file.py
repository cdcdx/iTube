import os
import json
import base58
import shutil
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


## file


## name
@router.get("/name/{id_name}")
async def get_video(id_name: str, cursor=Depends(get_db)):
    """获取id信息"""
    logger.info(f"/api/name - id_name: {id_name}")

    try:
        # 获取path
        check_query = "SELECT id,code,path,file,resolution FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")

        path = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"path: {path}")

        resolution = local_file['resolution']
        # logger.debug(f"resolution: {resolution}")

        idinfo = {
            "path": path,
            "resolution": resolution,
        }
        # base58 加密
        base_bytes = base58.b58encode(json.dumps(idinfo).encode())
        # logger.debug(f"path_bytes: {base_bytes}")
        base_str = bytes.decode(base_bytes)
        # logger.debug(f"base_str: {base_str}")

        logger.success(f"Get video successful! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": base_str,
        }
    except Exception as e:
        logger.error(f"/api/name - id_name: {id_name} - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## rename
@router.get("/rename/{id_name}/{new_base_name}")
async def file_rename(id_name: str, new_base_name: str, cursor=Depends(get_db)):
    """重命名"""
    logger.info(f"/api/rename - id_name: {id_name}")

    try:
        if not new_base_name:
            logger.warning(f"Name cannot be empty: {id_name}")
            return HTMLResponse("Name cannot be empty", status_code=402)

        # 获取 srcpath
        check_query = "SELECT path,file FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:
            logger.warning(f"Database not found: {id_name}")
            return HTMLResponse("Database not found", status_code=404)
        srcpath = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"rename path: {srcpath}")
        srcfile = local_file['file']
        # logger.debug(f"srcfile: {srcfile}")

        src_path = Path(srcpath)
        # logger.debug(f"rename src_path: {src_path}")
        if not src_path.exists():
            logger.warning(f"Video not found: {id_name}")
            return HTMLResponse("Video not found", status_code=404)

        # base58 解密 dstpath
        # logger.debug(f"base_name: {new_base_name}")
        path_bytes = base58.b58decode(new_base_name)
        # logger.debug(f"path_bytes: {path_bytes}")
        dstpath = bytes.decode(path_bytes)
        logger.debug(f"dstpath: {dstpath}")

        dstfile = os.path.basename(dstpath)
        # logger.debug(f"dstfile: {dstfile}")
        dstname = os.path.splitext(dstfile)[0]
        dstcode = dstname.split(' ')[0] # 获取识别码

        dst_path = Path(dstpath)
        logger.debug(f"rename dst_path: {dst_path}")

        if dst_path.exists():
            logger.warning(f"File already exists: {id_name}")
            return HTMLResponse("File already exists", status_code=401)

        # 文件名一样不用修改
        if srcfile == dstfile:
            logger.warning(f"No need to modify: {id_name}")
            return HTMLResponse("No need to modify", status_code=402)
        if dstfile == 'null':
            logger.warning(f"Target is empty: {id_name}")
            return HTMLResponse("Target is empty", status_code=402)

        # 修改文件名
        os.rename(src_path, dst_path)

        # 修改数据库
        update_query = "UPDATE dav_local SET code=%s,name=%s,file=%s,updated_time=NOW() WHERE id=%s"
        values = (dstcode, dstname, dstfile, id_name,)
        if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?').replace('NOW()','CURRENT_TIMESTAMP')
        logger.debug(f"update_query: {update_query} values: {values}")
        await cursor.execute(update_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()

        logger.success(f"File rename successful! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "File rename successful!",
        }
    except Exception as e:
        logger.error(f"/api/rename - id_name: {id_name} - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## web rename
@router.get("/webname/{id_name}")
async def file_webname(id_name: str, cursor=Depends(get_db)):
    """网络重命名"""
    logger.info(f"/api/webname - id_name: {id_name}")

    try:
        # 获取 srcpath
        check_query = "SELECT code,path,file FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:
            logger.warning(f"Database not found: {id_name}")
            return HTMLResponse("Database not found", status_code=404)
        srcpath = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"rename path: {srcpath}")
        srcfile = local_file['file']
        # logger.debug(f"srcfile: {srcfile}")

        src_path = Path(srcpath)
        # logger.debug(f"rename src_path: {src_path}")
        if not src_path.exists():
            logger.warning(f"Video not found: {id_name}")
            return HTMLResponse("Video not found", status_code=404)

        # ------------------------------------------------------
        code_name = local_file['code']
        if len(code_name) == 0:
            logger.error(f"Not Code")
            return {
                "code": 404,
                "success": False,
                "msg": "Not Code",
            }
        # logger.debug(f"code_name: {code_name}")
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
        # ------------------------------------------------------

        to_extend = os.path.splitext(srcfile)[1].lower()
        dstname = code_info['name'].replace('/', ' ')
        dstcode = dstname.split(' ')[0] # 获取识别码
        dstfile = f"{dstname}{to_extend}"
        dstpath = os.path.join(local_file['path'], dstfile)
        logger.debug(f"dstpath: {dstpath}")

        dst_path = Path(dstpath)
        logger.debug(f"rename dst_path: {dst_path}")
        if dst_path.exists():
            logger.warning(f"File already exists: {id_name}")
            return HTMLResponse("File already exists", status_code=401)

        # 文件名一样不用修改
        if srcfile == dstfile:
            logger.warning(f"No need to modify: {id_name}")
            return HTMLResponse("No need to modify", status_code=402)
        if dstfile == 'null':
            logger.warning(f"Target is empty: {id_name}")
            return HTMLResponse("Target is empty", status_code=402)

        # 修改文件名
        os.rename(src_path, dst_path)

        # 修改数据库
        update_query = "UPDATE dav_local SET code=%s,name=%s,file=%s,updated_time=NOW() WHERE id=%s"
        values = (dstcode, dstname, dstfile, id_name,)
        if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?').replace('NOW()','CURRENT_TIMESTAMP')
        logger.debug(f"update_query: {update_query} values: {values}")
        await cursor.execute(update_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()

        logger.success(f"File webname successful! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "File webname successful!",
        }
    except Exception as e:
        logger.error(f"/api/webname - id_name: {id_name} - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## key rename
@router.get("/keyname/{old_key}/{new_key}")
async def file_keyname(old_key: str, new_key: str, cursor=Depends(get_db)):
    """批量重命名:关键字替换"""
    logger.info(f"/api/keyname - key_name: {old_key} => {new_key}")

    try:
        if len(old_key) < 2:
            logger.warning(f"The number of old_key is greater than 2: {old_key}")
            return HTMLResponse("The number of old_key is greater than 2", status_code=402)

        # 获取匹配的文件列表
        check_query = "SELECT id,code,name,path,file FROM dav_local WHERE INSTR(UPPER(file), UPPER(%s))>0"
        values = (old_key,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        await cursor.execute(check_query, values)
        local_files = await cursor.fetchall()
        local_files_len = len(local_files)
        logger.debug(f"find {old_key} - {local_files_len} {local_files[0] if local_files_len>0 else ''}")
        
        if local_files_len == 0:
            return {
                "code": 200,
                "success": True,
                "msg": "Success",
                "data": "No files matched the criteria",
            }
        
        file_count = 0  # 成功处理的文件计数
        updated_records = []  # 存储需要更新的记录
        
        for local_file in local_files:
            # 如果是元组，转换为字典
            if isinstance(local_file, tuple):
                local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
            
            id_name = local_file['id']
            srcfile = local_file['file']
            srcpath = os.path.join(local_file['path'], srcfile)
            
            src_path = Path(srcpath)
            if not src_path.exists():
                logger.warning(f"Video not found: {srcpath}")
                continue
            
            # 只替换文件名部分，避免替换路径中的匹配项
            dstfile = srcfile.replace(old_key, new_key)
            dstpath = os.path.join(local_file['path'], dstfile)
            dst_path = Path(dstpath)
            
            if dst_path.exists():
                logger.warning(f"File already exists: {dstpath}")
                continue

            # 文件名一样不用修改
            if srcfile == dstfile:
                logger.warning(f"No need to modify: {old_key}")
                continue
            if dstfile == 'null':
                logger.warning(f"Target is empty: {old_key}")
                continue

            # 记录需要更新的信息
            dstname = os.path.splitext(dstfile)[0]
            updated_records.append((dstname, dstfile, id_name, src_path, dst_path))
            file_count += 1
        
        # 批量更新数据库和文件系统
        success_count = 0
        for dstname, dstfile, id_name, src_path, dst_path in updated_records:
            try:
                # 修改数据库
                update_query = "UPDATE dav_local SET name=%s,file=%s,updated_time=NOW() WHERE id=%s"
                values = (dstname, dstfile, id_name,)
                if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?').replace('NOW()','CURRENT_TIMESTAMP')
                await cursor.execute(update_query, values)
                
                # 修改文件名
                os.rename(src_path, dst_path)
                
                success_count += 1
                logger.success(f"File rename successful! id: {id_name} - {success_count}/{file_count}")
            except Exception as e:
                logger.error(f"Failed to rename file {src_path}: {str(e)}")
                # 如果需要严格模式，可以在这里回滚或者抛出异常
        
        # 统一提交数据库更改
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()
        
        # 关键字是否存在: 不存在则入库, 存在则将更新次数
        check_query = "SELECT id FROM dav_keyword WHERE `old_key`=%s and status=0 and id>0"
        values = (old_key,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        recoed_keys = await cursor.fetchone()
        logger.debug(f"recoed_keys: {recoed_keys}")
        if recoed_keys:
            # 更新搜索次数
            update_query = "UPDATE dav_keyword SET count=(count+1) WHERE `old_key`=%s"
            values = (old_key,)
            if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?')
            # logger.debug(f"update_query: {update_query} values: {values}")
            await cursor.execute(update_query, values)
        else:
            # 插入搜索记录
            insert_query = "INSERT INTO dav_keyword (`old_key`, `new_key`, count) VALUES (%s, %s, %s)"
            values = (old_key, new_key, 1,)
            if DB_ENGINE == "sqlite": insert_query = insert_query.replace('%s','?')
            # logger.debug(f"insert_query: {insert_query} values: {values}")
            await cursor.execute(insert_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()
        
        logger.success(f"Batch file rename completed! Success: {success_count}/{file_count}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": f"File rename successful! {success_count}/{file_count}",
        }
    except Exception as e:
        logger.error(f"/api/keyname - key_name: {old_key} - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}
        # 尝试回滚数据库更改
        try:
            if DB_ENGINE == "sqlite": cursor.connection.rollback()
            else: await cursor.connection.rollback()
        except:
            pass
        return {"code": 500, "success": False, "msg": "Server error"}


## delete
@router.get("/delete/{id_name}")
async def file_delete(id_name: str, pwd: str, cursor=Depends(get_db)):
    """删除 删除本地文件和数据库"""
    logger.info(f"/api/delete - id_name: {id_name}")

    try:
        # base58 解密 pwd
        # logger.debug(f"pwd: {pwd}")
        pwd_bytes = base58.b58decode(pwd)
        # logger.debug(f"pwd_bytes: {pwd_bytes}")
        actionpwd = bytes.decode(pwd_bytes)
        logger.debug(f"actionpwd: {actionpwd}")
        # 验证密码是否正确
        if actionpwd != APP_ACTION_PASSWD:
            logger.error(f"clear_db - ERROR: Password verification failed")
            return {"code": 400, "success": False, "msg": "Password verification failed"}
        
        # 获取path
        check_query = "SELECT id,code,path,file,status FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:  # 数据库未找到
            logger.warning(f"Database not found: {id_name}")
            return {"code": 400, "success": False, "msg": "Database not found"}

        path = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"delete path: {path}")
        status = local_file['status']
        logger.debug(f"status: {status}")

        if status == 1:  # 数据库已删除
            logger.warning(f"Database deleted: {id_name}")
            return {"code": 400, "success": False, "msg": "Database deleted"}
        # 数据库删除
        update_query = "UPDATE dav_local SET status=1, updated_time=NOW() WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?').replace('NOW()','CURRENT_TIMESTAMP')
        logger.debug(f"update_query: {update_query} values: {values}")
        await cursor.execute(update_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()

        # 删除文件
        try:
            if not os.path.exists(path):  # 文件不存在
                logger.warning(f"File not found: {path}")
                return {"code": 400, "success": False, "msg": "File not found"}
            # 删除文件    
            os.remove(path)
            logger.info(f"File {path} remove successfully.")
        except OSError as e:
            logger.error(f"File remove Error: {e}")

        # 计算hash
        video_hash = hashlib.sha256(path.encode()).hexdigest()
        thumbnail_path = f"{TEMP_PATH}/{video_hash}.png"
        # 删除缩略图
        try:
            if not os.path.exists(thumbnail_path):  # 文件不存在
                logger.warning(f"Thumbnail not found: {thumbnail_path}")
                return {"code": 400, "success": False, "msg": "File not found"}
            # 删除文件
            os.remove(thumbnail_path)
            logger.info(f"Thumbnail {thumbnail_path} remove successfully.")
        except OSError as e:
            logger.error(f"Thumbnail remove Error: {e}")

        logger.success(f"File deleted successful! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "File deleted successfully"
        }
    except Exception as e:
        logger.error(f"/api/delete - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## thumbnail
@router.get("/thumbnail/{id_name}")
async def file_syncthumbnail(id_name: str, cursor=Depends(get_db)):
    """删除缩略图"""
    logger.info(f"/api/syncthumbnail - id_name: {id_name}")

    try:
        # 获取path
        check_query = "SELECT id,code,path,file,status FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:  # 数据库未找到
            logger.warning(f"Database not found: {id_name}")
            return {"code": 400, "success": False, "msg": "Database not found"}

        path = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"path: {path}")
        
        # 计算hash
        video_hash = hashlib.sha256(path.encode()).hexdigest()
        thumbnail_path = f"{TEMP_PATH}/{video_hash}.png"
        # 删除缩略图
        try:
            if not os.path.exists(thumbnail_path):  # 文件不存在
                logger.warning(f"Thumbnail not found: {thumbnail_path}")
                return {"code": 400, "success": False, "msg": "File not found"}
            # 删除文件
            os.remove(thumbnail_path)
            logger.info(f"Thumbnail {thumbnail_path} remove successfully.")
        except OSError as e:
            logger.error(f"Thumbnail remove Error: {e}")

        logger.success(f"Thumbnail deleted successful! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Thumbnail deleted successfully"
        }
    except Exception as e:
        logger.error(f"/api/syncthumbnail - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## cut
@router.get("/cut/{id_name}/{second}")
async def file_cut(id_name: str, second: str, cursor=Depends(get_db)):
    """剪切 文件截取"""
    logger.info(f"/api/cut - id_name: {id_name}")

    try:
        # 获取path
        check_query = "SELECT id,code,path,file,status FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:  # 数据库未找到
            logger.warning(f"Database not found: {id_name}")
            return {"code": 400, "success": False, "msg": "Database not found"}

        frompath = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"cut path: {frompath} second: {second}")
        to_name = os.path.splitext(frompath)[0]
        to_extend = os.path.splitext(frompath)[1]
        topath = to_name + '-cut' + to_extend
        # logger.debug(f"frompath: {frompath} => topath: {topath}")

        # 获取视频时长
        file_duration = get_video_duration(frompath)
        logger.debug(f"duration: {file_duration}")
        if file_duration == 0.0:
            logger.error(f"Duration parsing error: Invalid sample size - {frompath}")
            return {"code": 400, "success": False, "msg": "Duration parsing error: Invalid sample size"}

        # # sql队列 - 视频剪切
        # 任务是否存在
        check_query = "SELECT id,status FROM dav_missions WHERE localid=%s and path=%s and file=%s and type=%s"
        values = (id_name, local_file['path'], local_file['file'], 1,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        exist_mission = await cursor.fetchone()
        if exist_mission:
            logger.success(f"File existting! id: {id_name} - {second}")
            return {
                "code": 200,
                "success": True,
                "msg": "Success",
                "data": "Video cutting in progress!" if exist_mission['status'] == 1 else "Video cutting completed!"
            }
        
        # 插入剪切任务
        insert_query = "INSERT INTO dav_missions (localid, path, file, type, start, end) VALUES (%s, %s, %s, %s, %s, %s) "
        values = (id_name, local_file['path'], local_file['file'], 1, int(second), 0,)
        if DB_ENGINE == "sqlite": insert_query = insert_query.replace('%s','?')
        logger.debug(f"insert_query: {insert_query} values: {values}")
        await cursor.execute(insert_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()
        
        logger.success(f"Video cutting in progress! id: {id_name} - {second}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Video cutting in progress!"
        }
    except Exception as e:
        logger.error(f"/api/cut - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## score
@router.get("/score/{id_name}/{stars}")
async def file_star(id_name: str, stars: str, cursor=Depends(get_db)):
    """文件评分"""
    logger.info(f"/api/score - id_name: {id_name}")

    try:
        # 获取path
        check_query = "SELECT id,code,path,file,status FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:  # 数据库未找到
            logger.warning(f"Database not found: {id_name}")
            return {"code": 400, "success": False, "msg": "Database not found"}

        frompath = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"score path: {frompath} stars: {stars}")

        # ------------------------------------------------------
        code_name = local_file['code']
        if len(code_name) == 0:
            logger.error(f"Not Code")
            return {
                "code": 404,
                "success": False,
                "msg": "Not Code",
            }
        # logger.debug(f"code_name: {code_name}")
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
        # ------------------------------------------------------
        
        # 修改数据库
        update_query = "UPDATE dav_web SET score=%s,updated_time=NOW() WHERE code=%s"
        values = (stars, code_name,)
        if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?').replace('NOW()','CURRENT_TIMESTAMP')
        logger.debug(f"update_query: {update_query} values: {values}")
        await cursor.execute(update_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()

        logger.success(f"id: {id_name} - score: {stars}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Score successful"
        }
    except Exception as e:
        logger.error(f"/api/score - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## transcode
@router.get("/transcode/{id_name}")
async def file_transcode(id_name: str, cursor=Depends(get_db)):
    """视频转码"""
    logger.info(f"/api/transcode - id_name: {id_name}")

    try:
        # 获取path
        check_query = "SELECT id,code,path,file,status FROM dav_local WHERE id=%s"
        values = (id_name,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_file = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(local_file, tuple):
            local_file = dict(zip([desc[0] for desc in cursor.description], local_file))
        # logger.debug(f"local_file: {local_file}")
        if local_file is None:  # 数据库未找到
            logger.warning(f"Database not found: {id_name}")
            return {"code": 400, "success": False, "msg": "Database not found"}

        frompath = os.path.join(local_file['path'], local_file['file'])
        logger.debug(f"transcode path: {frompath}")

        # 获取视频时长
        file_duration = get_video_duration(frompath)
        logger.debug(f"duration: {file_duration}")
        if file_duration == 0.0:
            logger.error(f"Duration parsing error: Invalid sample size - {frompath}")
            return {"code": 400, "success": False, "msg": "Duration parsing error: Invalid sample size"}

        # # sql队列 - 视频转码
        # 任务是否存在
        check_query = "SELECT id,status FROM dav_missions WHERE localid=%s and path=%s and file=%s and type=%s"
        values = (id_name, local_file['path'], local_file['file'], 2,)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        exist_mission = await cursor.fetchone()
        if exist_mission:
            logger.success(f"File existting! id: {id_name}")
            return {
                "code": 200,
                "success": True,
                "msg": "Success",
                "data": "Video transcoding in progress!" if exist_mission[1] == 1 else "Video transcoding completed!"
            }
        
        # 插入转码任务
        insert_query = "INSERT INTO dav_missions (localid, path, file, type) VALUES (%s, %s, %s, %s) "
        values = (id_name, local_file['path'], local_file['file'], 2,)
        if DB_ENGINE == "sqlite": insert_query = insert_query.replace('%s','?')
        logger.debug(f"insert_query: {insert_query} values: {values}")
        await cursor.execute(insert_query, values)
        if DB_ENGINE == "sqlite": cursor.connection.commit()
        else: await cursor.connection.commit()
        
        logger.success(f"Video transcoding in progress! id: {id_name}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Video transcoding in progress!"
        }
    except Exception as e:
        logger.error(f"/api/transcode - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## scan
@router.get("/scan")
async def folder_scan(background_tasks: BackgroundTasks, path: str | None='all', cursor=Depends(get_db)):
    """扫盘 更新本地数据库"""
    logger.info(f"/api/scan - path: {path}")

    try:
        if path == '' or path == 'all':
            localpaths = SCAN_PATH
        else:
            # base58 解密 path
            # logger.debug(f"path: {path}")
            path_bytes = base58.b58decode(path)
            # logger.debug(f"path_bytes: {path_bytes}")
            path = bytes.decode(path_bytes)
            logger.debug(f"path: {path}")
            localpaths = [path]
        
        # 后台任务 - 扫盘
        background_tasks.add_task(
            sync_scan_path,
            cursor=cursor,
            localpaths=localpaths,
        )

        logger.success(f"Folder scanning! localpaths: {localpaths}")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Folder scanning!",
        }
    except Exception as e:
        logger.error(f"/api/scan - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## sync
@router.get("/syncthumbnail")
async def sync_thumbnail(background_tasks: BackgroundTasks, path: str | None='all', cursor=Depends(get_db)):
    """同步缩略图"""
    logger.info(f"/api/syncthumbnail")

    try:
        if path == '' or path == 'all':
            localpaths = SCAN_PATH
        else:
            # base58 解密 path
            # logger.debug(f"path: {path}")
            path_bytes = base58.b58decode(path)
            # logger.debug(f"path_bytes: {path_bytes}")
            path = bytes.decode(path_bytes)
            logger.debug(f"path: {path}")
            localpaths = [path]

        ## 搜索列表
        if len(localpaths) > 1:
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and id>0 ORDER BY code ASC"
            values = ()
        else:
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE path=%s and status=0 and id>0 ORDER BY code ASC"
            values = (localpaths[0],)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_files = await cursor.fetchall()
        # 如果是元组，转换为字典
        if local_files and isinstance(local_files[0], tuple):
            columns = [desc[0] for desc in cursor.description]
            local_files = [dict(zip(columns, row)) for row in local_files]
        # logger.debug(f"local_files: {local_files}")

        # 后台任务 - 批量生成视频预览图
        background_tasks.add_task(
            sync_generate_thumbnails,
            local_files=local_files,
        )

        logger.success(f"Thumbnail syncing!")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Thumbnail syncing!",
        }
    except Exception as e:
        logger.error(f"/api/syncthumbnail - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}


## clear
@router.get("/cleardb")
async def clear_db(pwd: str, cursor=Depends(get_db)):
    """清空 初始化本地数据库"""
    logger.info(f"/api/cleardb")

    try:
        # base58 解密 pwd
        # logger.debug(f"pwd: {pwd}")
        pwd_bytes = base58.b58decode(pwd)
        # logger.debug(f"pwd_bytes: {pwd_bytes}")
        actionpwd = bytes.decode(pwd_bytes)
        logger.debug(f"actionpwd: {actionpwd}")
        # 验证密码是否正确
        if actionpwd != APP_ACTION_PASSWD:
            logger.error(f"clear_db - ERROR: Password verification failed")
            return {"code": 400, "success": False, "msg": "Password verification failed"}
        
        # 清空数据表
        if DB_ENGINE == "sqlite": 
            # 清空表,重置自增主键计数器
            # dav_local
            delete_query = "DELETE FROM dav_local"
            logger.debug(f"delete_query: {delete_query}")
            await cursor.execute(delete_query)
            update_query = "UPDATE sqlite_sequence SET seq=0 WHERE name='dav_local'"
            logger.debug(f"update_query: {update_query}")
            await cursor.execute(update_query)
            # dav_missions
            delete_query = "DELETE FROM dav_missions"
            logger.debug(f"delete_query: {delete_query}")
            await cursor.execute(delete_query)
            update_query = "UPDATE sqlite_sequence SET seq=0 WHERE name='dav_missions'"
            logger.debug(f"update_query: {update_query}")
            await cursor.execute(update_query)
            cursor.connection.commit()
        else:
            # dav_local
            delete_query = "truncate table dav_local"
            logger.debug(f"delete_query: {delete_query}")
            await cursor.execute(delete_query)
            # dav_missions
            delete_query = "truncate table dav_missions"
            logger.debug(f"delete_query: {delete_query}")
            await cursor.execute(delete_query)
            await cursor.connection.commit()
        logger.debug(f"TEMP_PATH: {TEMP_PATH}")

        # 删除 TEMP2_PATH
        if os.path.exists(TEMP2_PATH):
            shutil.rmtree(TEMP2_PATH)
        # 备份 TEMP_PATH 到 TEMP2_PATH
        os.rename(TEMP_PATH, TEMP2_PATH)
        if not os.path.exists(TEMP_PATH): os.mkdir(TEMP_PATH)

        logger.success(f"Database cleanup successful!")
        return {
            "code": 200,
            "success": True,
            "msg": "Success",
            "data": "Database cleanup successful!"
        }
    except Exception as e:
        logger.error(f"/api/cleardb - except ERROR: {str(e)}")
        return {"code": 500, "success": False, "msg": "Server error"}

