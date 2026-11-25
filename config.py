#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 환경변수와 앱 상수 (DB 경로, 시간대, 하루 학습량, 업로드 상한)
# 파일 위치: config.py

import os
import secrets
from datetime import datetime, timedelta, timezone

# 개발 PC 기본값은 ./data/voca.db. 서버에서는 Dockerfile 의 DB_PATH=/data/voca.db 를 쓴다 (R-06)
DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "voca.db"))

# 환경변수가 없으면 기동할 때 무작위로 만든다 (R-08, VOCA-NFR-004)
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# 고정 오프셋 한국 시간. zoneinfo 는 쓰지 않는다 (아키텍처 A-6)
KST = timezone(timedelta(hours=9))

DAILY_COUNT = 10              # 하루 학습량 (D-4)
REVIEW_PREV_COUNT = 5         # 직전 일차에서 복습에 섞는 단어 수 (D-5)
REVIEW_WRONG_COUNT = 3        # 자주 틀린 단어를 섞는 최대 수 (D-5)
WRONG_THRESHOLD = 2           # 이 횟수 이상 틀리면 "자주 틀린 단어" (D-5)
WORDS_PER_PAGE = 50           # 단어 목록 페이지 크기
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # CSV 업로드 상한, 서버 기준과 맞춤 (A-7)


def now_iso() -> str:
    """현재 시각을 한국 시간 ISO 8601 문자열로 돌려준다 (데이터 설계서 §5.2)."""
    return datetime.now(KST).isoformat(timespec="seconds")


def today_kst() -> str:
    """오늘 날짜를 YYYY-MM-DD 로 돌려준다. 날짜 경계는 한국 시간 기준이다 (D-8)."""
    return datetime.now(KST).strftime("%Y-%m-%d")
