#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습 진척 통계 화면 라우트 (VOCA-FR-031~034)
# 파일 위치: routes/stats.py

from flask import Blueprint, render_template

from db import request_db
from services import stats_service as st

# app.py 에서 url_prefix="/stats" 로 등록한다
bp = Blueprint("stats", __name__)


@bp.get("")
def index():
    conn = request_db()
    return render_template(
        "stats/index.html",
        progress=st.get_progress(conn),
        attempts=st.get_exam_trend(conn),
        daily=st.get_daily_exam_trend(conn),
        top_wrong=st.get_top_wrong_words(conn),
    )
