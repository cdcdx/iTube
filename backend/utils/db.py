import os
import urllib
import aiosqlite
import aiomysql
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from fastapi import HTTPException

from utils.log import log as logger
from config import DB_ENGINE, SQLITE_URL, MYSQL_URL, MYSQL_MAXCONNECT, BASE_DIR

class Database(ABC):
    def __init__(self, url: str):
        self.url = url
        self.pool = None

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator:
        pass

class SQLiteDatabase(Database):
    def __init__(self, url: str):
        super().__init__(url)
        db_path = url.split("://")[1]
        if db_path.startswith('./'):
            self.url = os.path.join(BASE_DIR, db_path.replace('./', ''))
        else:
            self.url = db_path
        logger.info(f"SQLite URL: {self.url}")

    async def connect(self) -> None:
        if not os.path.exists(self.url):
            conn = await aiosqlite.connect(self.url, uri=True)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_local (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT DEFAULT '',
                    name         TEXT NOT NULL,
                    path         TEXT DEFAULT '',
                    file         TEXT DEFAULT '',
                    size         REAL DEFAULT 0.0,
                    created      DATETIME DEFAULT NULL,
                    duration     REAL DEFAULT 0.0,
                    aspectratio  REAL DEFAULT 0.0,
                    resolution   TEXT DEFAULT '',
                    format       TEXT DEFAULT '',
                    fps          REAL DEFAULT 0.0,
                    crc          TEXT DEFAULT '',
                    subtitle     TEXT DEFAULT '',
                    grade        INTEGER DEFAULT 0,
                    score        INTEGER DEFAULT 0,
                    comment      TEXT DEFAULT '',
                    status       INTEGER DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_search (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parid        INTEGER DEFAULT 0,
                    key          TEXT DEFAULT '',
                    type         INTEGER DEFAULT 0,
                    count        INTEGER DEFAULT 0,
                    status       INTEGER DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_keyword (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_key      TEXT DEFAULT '',
                    new_key      TEXT DEFAULT '',
                    count        INTEGER DEFAULT 0,
                    status       INTEGER DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    localid      INTEGER DEFAULT 0,
                    path         TEXT DEFAULT '',
                    file         TEXT DEFAULT '',
                    type         INTEGER DEFAULT 0,
                    start        INTEGER DEFAULT 0,
                    end          INTEGER DEFAULT 0,
                    preset       TEXT DEFAULT 'slow',
                    crf          INTEGER DEFAULT 15,
                    status       INTEGER DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_web (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT DEFAULT '',
                    name         TEXT NOT NULL,
                    date         TEXT DEFAULT '',
                    studio       TEXT DEFAULT '',
                    director        TEXT DEFAULT '',
                    series       TEXT DEFAULT '',
                    genre        TEXT DEFAULT '',
                    actors       TEXT DEFAULT '',
                    websites     TEXT DEFAULT '',
                    videos       TEXT DEFAULT '',
                    images       TEXT DEFAULT '',
                    magnet       TEXT DEFAULT '',
                    score        INTEGER DEFAULT 0,
                    comment      TEXT DEFAULT '',
                    status       INTEGER DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            await conn.commit()
            await conn.close()

        # 检查并更新表结构：为dav_local添加format字段
        conn = await aiosqlite.connect(self.url, uri=True)
        cursor = await conn.execute("PRAGMA table_info(dav_local)")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]
        if 'format' not in column_names:
            await conn.execute("""
                ALTER TABLE dav_local ADD COLUMN format TEXT DEFAULT ''
                """)
            await conn.commit()
        await conn.close()

        # 创建连接池
        self.pool = await aiosqlite.connect(self.url, uri=True, check_same_thread=False)

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        if self.pool is None:
            await self.connect()
        try:
            yield self.pool
        finally:
            pass  # SQLite 不需要显式关闭连接池中的连接

class MySQLDatabase(Database):
    def __init__(self, url: str):
        super().__init__(url)
        parsed_url = urllib.parse.urlparse(url)
        self.host = parsed_url.hostname
        self.port = parsed_url.port or 3306
        self.username = urllib.parse.unquote(parsed_url.username)
        self.password = urllib.parse.unquote(parsed_url.password)
        self.db = parsed_url.path.lstrip('/')
        logger.info(f"MySQL URL: host={self.host}, port={self.port}, user={self.username}, db={self.db}")

    async def connect(self) -> None:
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                db=self.db,
                maxsize=MYSQL_MAXCONNECT
            )
            # 连接成功后检查并创建表
            await self.create_tables()
        except aiomysql.Error as e:
            logger.error(f"Failed to connect to MySQL database: {e}")
            # 尝试创建数据库
            await self.create_database()
            # 重新尝试创建连接池
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                db=self.db,
                maxsize=MYSQL_MAXCONNECT
            )
            # 连接成功后检查并创建表
            await self.create_tables()

    async def create_database(self) -> None:
        try:
            async with aiomysql.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password
            ) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db}")
                    await conn.commit()
        except aiomysql.Error as e:
            logger.error(f"Failed to create MySQL database: {e}")
            raise HTTPException(status_code=500, detail="Failed to create database")

    async def create_tables(self) -> None:
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 检查表是否存在 dav_local
                    await cursor.execute("SHOW TABLES LIKE 'dav_local'")
                    table_exists = await cursor.fetchone()
                    if not table_exists:
                        # 表不存在，创建表
                        await cursor.execute("""
                            CREATE TABLE `dav_local`
                            (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                -- 识别码
                                `code`                  varchar(48)   DEFAULT ''    COMMENT '识别码',   -- XXX-000
                                `name`                  varchar(1024) NOT NULL      COMMENT '标题',     -- XXX-000 xxxxxx
                                -- 文件信息
                                `path`                  varchar(256)  DEFAULT ''    COMMENT '路径',     -- /nfs/hd01/
                                `file`                  varchar(1024) DEFAULT ''    COMMENT '文件',     -- XXX-000 xxxxxx.mp4
                                `size`                  float(16)     DEFAULT 0.0   COMMENT '大小',     -- 999 MByte
                                `created`               datetime      DEFAULT NULL  COMMENT '创建时间',
                                `duration`              float(16)     DEFAULT 0.0   COMMENT '时长',     -- 888 Second
                                `aspectratio`           float(16)     DEFAULT 0.0   COMMENT '宽高比',   -- 0.5625/0.75
                                `resolution`            varchar(16)   DEFAULT ''    COMMENT '分辨率',   -- 1080 720
                                `format`                varchar(32)   DEFAULT ''    COMMENT '格式',     -- mp4
                                `fps`                   float(16)     DEFAULT 0.0   COMMENT '帧率',     -- 30 60
                                `crc`                   varchar(32)   DEFAULT ''    COMMENT 'crc',     -- 3d91035d
                                -- 标记信息
                                `subtitle`              varchar(8)    DEFAULT NULL  COMMENT '字幕',    --  NULL/CN/JP/EN
                                `grade`                 int(4)        DEFAULT 0     COMMENT '等级',    --  -2 luan2/-1 luan/0 you/1 wu/2 good
                                -- 个人评论
                                `score`                 int(4)        DEFAULT 0     COMMENT '评分',    --  -10~0~10
                                `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist, 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                        await conn.commit()
                    # 检查表是否存在 dav_search 
                    await cursor.execute("SHOW TABLES LIKE 'dav_search'")
                    table_exists = await cursor.fetchone()
                    if not table_exists:
                        # 表不存在，创建表
                        await cursor.execute("""
                            CREATE TABLE `dav_search`
                            (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `parid`                 int           DEFAULT 0     COMMENT '父级ID', -- 0 nothing / other
                                `key`                   varchar(48)   DEFAULT ''    COMMENT '搜索关键词',
                                `type`                  int           DEFAULT 0     COMMENT '关键词分类',
                                `count`                 int           DEFAULT 1     COMMENT '搜索次数', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist, 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                        await conn.commit()
                    # 检查表是否存在 dav_keyword 
                    await cursor.execute("SHOW TABLES LIKE 'dav_keyword'")
                    table_exists = await cursor.fetchone()
                    if not table_exists:
                        # 表不存在，创建表
                        await cursor.execute("""
                            CREATE TABLE `dav_keyword`
                            (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `old_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
                                `new_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
                                `count`                 int           DEFAULT 1     COMMENT '替换次数', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist, 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                        await conn.commit()
                    # 检查表是否存在 dav_missions 
                    await cursor.execute("SHOW TABLES LIKE 'dav_missions'")
                    table_exists = await cursor.fetchone()
                    if not table_exists:
                        # 表不存在，创建表
                        await cursor.execute("""
                            CREATE TABLE `dav_missions`
                            (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `localid`               int           DEFAULT 0     COMMENT '文件ID', 
                                -- 文件信息
                                `path`                  varchar(512)  DEFAULT ''    COMMENT '路径',    -- /nfs/hd01/
                                `file`                  varchar(512)  DEFAULT ''    COMMENT '文件',    -- XXX-000 xxxxxx.mp4
                                -- 任务信息
                                `type`                  int           DEFAULT 0     COMMENT '任务类型',  -- 0 null / 1 cut / 2 transcode
                                -- 1 cut
                                `start`                 int           DEFAULT 0     COMMENT '开始秒数', 
                                `end`                   int           DEFAULT 0     COMMENT '结束秒数', 
                                -- 2 transcode
                                `preset`                varchar(16)   DEFAULT 'slow' COMMENT '编码速度',  -- ultrafast superfast veryfast faster fast medium slow slower veryslow
                                `crf`                   int           DEFAULT 15     COMMENT '质量',    -- 0无损 23默认 51最差
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 create / 1 doing / 2 done / -1 failed
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                        await conn.commit()
                    # 检查表是否存在 dav_web 
                    await cursor.execute("SHOW TABLES LIKE 'dav_web'")
                    table_exists = await cursor.fetchone()
                    if not table_exists:
                        # 表不存在，创建表
                        await cursor.execute("""
                            CREATE TABLE `dav_web`
                            (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                -- 识别码
                                `code`                  varchar(48)   NOT NULL      COMMENT '识别码',   -- XXX-000
                                `name`                  varchar(1024) NOT NULL      COMMENT '标题',     -- XXX-000 xxxxxx
                                -- 识别码信息
                                `date`                  varchar(16)   DEFAULT ''    COMMENT '发行日期', 
                                `studio`                varchar(64)   DEFAULT ''    COMMENT '发行商',  -- 
                                `director`              varchar(64)   DEFAULT ''    COMMENT '导演',    -- 
                                `series`                varchar(256)  DEFAULT ''    COMMENT '系列', 
                                `genre`                 varchar(256)  DEFAULT ''    COMMENT '类别',   -- [ 1, 2 ]
                                `actors`                varchar(256)  DEFAULT ''    COMMENT '演员',   -- [ 1, 2 ]
                                `websites`              varchar(512)  DEFAULT ''    COMMENT '网站',   -- { "javbus": "", "javdb": "", "javlibrary": "", }
                                `videos`                varchar(512)  DEFAULT ''    COMMENT '预览视频',   -- [ "https://", ]
                                `images`                varchar(512)  DEFAULT ''    COMMENT '预览图片',   -- [ "https://", ]
                                `magnet`                varchar(512)  DEFAULT ''    COMMENT '磁力链接',   -- [ "magnet://", ]
                                -- 个人评论
                                `score`                 int(4)        DEFAULT 0     COMMENT '评分',    --  -10~0~10
                                `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist, 1 delete
                                `created_time`         datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`         datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                        await conn.commit()
        except aiomysql.Error as e:
            logger.error(f"Failed to create or check dav table: {e}")
            raise HTTPException(status_code=500, detail="Failed to create or check dav table")

    async def disconnect(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiomysql.Connection, None]:
        if self.pool is None:
            await self.connect()
        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            if self.pool:
                self.pool.release(conn)

# print(f"DB_ENGINE: {DB_ENGINE}")
if DB_ENGINE == "mysql":
    database = MySQLDatabase(url=MYSQL_URL)
else:
    database = SQLiteDatabase(url=SQLITE_URL)

async def get_db() -> AsyncGenerator:
    try:
        async with database.get_connection() as conn:
            cursor = await conn.cursor()
            yield cursor
    except Exception as e:
        logger.error(f"Database connection error: {str(e)} | Engine: {DB_ENGINE} | URL: {database.url}")
        raise HTTPException(status_code=500, detail="Database connection error")

@asynccontextmanager
async def get_db_app():
    async with database.get_connection() as conn:
        async with conn.cursor() as cursor:
            yield cursor
