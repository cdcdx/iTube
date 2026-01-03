# routes/frontend.py
import os
import base58
import ffmpeg
from pathlib import Path
from utils.log import log as logger
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse

from utils.db import get_db
from utils.security import get_current_username
from utils.local import is_mobile, generate_thumbnails
from config import APP_TITLE, APP_PAGE_LIMIT, SCAN_CODE, SCAN_PATH, DB_ENGINE, templates, TEMP_PATH


router = APIRouter()


# frontend html
## favicon.ico
@router.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/frontend/static/images/favicon.ico")


## ca.crt
@router.get("/ca.crt")
async def ca_crt():
    return RedirectResponse(url="/ssl/ca.crt")


## index.html
@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, query: str = None, page: int | None = 0, username=Depends(get_current_username), cursor=Depends(get_db)):
    """加载主页"""
    limit = APP_PAGE_LIMIT
    logger.info(f"/?page={page}&query={query} - query: {query} / page: {page} limit: {limit}")

    try:
        # logger.info(f"Accessing root path with headers: {request.headers}")
        
        mobile = is_mobile(request)
        # SCAN_PATH转base58
        scan_paths=[]
        for scan_path in SCAN_PATH:
            # base58 加密
            localpath_bytes=base58.b58encode(scan_path.encode('UTF-8'))
            # logger.debug(f"localpath_bytes: {localpath_bytes}")
            localpath = bytes.decode(localpath_bytes)
            # logger.debug(f"localpath: {localpath}")
            scan_paths.append(localpath)
        logger.debug(f"scan_paths: {scan_paths}")
        # 搜索记录
        check_query = "SELECT `key` FROM dav_search WHERE id>0 and status=0 order by `type`,`key` asc" # limit 20"
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query}")
        await cursor.execute(check_query)
        keys_tuple = await cursor.fetchall()
        # logger.debug(f"keys_tuple: {keys_tuple}")
        search_keys=[]
        # ## 如果是元组，转换为数组
        for key in keys_tuple:
            search_keys.append(key[0])
        # logger.debug(f"search_keys: {search_keys}")

        ## 搜索数量
        if query in ['all','all2','all3']:
            check_query = "SELECT count(*) as len FROM dav_local WHERE status=0 and id>0"
            values = ()
        elif query == 'repeat':
            if SCAN_CODE:
                check_query = "SELECT count(*) as len FROM dav_local, (SELECT * FROM (SELECT code,count(*) as count FROM dav_local WHERE status=0 GROUP BY code ORDER BY count DESC)as aaa WHERE aaa.count > 1) as bbb WHERE bbb.code = dav_local.code and dav_local.status=0"
            else:
                check_query = "SELECT count(*) as len FROM dav_local, (SELECT * FROM (SELECT file,count(*) as count FROM dav_local WHERE status=0 GROUP BY file ORDER BY count DESC)as aaa WHERE aaa.count > 1) as bbb WHERE bbb.file = dav_local.file and dav_local.status=0"
            values = ()
        elif query == 'nojapan':
            check_query = "SELECT count(*) as len FROM dav_local WHERE status=0 and file NOT GLOB '*[あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン]*'"
            values = ()
        elif query:
            if '*' in query:
                query_parts = query.split('*')
            else:
                query_parts = query.split()
            # logger.info(f"query_parts: {query_parts} len: {len(query_parts)}")
            conditions = " AND ".join([f"INSTR(UPPER(file), UPPER(%s))>0" for _ in query_parts])
            check_query = f"SELECT count(*) as len FROM dav_local WHERE status=0 and {conditions}"
            values = tuple(query_parts)
        else:
            check_query = "SELECT count(*) as len FROM dav_local WHERE status=0 and id=0"
            values = ()
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        len_files = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(len_files, tuple):
            len_files = dict(zip([desc[0] for desc in cursor.description], len_files))
        logger.debug(f"len_files: {len_files}")

        count = len_files['len']
        logger.info(f"count: {count}")
        if count == 0:
            return templates.TemplateResponse("index.html", {
                "title": query,
                "apptitle": APP_TITLE,
                "request": request,
                "results": [],
                "paths": scan_paths,
                "keys": search_keys,
                "query": query,
                "mobile": mobile,
            })

        ## 第一次搜索入库 若含有'-'/'_'/' '/纯数字/则不入库
        if page == 0 and (query.find('-') < 0 and query.find('_') < 0 and query.find(' ') < 0 and query.isdigit() == False and query not in ['all','all2','all3','repeat','trans','transcode',''] ):
            # 关键字是否存在: 不存在则入库, 存在则将更新次数
            check_query = "SELECT id FROM dav_search WHERE `key`=%s and status=0 and id>0"
            values = (query,)
            if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
            logger.debug(f"check_query: {check_query} values: {values}")
            await cursor.execute(check_query, values)
            recoed_keys = await cursor.fetchone()
            logger.debug(f"recoed_keys: {recoed_keys}")
            if recoed_keys:
                # 更新搜索次数
                update_query = "UPDATE dav_search SET count=(count+1) WHERE `key`=%s"
                values = (query,)
                if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?')
                # logger.debug(f"update_query: {update_query} values: {values}")
                await cursor.execute(update_query, values)
            else:
                # 插入搜索记录
                insert_query = "INSERT INTO dav_search (`key`, `type`, count) VALUES (%s, %s, %s)"
                values = (query, 1, 1,)
                if DB_ENGINE == "sqlite": insert_query = insert_query.replace('%s','?')
                # logger.debug(f"insert_query: {insert_query} values: {values}")
                await cursor.execute(insert_query, values)
            if DB_ENGINE == "sqlite": cursor.connection.commit()
            else: await cursor.connection.commit()

        ## 搜索列表
        if page == 0: page = 1
        if count < limit * page:
            alimit = count - limit * (page - 1)
        else:
            alimit = limit
        if query == 'all':
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and id>0 ORDER BY code ASC LIMIT %s,%s"
            values = (limit * (page - 1), alimit,)
        elif query == 'all2':
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and id>0 ORDER BY created ASC LIMIT %s,%s"
            values = (limit * (page - 1), alimit,)
        elif query == 'all3':
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and id>0 ORDER BY id ASC LIMIT %s,%s"
            values = (limit * (page - 1), alimit,)
        elif query == 'repeat':
            if SCAN_CODE:
                check_query = "SELECT dav_local.id,dav_local.code,dav_local.path,dav_local.file,dav_local.size,dav_local.duration,dav_local.aspectratio,dav_local.resolution,dav_local.created FROM dav_local, (SELECT * FROM (SELECT code,count(*) as count FROM dav_local WHERE status=0 GROUP BY code ORDER BY count DESC)as aaa WHERE aaa.count > 1) as bbb WHERE bbb.code = dav_local.code and dav_local.status=0 ORDER BY dav_local.code,dav_local.file ASC LIMIT %s,%s"
            else:
                check_query = "SELECT dav_local.id,dav_local.code,dav_local.path,dav_local.file,dav_local.size,dav_local.duration,dav_local.aspectratio,dav_local.resolution,dav_local.created FROM dav_local, (SELECT * FROM (SELECT file,count(*) as count FROM dav_local WHERE status=0 GROUP BY file ORDER BY count DESC)as aaa WHERE aaa.count > 1) as bbb WHERE bbb.file = dav_local.file and dav_local.status=0 ORDER BY dav_local.file ASC LIMIT %s,%s"
            values = (limit * (page - 1), alimit,)
        elif query == 'nojapan':
            check_query = "SELECT dav_local.id,dav_local.code,dav_local.path,dav_local.file,dav_local.size,dav_local.duration,dav_local.aspectratio,dav_local.resolution,dav_local.created FROM dav_local WHERE status=0 and file NOT GLOB '*[あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン]*' ORDER BY dav_local.file ASC LIMIT %s,%s"
            values = (limit * (page - 1), alimit,)
        elif query:
            if '*' in query:
                query_parts = query.split('*')
            else:
                query_parts = query.split()
            # logger.info(f"query_parts: {query_parts} len: {len(query_parts)}")
            conditions = " AND ".join([f"INSTR(UPPER(file), UPPER(%s))>0" for _ in query_parts])
            check_query = f"SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and {conditions} ORDER BY code ASC LIMIT %s,%s"
            values = tuple(query_parts) + (limit * (page - 1), alimit,)
        else:
            check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,created FROM dav_local WHERE status=0 and id=0 ORDER BY code ASC"
            values = ()
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        # logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        local_files = await cursor.fetchall()
        # 如果是元组，转换为字典
        if local_files and isinstance(local_files[0], tuple):
            columns = [desc[0] for desc in cursor.description]
            local_files = [dict(zip(columns, row)) for row in local_files]
        # logger.debug(f"local_files: {local_files}")

        for local_file in local_files:
            if local_file['aspectratio'] == 0 or local_file['aspectratio'] is None:
                local_file['aspectratio']=0.5625

        # 批量获取缩略图
        results = {'videos': [], 'count': 0}
        await generate_thumbnails(local_files, True) # isShow=True

        results['videos'] = local_files
        results['count'] = count
        results['limit'] = limit

        # logger.debug(f"results: {results}")
        return templates.TemplateResponse("index.html", {
            "title": query,
            "apptitle": APP_TITLE,
            "request": request,
            "results": results,
            "paths": scan_paths,
            "keys": search_keys,
            "query": query,
            "mobile": mobile,
        })
    except Exception as e:
        logger.error(f"/?page={page}&query={query} - except ERROR: {str(e)}")
        return HTMLResponse("Server error", status_code=500)
        # return {"code": 500, "success": False, "msg": "Server error"}


## video.html
@router.get("/video/{id_name}", response_class=HTMLResponse)
async def play_video(request: Request, id_name: str, cursor=Depends(get_db)):
    """加载视频页"""
    logger.info(f"/video/{id_name} - id_name: {id_name}")

    try:
        mobile = is_mobile(request)
        # SCAN_PATH转base58
        scan_paths=[]
        for scan_path in SCAN_PATH:
            # base58 加密
            localpath_bytes=base58.b58encode(scan_path.encode('UTF-8'))
            # logger.debug(f"localpath_bytes: {localpath_bytes}")
            localpath = bytes.decode(localpath_bytes)
            # logger.debug(f"localpath: {localpath}")
            scan_paths.append(localpath)
        logger.debug(f"scan_paths: {scan_paths}")
        # 搜索记录
        check_query = "SELECT `key` FROM dav_search WHERE id>0 and status=0 order by `type`,`key` asc" # limit 20"
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        logger.debug(f"check_query: {check_query}")
        await cursor.execute(check_query)
        keys_tuple = await cursor.fetchall()
        # logger.debug(f"keys_tuple: {keys_tuple}")
        search_keys=[]
        # ## 如果是元组，转换为数组
        for key in keys_tuple:
            search_keys.append(key[0])
        # logger.debug(f"search_keys: {search_keys}")

        ## 数量
        check_query = "SELECT count(*) as len FROM dav_local WHERE status=0 and id>0"
        values = ()
        await cursor.execute(check_query, values)
        len_files = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(len_files, tuple):
            len_files = dict(zip([desc[0] for desc in cursor.description], len_files))
        # logger.debug(f"len_files: {len_files}")
        count = len_files['len']
        logger.info(f"count: {count}")
        if count == 0:
            logger.warning(f"Database is empty: {id_name}")
            return HTMLResponse("Database is empty", status_code=404)

        # 获取path
        check_query = "SELECT id,code,path,file,size,duration,aspectratio,resolution,format,created FROM dav_local WHERE id=%s"
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

        path = os.path.join(local_file['path'], local_file['file'])
        # logger.debug(f"path: {path}")

        video_path = Path(path)
        # logger.debug(f"video_path: {video_path}")
        if not video_path.exists():
            logger.warning(f"Video not found: {id_name}")
            return HTMLResponse("Video not found", status_code=404)

        if local_file['format'] is None or local_file['format'] == "":
            # 使用 ffmpeg 获取视频信息
            try:
                probe = ffmpeg.probe(video_path)
                video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                logger.debug(f"video_info: {video_info}")
                video_format = probe['format']
                logger.debug(f"video_format: {video_format}")
                video_format_name = video_format['format_name']
                logger.debug(f"video_format_name: {video_format_name}")
            except ffmpeg.Error as e:
                video_format_name = ""
                logger.error(f"FFmpeg error: {e.stderr.decode()}")
                return HTMLResponse("Error processing video", status_code=500)
            # 更新数据库格式字段
            update_query = "UPDATE dav_local SET format=%s WHERE id=%s"
            values = (video_format_name, id_name,)
            if DB_ENGINE == "sqlite": update_query = update_query.replace('%s','?')
            # logger.debug(f"update_query: {update_query} values: {values}")
            await cursor.execute(update_query, values)
            if DB_ENGINE == "sqlite": cursor.connection.commit()
            else: await cursor.connection.commit()
            local_file['format'] = video_format_name

        # base58 加密
        path_bytes = base58.b58encode(path.encode('UTF-8'))
        # logger.debug(f"path_bytes: {path_bytes}")
        path_base = bytes.decode(path_bytes)
        # logger.debug(f"path_base: {path_base}")
        local_file['base'] = path_base
        
        if local_file['aspectratio'] == 0 or local_file['aspectratio'] is None:
            local_file['aspectratio']=0.5625
        
        # 关键字是否存在: 不存在则入库, 存在则将更新次数
        check_query = "SELECT score FROM dav_web WHERE `code`=%s and status=0"
        values = (local_file['code'],)
        if DB_ENGINE == "sqlite": check_query = check_query.replace('%s','?')
        logger.debug(f"check_query: {check_query} values: {values}")
        await cursor.execute(check_query, values)
        score_keys = await cursor.fetchone()
        # 如果是元组，转换为字典
        if isinstance(score_keys, tuple):
            score_keys = dict(zip([desc[0] for desc in cursor.description], score_keys))
        logger.debug(f"score_keys: {score_keys}")
        local_file['score'] = score_keys['score'] if score_keys else 0
        
        results = dict(videos=[])
        results['videos'] = local_file
        results['count'] = count

        logger.debug(f"results: {results}")
        return templates.TemplateResponse("video.html", {
            "title": local_file['code'],
            "apptitle": APP_TITLE,
            "request": request,
            "results": results,
            "paths": scan_paths,
            "keys": search_keys,
            "id": id_name,
            "base": path_base,
            "mobile": mobile,
        })
    except Exception as e:
        logger.error(f"/video/{id_name} - except ERROR: {str(e)}")
        return HTMLResponse("Server error", status_code=500)
        # return {"code": 500, "success": False, "msg": "Server error"}

