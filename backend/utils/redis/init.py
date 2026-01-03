#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""

@File ：init.py
@Author ：Cary
@Date ：2024/2/26 14:27
@Descripttion : "redis连接初始化"
"""

from fastapi import FastAPI
from fastapi.requests import Request
from pydantic import Field
from redis import asyncio as aioredis
from typing import Union, Annotated
from loguru import logger

from config import REDIS_CONFIG


class RedisMixin:
    def __init__(self):
        self.mode: str = REDIS_CONFIG['mode']
        self.host: str = REDIS_CONFIG['host']
        self.username: str = REDIS_CONFIG['username']
        self.password: str = REDIS_CONFIG['password']
        self.db: int = REDIS_CONFIG['db']
        self.sentinel_name: str = None
        self.encoding: str = 'utf-8'
        self.decode_responses: bool = True
        self.max_connections: int = 2000
        self.ssl: bool = False
        self.ssl_cert_reqs: str = None
        self.ssl_ca_certs: str = None

    @property
    async def redis_standalone_conn(self) -> aioredis.Redis:
        """
        单机
        :return:
        """
        sentinel_host = self.host.split(':')[0]
        sentinel_port = int(self.host.split(":")[-1])
        return aioredis.Redis(host=sentinel_host, port=sentinel_port,
                              username=self.username,
                              password=self.password,
                              db=self.db,
                              decode_responses=self.decode_responses,
                              max_connections=self.max_connections,
                              ssl=self.ssl,
                              ssl_cert_reqs=self.ssl_cert_reqs,
                              ssl_ca_certs=self.ssl_ca_certs)

    @property
    async def redis_sentinel_conn(self) -> aioredis.Sentinel:
        """
        哨兵
        :return:
        """
        sentinel_list = []
        for address in self.host.split(','):
            sentinel_host = address.split(':')[0]
            sentinel_port = int(address.split(':')[-1])
            sentinel_list.append(
                (sentinel_host, sentinel_port)
            )
        return aioredis.Sentinel(sentinels=sentinel_list,
                                 username=self.username,
                                 password=self.password,
                                 db=self.db,
                                 decode_responses=self.decode_responses,
                                 max_connections=self.max_connections,
                                 ssl=self.ssl,
                                 ssl_cert_reqs=self.ssl_cert_reqs,
                                 ssl_ca_certs=self.ssl_ca_certs)

    @property
    async def redis_cluster_conn(self) -> aioredis.RedisCluster:
        """
        集群
        :return:
        """
        startup_nodes = []
        for address in self.host.split(','):
            cluster_host = address.split(':')[0]
            cluster_port = int(address.split(':')[-1])
            startup_nodes.append(
                aioredis.cluster.ClusterNode(cluster_host, cluster_port)
            )
        return aioredis.RedisCluster(startup_nodes=startup_nodes,
                                     username=self.username,
                                     password=self.password,
                                     decode_responses=self.decode_responses,
                                     ssl=self.ssl,
                                     ssl_cert_reqs=self.ssl_cert_reqs,
                                     ssl_ca_certs=self.ssl_ca_certs)

    @property
    async def connect_redis(self):
        """
        连接redis
        """

        if self.mode == "standalone":
            redis_conn: aioredis.Redis = await self.redis_standalone_conn
        elif self.mode == "sentinel":
            redis_conn: aioredis.Sentinel = await self.redis_sentinel_conn
        elif self.mode == "cluster":
            redis_conn: aioredis.RedisCluster = await self.redis_cluster_conn
        else:
            raise ValueError("Redis mode not supported")

        try:
            await redis_conn.ping()
            return redis_conn
        except aioredis.ConnectionError as e:
            logger.error(f"Redis连接失败: {e}")
            return None


async def register_redis(app: FastAPI):
    # 注册redis测试连接
    app.state.cache = await RedisMixin().connect_redis


redisCache = Annotated[
    Union[aioredis.Redis, aioredis.Sentinel, aioredis.RedisCluster], Field(description="redis联合类型")]


async def get_redis() -> redisCache:
    try:
        _redis_coon = await RedisMixin().connect_redis
        if _redis_coon is None:
            yield None

        try:
            yield _redis_coon
        finally:
            await _redis_coon.close()
    except Exception as e:
        if _redis_coon is not None:
            await _redis_coon.close()
        yield None


if __name__ == "__main__":
    import asyncio

    a = asyncio.run(RedisMixin().connect_redis)
    print(type(a))
    print(a)
