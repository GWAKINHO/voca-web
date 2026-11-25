#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 공개 사용자 순위표 및 읽기 전용 통계 라우트 (VOCA-FR-051~053)
# 파일 위치: routes/ranking.py

from flask import Blueprint, abort, render_template

from db import request_db
from services import ranking_service as rk

# app.py 에서 url_prefix="/ranking" 로 등록한다. 읽기 전용 GET 라우트만 제공한다 (FR-053)
bp = Blueprint("ranking", __name__)


@bp.get("")
def index():
    conn = request_db()
    return render_template("ranking/index.html", ranking=rk.list_public_ranking(conn))


@bp.get("/<int:target_user_id>")
def detail(target_user_id):
    conn = request_db()
    data = rk.get_public_user_stats(conn, target_user_id)
    if data is None:
        # 비공개 사용자이거나 존재하지 않는 계정이면 차단한다 (VOCA-FR-052)
        abort(404)
    return render_template("ranking/detail.html", **data)
