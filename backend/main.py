import argparse
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.router import api_router
from api.router import root_router
from utils.db import database
from utils.log import loggers, log as logger
from utils.local import check_ssl_files
from config import *


# 初始化参数
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', type=bool, default=False, action=argparse.BooleanOptionalAction)
parser.add_argument('-l', '--log', type=str, default="warning")
args = parser.parse_args()
run_debug = bool(args.debug)
run_log = str(args.log.lower())
if run_debug:
    run_log = "DEBUG"
# print(f"log level: {run_log}")
# 日志配置
logger.remove()
logger.add(sys.stdout, level=str(run_log).upper())
loggers.init_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    logger.info("Application starting up...")
    try:
        await database.connect()
        logger.info("Database connected successfully")
        yield
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise
    finally:
        # 关闭逻辑
        logger.info("Application shutting down...")
        try:
            await database.disconnect()
            logger.info("Database disconnected successfully")
        except Exception as e:
            logger.error(f"Error during database disconnection: {e}")


app = FastAPI(
    title=FASTAPI_TITLE,
    version=FASTAPI_VERSION,
    description=FASTAPI_DESCRIPTION,
    docs_url=FASTAPI_DOCS_URL,
    redoc_url=FASTAPI_REDOC_URL,
    openapi_url=FASTAPI_OPENAPI_URL,
    lifespan=lifespan
)

# 添加中间件
## 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 添加GZip压缩中间件以减少传输大小
app.add_middleware(GZipMiddleware, minimum_size=1000)
## 路由
app.include_router(api_router)
app.include_router(root_router)

# 静态文件服务
app.mount("/frontend/static", StaticFiles(directory="./frontend/static"), name="static")
app.mount("/.temp", StaticFiles(directory=TEMP_PATH), name="temp")


if __name__ == "__main__":
    logger.info(f"Starting server on {UVICORN_HOST}:{UVICORN_PORT}")

    # 检查SSL证书文件
    SSL_CERTFILE, SSL_KEYFILE = check_ssl_files(SSL_CERTFILE, SSL_KEYFILE)
    if SSL_CERTFILE and SSL_KEYFILE:
        logger.info(f"SSL enabled - Cert: {SSL_CERTFILE}, Key: {SSL_KEYFILE}")
    else:
        logger.info("SSL disabled - Cert or key file not found")
    
    # 根据是否调试模式确定工作进程数
    cpu_count = 1 if run_debug else max(1, os.cpu_count() or 1)
    logger.info(f"cpu_count: {cpu_count}")

    try:
        uvicorn.run(
                app="main:app",
                host=UVICORN_HOST,
                port=UVICORN_PORT,
                reload=run_debug,
                workers=1,  # 禁用多进程
                limit_concurrency=2000,
                ssl_keyfile=SSL_KEYFILE if SSL_KEYFILE else None,
                ssl_certfile=SSL_CERTFILE if SSL_CERTFILE else None,
            )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down gracefully...")
    except asyncio.exceptions.CancelledError:
        logger.info("Task was cancelled, shutting down gracefully...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        logger.info("Application shutdown complete")
