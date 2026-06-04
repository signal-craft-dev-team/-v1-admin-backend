from typing import Annotated
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import UUID
 
from .src.config import settings

# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(
    title="SignalCraft Admin API",
    version="0.0.1",
    description='''운영자용 서버.<br>
                  DB 관리, 유저 관리, 운영자 대시보드 API 등을 제공합니다.''',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ADMIN_ORIGINS,   # 스테이징에선 대시보드 origin 으로 잠그세요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
