import os
import sys
from cryptography.fernet import Fernet
from fastapi.templating import Jinja2Templates
from dotenv import find_dotenv, load_dotenv, get_key, set_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_envsion(key, format=True):
    if format:
        value = []
        value_str = get_key(find_dotenv('.env'), key_to_get=key)
        if value_str:
            value = value_str.split(',')
    else:
        value = get_key(find_dotenv('.env'), key_to_get=key)
    return value


def set_envsion(key, value, format=True):
    if format:
        value_str = ','.join(value)
    else:
        value_str = value
    return set_key(find_dotenv('.env'), key_to_set=key, value_to_set=value_str)


# .env
if not os.path.exists('.env'):
    print("ERROR: '.env' file does not exist")
    sys.exit()
else:
    load_dotenv(find_dotenv('.env'))


# ## CRYPTO-KEY
# if os.getenv("KEY") is None:
#     print("ERROR: 'KEY' is not set in the .env file")
#     sys.exit()
# else:
#     KEY = os.getenv("KEY")
#     KEY = KEY if KEY.endswith("=") else KEY + "="
#     FNet = Fernet(KEY)


# APP
APP_TITLE = os.getenv('APP_TITLE', default='iTube')
APP_PAGE_LIMIT = int(os.getenv('APP_PAGE_LIMIT', default=12))
APP_ACTION_PASSWD = os.getenv('APP_ACTION_PASSWD', default='123456')


# FastAPI
FASTAPI_API_PATH: str = '/api'
FASTAPI_TITLE: str = APP_TITLE
FASTAPI_VERSION: str = '0.0.1'
FASTAPI_DESCRIPTION: str = f'{APP_TITLE} API Interface'
FASTAPI_DOCS_URL: str | None = f'{FASTAPI_API_PATH}/docs'
FASTAPI_REDOC_URL: str | None = None
FASTAPI_OPENAPI_URL: str | None = f'{FASTAPI_API_PATH}/openapi'
FASTAPI_STATIC_FILES: bool = False


# UVICORN
UVICORN_HOST = os.getenv('UVICORN_HOST', default='127.0.0.1')
UVICORN_PORT = int(os.getenv('UVICORN_PORT', default=8000))
SSL_KEYFILE = os.getenv('SSL_KEYFILE', default='')
SSL_CERTFILE = os.getenv('SSL_CERTFILE', default='')


# BASIC AUTH
BASIC_USERNAME = os.getenv('BASIC_USERNAME', default='admin')
BASIC_PASSWORD = os.getenv('BASIC_PASSWORD', default='admin')


# SQL配置
DB_ENGINE = os.getenv('DB_ENGINE', default='sqlite')
SQLITE_URL = os.getenv('SQLITE_URL', default='dav_db.sqlite')
MYSQL_URL = os.getenv('MYSQL_URL', default='')
DB_MAXCONNECT = int(os.getenv('DB_MAXCONNECT', default=100))

# REDIS配置
REDIS_MODE = os.getenv('REDIS_MODE', default='standalone')
REDIS_ADDRESS = os.getenv('REDIS_ADDRESS', default='127.0.0.1:6379')
REDIS_USERNAME = os.getenv('REDIS_USERNAME', default=None)
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', default=None)
REDIS_DB = int(os.getenv('REDIS_DB', default=0))
REDIS_TIMEOUT = int(os.getenv('REDIS_TIMEOUT', default=5))
REDIS_CONFIG = {
    'mode': REDIS_MODE,
    'host': REDIS_ADDRESS,
    'username': REDIS_USERNAME,
    'password': REDIS_PASSWORD,
    'db': REDIS_DB,
    'timeout': REDIS_TIMEOUT,
}

# PATH
SCAN_PATH = get_envsion('SCAN_PATH')
SCAN_CODE = bool(os.getenv('SCAN_CODE', 'False') == 'True')
SCAN_EXT_LIST = get_envsion('SCAN_EXT_LIST')
PATH_FILTER_LIST = get_envsion('PATH_FILTER_LIST')

# THUMBNAIL
THUMBNAIL_TIME = int(os.getenv('THUMBNAIL_TIME', default=30))
THUMBNAIL_COMPRESSION = int(os.getenv('THUMBNAIL_COMPRESSION', default=1))
THUMBNAIL_CLEAR = bool(os.getenv('THUMBNAIL_CLEAR', 'False') == 'True')

# TEMP_PATH
TEMP_PATH = os.getenv("TEMP_PATH", default="./.temp")  # os.path.join(os.path.dirname(os.path.dirname(__file__)), "./.temp"))
TEMP2_PATH = os.getenv("TEMP2_PATH", default="./.temp2")  # os.path.join(os.path.dirname(os.path.dirname(__file__)), "./.temp2"))
if not os.path.exists(TEMP_PATH): os.mkdir(TEMP_PATH)

# Jinja2
templates = Jinja2Templates(directory='./frontend/templates')

# PROXY
HTTP_PROXY = os.getenv('HTTP_PROXY', default='')
web_proxies={
    "http": HTTP_PROXY,
    "https": HTTP_PROXY,
}
web_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
