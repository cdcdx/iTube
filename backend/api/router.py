#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from api.frontend import router as frontend_router

from api.net import router as net_router
from api.file import router as file_router
from api.stream import router as stream_router

root_router = APIRouter()
root_router.include_router(frontend_router, prefix="", tags=["frontend"])

api_router = APIRouter(prefix="/api")
api_router.include_router(net_router, prefix="", tags=["net"])
api_router.include_router(file_router, prefix="", tags=["file"])
api_router.include_router(stream_router, prefix="", tags=["stream"])
