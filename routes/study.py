#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 오늘 암기 카드(한 장씩)와 다음 카드 기록 라우트 (VOCA-FR-011~014)
# 파일 위치: routes/study.py

import sqlite3

from flask import Blueprint, redirect, render_template, request, url_for

from config import today_kst
from db import request_db
from services import study_service as ss

# app.py 에서 url_prefix="/study" 로 등록한다
bp = Blueprint("study", __name__)


@bp.get("")
def today():
    conn = request_db()
    day_no = ss.assign_today(conn, today_kst())
    cards = ss.build_cards(conn, day_no) if day_no else []

    if not cards:
        return render_template("study/today.html", state="empty")

    i = max(0, request.args.get("i", default=0, type=int))
    if i >= len(cards):
        return render_template("study/today.html", state="done", total=len(cards))

    return render_template(
        "study/today.html",
        state="card",
        day_no=day_no,
        card=cards[i],
        i=i,
        total=len(cards),
        show=request.args.get("show") == "1",
    )


@bp.post("/next")
def next_card():
    """현재 카드를 본 것으로 기록하고 다음 카드로 간다 (FR-014).

    기록할 일차는 서버가 오늘 기준으로 다시 구한다. 폼 값은 믿지 않는다.
    """
    conn = request_db()
    word_id = request.form.get("word_id", type=int)
    i = request.form.get("i", default=0, type=int)
    day_no = ss.assign_today(conn, today_kst())
    if word_id and day_no:
        try:
            ss.record_study(conn, word_id, day_no)
        except sqlite3.IntegrityError:
            # 기록 사이에 단어가 삭제됐다면 기록 없이 넘어간다
            conn.rollback()
    return redirect(url_for("study.today", i=i + 1))
