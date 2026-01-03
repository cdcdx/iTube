import sys
import logging
from types import FrameType
from typing import cast
from loguru import logger

class Logger:
    """输出日志到文件和控制台"""

    def __init__(self):
        self._setup_logger()

    def _setup_logger(self):
        # 清空所有设置
        self.logger = logger
        self.logger.remove()
        # 添加控制台输出的格式,sys.stdout为输出到屏幕
        self.logger.add(
            sys.stdout,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "  # 颜色>时间
                "{process.name} | "  # 进程名
                "{thread.name} | "  # 线程名
                "<cyan>{module}</cyan>.<cyan>{function}</cyan>"  # 模块名.方法名
                ":<cyan>{line}</cyan> | "  # 行号
                "<level>{level}</level>: "  # 等级
                "<level>{message}</level>"  # 日志内容
            ),
        )

    def init_config(self):
        LOGGER_NAMES = ("uvicorn.asgi", "uvicorn.access", "uvicorn")
 
        # change handler for default uvicorn logger
        logging.getLogger().handlers = [InterceptHandler()]
        for logger_name in LOGGER_NAMES:
            logging_logger = logging.getLogger(logger_name)
            logging_logger.setLevel(logging.WARNING)  # 设置特定日志记录器的级别为 WARNING
            logging_logger.handlers = [InterceptHandler()]

    def get_logger(self):
        return self.logger

class InterceptHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logger = logger

    def emit(self, record: logging.LogRecord) -> None:
        # 过滤掉包含 callHandlers 的日志消息
        if 'callHandlers' in record.getMessage():
            return

        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:  # noqa: WPS609
            frame = cast(FrameType, frame.f_back)
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage(),
        )


# 创建 Logger 实例
loggers = Logger()
log = loggers.get_logger()

# # 初始化日志配置
# loggers.init_config()
