import asyncio
import json
from builtins import anext
from contextlib import asynccontextmanager

from utils.redis.init import get_redis
from utils.redis.serialization_tools import is_json, get_dict_target_value
from utils.log import log as logger


@asynccontextmanager
async def get_redis_connection():
    _c = get_redis()
    if _c is None:
        raise RuntimeError("Unable to connect to Redis: _c")
    cache = await anext(_c)
    if cache is None:
        raise RuntimeError("Unable to connect to Redis: cache")  # 请先安装redis以来
    try:
        yield cache
    finally:
        # 如果需要，这里可以添加连接清理代码
        pass


async def validate_key_and_data(cache, key: str):
    """验证键值对是否存在且有效"""
    if not await cache.exists(key):
        return None
    data = await cache.get(key)
    if not data:
        return None
    return data


# 键值是否存在
async def redis_exists_key(key: str) -> bool:
    """
    key : redis中的key 判断key是否存在，空视为不存在
    """
    try:
        async with get_redis_connection() as cache:
            data = await validate_key_and_data(cache, key)
            if not data:
                return False
            return True
    except Exception as e:
        logger.error(f"redis_exists_key Exception: {str(e)}")
        return False


# 统计前缀键值数量
async def redis_count_key(prefix: str) -> int:
    """
    prefix : redis中的key的前缀
    """
    try:
        async with get_redis_connection() as cache:
            keys = await cache.keys(f"{prefix}*")
            # print(f"count: {len(keys)}")
            return len(keys)
    except Exception as e:
        logger.error(f"redis_count_key Exception: {str(e)}")
        return 0


# 键值计数器
async def redis_count(key, amount=1):
    """redis 计数器"""
    try:
        async with get_redis_connection() as cache:
            count = await cache.incr(key, amount)
            return count
    except Exception as e:
        logger.error(f"redis_count Exception: {str(e)}")
        return 0


# 键值对自增1
async def increment_redis_data(key: str, value_key: str = None, **kwargs) -> bool:
    """
    key : redis中的key
    value_key : 如果是个json可直接查找json里的字段
    """
    try:
        async with get_redis_connection() as cache:
            data = await validate_key_and_data(cache, key)
            if not data:
                return False
            # print(f"increment_redis_data key: {key} data: {data}")
            if is_json(data):
                data = json.loads(data)
                if value_key and int(get_dict_target_value(data, value_key)) >= 0:
                    data['count'] += 1
                    data_json = json.dumps(data)
                    # print(f"increment_redis_data key: {key} data_json: {data_json}")
                    await cache.set(key, data_json, **kwargs)
            return True
    except Exception as e:
        logger.error(f"increment_redis_data Exception: {str(e)}")
        return False


# 获取键值数据
async def get_redis_data(key: str, value_key: str = None):
    """
    key : redis中的key
    value_key : 如果是个json可直接查找json里的字段
    """
    try:
        async with get_redis_connection() as cache:
            data = await validate_key_and_data(cache, key)
            if not data:
                return None
            # print(f"get_redis_data {key} data: {data}")
            if is_json(data):
                data = json.loads(data)
                if value_key:
                    return get_dict_target_value(data, value_key)
            return data
    except Exception as e:
        logger.error(f"get_redis_data Exception: {str(e)}")
        return None


# 设置键值对
async def set_redis_data(key: str, value=None, **kwargs):
    """
    key : redis中的key
    value : 要存的数据
    """
    try:
        async with get_redis_connection() as cache:
            if isinstance(value, dict):
                value = json.dumps(value)
            # print(f"set_redis_data {key} value: {value}")
            await cache.set(key, value, **kwargs)
    except Exception as e:
        logger.error(f"set_redis_data Exception: {str(e)}")
        return None


# 批量获取多个键值数据
async def batch_get_redis_data(keys: list, value_key: str = None):
    """批量获取多个键值数据"""
    results = {}
    try:
        if len(keys) == 0:
            return results
        async with get_redis_connection() as cache:
            for key in keys:
                data = await validate_key_and_data(cache, key)
                if not data:
                    results[key] = None
                    continue
                if is_json(data):
                    data = json.loads(data)
                    if value_key:
                        results[key] = get_dict_target_value(data, value_key)
                    else:
                        results[key] = data
                else:
                    results[key] = data
    except Exception as e:
        logger.error(f"batch_get_redis_data Exception: {str(e)}")
    return results


# 批量设置多个键值对
async def batch_set_redis_data(key_value_pairs: dict, batch_size: int = 1000, **kwargs):
    """批量设置多个键值对"""
    try:
        if len(key_value_pairs) == 0:
            return key_value_pairs
        async with get_redis_connection() as cache:
            pipe = cache.pipeline(transaction=False)  # 设置transaction=False提高性能
            pending_operations = 0

            async def execute_batch():
                nonlocal pending_operations
                if pending_operations > 0:
                    await pipe.execute()
                    pending_operations = 0

            for key, value in key_value_pairs.items():
                if isinstance(value, dict):
                    value = json.dumps(value)
                pipe.set(key, value, **kwargs)
                pending_operations += 1

                if pending_operations >= batch_size:
                    await execute_batch()

            await execute_batch()  # 处理剩余操作
    except Exception as e:
        logger.error(f"batch_set_redis_data Exception: {str(e)}")
        return None


# 获取键值ttl
async def get_redis_ttl(key: str) -> int:
    """
    key : redis中的key
    """
    try:
        async with get_redis_connection() as cache:
            return await cache.ttl(key)
    except Exception as e:
        logger.error(f"get_redis_ttl Exception: {str(e)}")
        return 0


# 设置键值ttl ex=20 秒
async def set_redis_ttl(key: str, **kwargs) -> bool:
    """
    key : redis中的key
    """
    try:
        async with get_redis_connection() as cache:
            data = await validate_key_and_data(cache, key)
            if not data:
                return False
            value = await cache.get(key)
            await cache.set(key, value, **kwargs)
            return True
    except Exception as e:
        logger.error(f"set_redis_ttl Exception: {str(e)}")
        return False


# 批量设置前缀键值ttl ex=20 秒
async def batch_set_redis_ttl(prefix: str, **kwargs) -> bool:
    """
    prefix : redis中的key的前缀
    """
    try:
        async with get_redis_connection() as cache:
            pipe = cache.pipeline(transaction=False)  # 设置transaction=False提高性能
            cursor = b'0'
            while cursor:
                cursor, keys = await cache.scan(cursor=cursor, match=f"{prefix}*", count=1000)
                if keys:
                    values = await cache.mget(keys)
                    for key, value in zip(keys, values):
                        if value:
                            pipe.set(key, value, **kwargs)
            await pipe.execute()
            return True
    except Exception as e:
        logger.error(f"batch_set_redis_ttl Exception: {str(e)}")
        return False


# 删除键值对
async def del_redis_data(key: str) -> bool:
    """
    key : redis中的key
    """
    try:
        async with get_redis_connection() as cache:
            data = await validate_key_and_data(cache, key)
            if not data:
                return False
            await cache.delete(key)
            return True
    except Exception as e:
        logger.error(f"del_redis_data Exception: {str(e)}")
        return False


# 批量删除多个前缀键值
async def batch_del_redis_data(prefix: str) -> bool:
    """
    prefix : redis中的key的前缀
    """
    try:
        async with get_redis_connection() as cache:
            pipe = cache.pipeline(transaction=False)  # 设置transaction=False提高性能
            keys = await cache.keys(f"{prefix}*")
            if keys:
                pipe.delete(*keys)
                await pipe.execute()
            return True
    except Exception as e:
        logger.error(f"batch_del_redis_data Exception: {str(e)}")
        return False


if __name__ == '__main__':
    asyncio.run(get_redis_data('sys:settings'))
