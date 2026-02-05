import os
import re
import urllib
import aiosqlite
import aiomysql
import datetime
from datetime import datetime as dt
from decimal import Decimal
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from loguru import logger

from config import BASE_DIR, DB_ENGINE, SQLITE_URL, MYSQL_URL, DB_MAXCONNECT

class Database(ABC):
    """数据库抽象基类"""
    def __init__(self, url: str):
        self.url = url
        self.pool = None
        self.is_connected = False

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

    async def health_check(self) -> bool:
        """检查数据库连接健康状况"""
        try:
            async with self.get_connection() as conn:
                if isinstance(self, SQLiteDatabase):  # SQLite
                    await conn.execute("SELECT 1")
                else:  # MySQL
                    await conn.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

class SQLiteDatabase(Database):
    """SQLite数据库实现"""
    def __init__(self, url: str):
        super().__init__(url)
        db_path = url.split("://")[1]
        if db_path.startswith('./'):
            self.url = os.path.join(BASE_DIR, db_path.replace('./', ''))
        else:
            self.url = db_path
        logger.info(f"SQLite URL: {self.url}")

    async def connect(self) -> None:
        """连接数据库并创建表"""
        try:
            # 检查数据库文件是否存在，不存在则创建
            if not os.path.exists(self.url):
                await self._initialize_database()
            
            # 创建连接池
            self.pool = await aiosqlite.connect(self.url, uri=True, check_same_thread=False)
            if self.pool:
                self.is_connected = True
                logger.info(f"Connected to SQLite database: {self.url}")
                # 检查并创建表
                await self.create_tables()
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise RuntimeError(f"Failed to connect to SQLite database: {str(e)}") from e

    async def _initialize_database(self) -> None:
        """初始化新的数据库文件"""
        conn = await aiosqlite.connect(self.url, uri=True)
        try:
            await self.create_tables(conn)
        finally:
            await conn.close()

    async def create_tables(self, conn=None) -> None:
        """创建数据库表"""
        should_commit = conn is None
        try:
            if conn is None:
                conn = await aiosqlite.connect(self.url, uri=True)
            
            # 创建表 dav_local
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_local (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT     DEFAULT '',
                    name         TEXT     NOT NULL,
                    path         TEXT     DEFAULT '',
                    file         TEXT     DEFAULT '',
                    size         REAL     DEFAULT 0.0,
                    created      DATETIME DEFAULT NULL,
                    duration     REAL     DEFAULT 0.0,
                    aspectratio  REAL     DEFAULT 0.0,
                    fps          REAL     DEFAULT 0.0,
                    resolution   TEXT     DEFAULT '',
                    format       TEXT     DEFAULT '',
                    crc          TEXT     DEFAULT '',
                    subtitle     TEXT     DEFAULT '',
                    grade        INTEGER  DEFAULT 0,
                    score        INTEGER  DEFAULT 0,
                    comment      TEXT     DEFAULT '',
                    status       INTEGER  DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            
            # 创建表 dav_search
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_search (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    parid        INTEGER  DEFAULT 0,
                    key          TEXT     DEFAULT '',
                    type         INTEGER  DEFAULT 0,
                    count        INTEGER  DEFAULT 0,
                    status       INTEGER  DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            
            # 检查是否有初始数据
            cursor = await conn.execute("SELECT COUNT(*) FROM dav_search")
            count = await cursor.fetchone()
            if count and count[0] == 0:
                # 插入数据
                await conn.execute("""
                    INSERT INTO dav_search ("id", "parid", "key", "type", "count", "status") VALUES 
                        (1, -1, 'all', 0, 30, 0),
                        (2, -1, 'all2', 0, 30, 0),
                        (3, -1, 'all3', 0, 30, 0),
                        (4, -1, 'repeat', 0, 30, 0),
                        (5, -1, 'nojapan', 0, 30, 0),
                        (6, -1, 'score', 0, 10, 0),
                        (7, -1, 'transcode', 0, 10, 0);
                """)
            
            # 创建表 dav_keyword
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_keyword (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_key      TEXT     DEFAULT '',
                    new_key      TEXT     DEFAULT '',
                    count        INTEGER  DEFAULT 0,
                    status       INTEGER  DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            
            # 创建表 dav_missions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_missions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    localid      INTEGER  DEFAULT 0,
                    path         TEXT     DEFAULT '',
                    file         TEXT     DEFAULT '',
                    type         INTEGER  DEFAULT 0,
                    start        INTEGER  DEFAULT 0,
                    end          INTEGER  DEFAULT 0,
                    preset       TEXT     DEFAULT 'slow',
                    crf          INTEGER  DEFAULT 15,
                    status       INTEGER  DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            
            # 创建表 dav_web
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS dav_web (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT     DEFAULT '',
                    name         TEXT     NOT NULL,
                    date         TEXT     DEFAULT '',
                    studio       TEXT     DEFAULT '',
                    director     TEXT     DEFAULT '',
                    series       TEXT     DEFAULT '',
                    genre        TEXT     DEFAULT '',
                    actors       TEXT     DEFAULT '',
                    websites     TEXT     DEFAULT '',
                    videos       TEXT     DEFAULT '',
                    images       TEXT     DEFAULT '',
                    magnet       TEXT     DEFAULT '',
                    score        INTEGER  DEFAULT 0,
                    comment      TEXT     DEFAULT '',
                    status       INTEGER  DEFAULT 0,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_time DATETIME DEFAULT NULL
                )""")
            
            if should_commit:
                await conn.commit()
        except Exception as e:
            if should_commit:
                await conn.rollback()
            logger.error(f"Failed to create tables in SQLite: {e}")
            raise RuntimeError(f"Failed to create tables in SQLite: {str(e)}") from e
        finally:
            if should_commit:
                await conn.close()

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.is_connected = False
            logger.info("Disconnected from SQLite database")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        if not self.is_connected:
            await self.connect()
        if not self.pool:
            logger.error("Failed to establish database connection")
            raise RuntimeError("Failed to establish database connection")
        
        try:
            yield self.pool
        except Exception as e:
            logger.error(f"Error during database operation: {e}")
            raise RuntimeError(f"Error during database operation: {str(e)}") from e

class MySQLDatabase(Database):
    """MySQL数据库实现"""
    def __init__(self, url: str):
        super().__init__(url)
        parsed_url = urllib.parse.urlparse(url)
        self.host = parsed_url.hostname
        self.port = parsed_url.port or 3306
        self.username = urllib.parse.unquote(parsed_url.username)
        self.password = urllib.parse.unquote(parsed_url.password)
        self.db = parsed_url.path.lstrip('/')
        self.max_connection = DB_MAXCONNECT
        logger.info(f"MySQL URL: host={self.host}, port={self.port}, user={self.username}, db={self.db}")

    async def connect(self) -> None:
        """连接数据库并创建表"""
        try:
            # 创建连接池
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                db=self.db,
                maxsize=self.max_connection
            )
            
            # 创建连接池
            if self.pool:
                self.is_connected = True
                logger.info(f"Connected to MySQL database: {self.db}")
                # 检查并创建表
                await self.create_tables()
        except aiomysql.Error as e:
            logger.warning(f"Failed to connect to MySQL database '{self.db}': {e}")
            # 检查错误是否与用户不存在相关
            if "does not exist" in str(e) or "authentication" in str(e).lower():
                logger.error(f"Database authentication failed: {e}")
                raise Exception(f"Database authentication failed: {e}")
            else:
                # 创建数据库
                try:
                    await self._create_database()
                    # 重试连接
                    self.pool = await aiomysql.create_pool(
                        host=self.host,
                        port=self.port,
                        user=self.username,
                        password=self.password,
                        db=self.db,
                        minsize=1,
                        maxsize=self.max_connection
                    )
                    if self.pool:
                        self.is_connected = True
                        logger.info(f"Connected to MySQL database: {self.db}")
                        # 检查并创建表
                        await self.create_tables()
                except Exception as e:
                    logger.error(f"Failed to connect to MySQL database: {e}")
                    raise Exception(f"Failed to connect to MySQL database: {str(e)}") from e

    async def _create_database(self) -> None:
        """创建数据库"""
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
            logger.error(f"Failed to create database '{self.db}': {e}")
            raise RuntimeError(f"Failed to create database '{self.db}': {str(e)}") from e

    async def create_tables(self) -> None:
        """创建数据库表"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 创建表 dav_local
                    await cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dav_local (
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
                                `fps`                   float(16)     DEFAULT 0.0   COMMENT '帧率',     -- 30 60
                                `resolution`            varchar(16)   DEFAULT ''    COMMENT '分辨率',   -- 1080 720
                                `format`                varchar(32)   DEFAULT ''    COMMENT '格式',     -- mp4
                                `crc`                   varchar(32)   DEFAULT ''    COMMENT 'crc',     -- 3d91035d
                                -- 标记信息
                                `subtitle`              varchar(8)    DEFAULT NULL  COMMENT '字幕',    --  NULL/CN/JP/EN
                                `grade`                 int(4)        DEFAULT 0     COMMENT '等级',    --  -2 luan2 / -1 luan / 0 ai / 1 youma / 2 aima / 11 wuma / 99 good
                                -- 个人评论
                                `score`                 int(4)        DEFAULT 0     COMMENT '评分',    --  -10~0~10
                                `comment`               varchar(256)  DEFAULT ''    COMMENT '评论', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE,
                                INDEX idx_email (code)
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                    
                    # 创建表 dav_search 
                    await cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dav_search (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `parid`                 int           DEFAULT 0     COMMENT '父级ID', -- 0 nothing / other
                                `key`                   varchar(48)   DEFAULT ''    COMMENT '搜索关键词',
                                `type`                  int           DEFAULT 0     COMMENT '关键词分类',  -- 0 system / 1 key / 2 girl / 3 series / 4 actor
                                `count`                 int           DEFAULT 1     COMMENT '搜索次数', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                    
                    # 插入数据
                    await cursor.execute("""
                            INSERT INTO dav_search ("id", "parid", "key", "type", "count", "status") VALUES 
                                (1, -1, 'all', 0, 30, 0),
                                (2, -1, 'all2', 0, 30, 0),
                                (3, -1, 'all3', 0, 30, 0),
                                (4, -1, 'repeat', 0, 30, 0),
                                (5, -1, 'nojapan', 0, 30, 0),
                                (6, -1, 'score', 0, 10, 0),
                                (7, -1, 'transcode', 0, 10, 0);
                        """)
                    
                    # 创建表 dav_keyword 
                    await cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dav_keyword (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `old_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
                                `new_key`               varchar(48)   DEFAULT ''    COMMENT '替换关键词',
                                `count`                 int           DEFAULT 1     COMMENT '替换次数', 
                                `status`                int           DEFAULT 0     COMMENT '状态',    -- 0 exist / 1 delete
                                `created_time`          datetime      DEFAULT NOW() COMMENT '创建时间',
                                `updated_time`          datetime      DEFAULT NULL  COMMENT '更新时间',
                                PRIMARY KEY (`id`)  USING BTREE
                            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
                        """)
                    
                    # 创建表 dav_missions 
                    await cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dav_missions (
                                `id`                    int           NOT NULL AUTO_INCREMENT COMMENT 'id',
                                `localid`               int           DEFAULT 0     COMMENT '文件ID', 
                                -- 文件信息
                                `path`                  varchar(512)  DEFAULT ''    COMMENT '路径',    -- /nfs/hd01/
                                `file`                  varchar(512)  DEFAULT ''    COMMENT '文件',    -- XXX-000 xxxxxx.mp4
                                -- 任务信息
                                `type`                  int           DEFAULT 0     COMMENT '任务类型',  -- 0 null / 1 cut / 2 transcode / 3 scan_path / 4 clear_local_db
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
                    
                    # 创建表 dav_web 
                    await cursor.execute("""
                            CREATE TABLE IF NOT EXISTS dav_web (
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
                                `videos`                varchar(1024) DEFAULT ''    COMMENT '预览视频',   -- [ "https://", ]
                                `images`                varchar(1024) DEFAULT ''    COMMENT '预览图片',   -- [ "https://", ]
                                `magnet`                varchar(128)  DEFAULT ''    COMMENT '磁力链接',   -- [ "magnet://", ]
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
            logger.error(f"Failed to create tables in MySQL: {e}")
            raise RuntimeError(f"Failed to create tables in MySQL: {str(e)}") from e

    async def disconnect(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.is_connected = False
            logger.info("Disconnected from MySQL database")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiomysql.Connection, None]:
        if not self.is_connected:
            await self.connect()
        if not self.pool:
            logger.error("Failed to establish database connection")
            raise RuntimeError("Failed to establish database connection")
        
        conn = await self.pool.acquire()
        try:
            yield conn
        except Exception as e:
            logger.error(f"Error during database operation: {e}")
            raise RuntimeError(f"Error during database operation: {str(e)}") from e
        finally:
            if self.pool:
                self.pool.release(conn)

# print(f"DB_ENGINE: {DB_ENGINE}")
# 根据配置创建数据库实例
def create_database_instance():
    """根据配置创建相应的数据库实例"""
    if DB_ENGINE == "mysql":
        return MySQLDatabase(url=MYSQL_URL)
    else:  # 默认使用SQLite
        return SQLiteDatabase(url=SQLITE_URL)
database = create_database_instance()

async def get_db() -> AsyncGenerator:
    try:
        async with database.get_connection() as conn:
            cursor = await conn.cursor()
            try:
                yield cursor
            finally:
                await cursor.close()
    except Exception as e:
        logger.error(f"Failed to get_db: {str(e)} | Engine: {DB_ENGINE} | URL: {database.url}")
        raise RuntimeError(f"Failed to get_db: {str(e)}") from e

@asynccontextmanager
async def get_db_app():
    try:
        async with database.get_connection() as conn:
            async with conn.cursor() as cursor:
                yield cursor
    except Exception as e:
        logger.error(f"Failed to get_db_app: {str(e)} | Engine: {DB_ENGINE} | URL: {database.url}")
        raise RuntimeError(f"Failed to get_db_app: {str(e)}") from e

def format_query_for_db(query: str) -> str:
    """根据数据库类型格式化查询语句"""
    if DB_ENGINE == "sqlite":
        # 将 %s 替换为 ?
        query = query.replace('%s', '?')
        query = query.replace('NOW()', 'CURRENT_TIMESTAMP')
        
        # 处理 unix_timestamp 语法
        # query = re.sub(r'unix_timestamp\(([^)]+)\)', r'strftime(\1)', query)
        query = re.sub(r'unix_timestamp\(([^)]+)\)', r'strftime(\'%s\', \1)', query)
        
        # 处理 COLLATE utf8mb4_general_ci 语法
        query = re.sub(r'\bCOLLATE\s+utf8mb4_general_ci\b', 'COLLATE NOCASE', query, flags=re.IGNORECASE)
        # query = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s+COLLATE\s+utf8mb4_general_ci\s+=\s+(%s)', r'LOWER(\1) = LOWER(\2)', query, flags=re.IGNORECASE)
        
        return query
    else:  # MySQL
        return query

def convert_row_to_dict(row, cursor_description=None):
    """将数据库查询结果行转换为字典"""
    if row is None:
        return None
    
    if isinstance(row, tuple) and cursor_description:
        return dict(zip([desc[0] for desc in cursor_description], row))
    elif hasattr(row, 'items'):  # 字典类型
        return dict(row)
    elif hasattr(row, 'keys'):  # 映射类型
        return dict(row)
    return row

def format_datetime_fields(data: dict) -> dict:
    """格式化日期时间字段"""
    if data is None:
        return None
    
    formatted_data = {}
    for key, value in data.items():
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            formatted_data[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, Decimal):
            formatted_data[key] = float(value)
        else:
            formatted_data[key] = value
    return formatted_data
