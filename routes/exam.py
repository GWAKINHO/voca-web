#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 시험 설정·출제·풀이·채점·결과 라우트 (VOCA-FR-021~026, 043)
# 파일 위치: routes/exam.py

from flask import Blueprint, abort, redirect, render_template, request, url_for

from db import request_db
from routes.auth import current_user_id
from services import exam_service as es
from services import settings_service as ssvc
from services.exam_service import ExamError, NotFoundError

# app.py 에서 url_prefix="/exam" 로 등록한다. 주소는 모두 url_for 로 만든다 (R-04)
bp = Blueprint("exam", __name__)


@bp.get("/new")
def new_form():
    conn = request_db()
    uid = current_user_id()
    word_count = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    cfg = ssvc.get_settings(conn, user_id=uid)
    return render_template(
        "exam/new.html",
        word_count=word_count,
        settings=cfg,
        err=request.args.get("err", ""),
    )


@bp.post("")
def create():
    conn = request_db()
    uid = current_user_id()
    raw_count = request.form.get("count", "").strip()
    try:
        count = int(raw_count)
    except ValueError:
        return redirect(url_for("exam.new_form", err="문제 수는 숫자로 입력하세요."))

    direction = request.form.get("direction", "en_ko")
    qtypes = request.form.getlist("qtype")

    try:
        attempt_id = es.create_attempt(conn, count, direction, qtypes, user_id=uid)
    except ExamError as e:
        return redirect(url_for("exam.new_form", err=str(e)))

    attempt = es.get_attempt(conn, attempt_id, user_id=uid)
    if attempt["total"] < count:
        return redirect(url_for("exam.take", attempt_id=attempt_id, requested=count))
    return redirect(url_for("exam.take", attempt_id=attempt_id))


@bp.get("/<int:attempt_id>")
def take(attempt_id):
    conn = request_db()
    uid = current_user_id()
    try:
        attempt = es.get_attempt(conn, attempt_id, user_id=uid)
    except NotFoundError:
        abort(404)

    if attempt["submitted_at"] is not None:
        return redirect(url_for("exam.result", attempt_id=attempt_id))

    items = es.get_items(conn, attempt_id, user_id=uid)
    requested = request.args.get("requested", type=int)
    notice = ""
    if requested and requested > attempt["total"]:
        notice = f"단어가 부족해 요청한 {requested}문제 대신 {attempt['total']}문제만 출제했습니다."

    return render_template(
        "exam/take.html",
        attempt=attempt,
        items=items,
        notice=notice,
    )


@bp.post("/<int:attempt_id>/submit")
def submit(attempt_id):
    conn = request_db()
    uid = current_user_id()
    try:
        items = es.get_items(conn, attempt_id, user_id=uid)
    except NotFoundError:
        abort(404)

    answers = {item["id"]: request.form.get(f"ans_{item['id']}", "") for item in items}
    es.grade(conn, attempt_id, answers, user_id=uid)
    return redirect(url_for("exam.result", attempt_id=attempt_id))


@bp.get("/<int:attempt_id>/result")
def result(attempt_id):
    conn = request_db()
    uid = current_user_id()
    try:
        attempt = es.get_attempt(conn, attempt_id, user_id=uid)
    except NotFoundError:
        abort(404)

    if attempt["submitted_at"] is None:
        return redirect(url_for("exam.take", attempt_id=attempt_id))

    items = es.get_items(conn, attempt_id, user_id=uid)
    wrong_items = [it for it in items if not it["is_correct"]]
    total = attempt["total"]
    correct = attempt["correct"] or 0
    percent = round(correct * 100 / total) if total else 0

    return render_template(
        "exam/result.html",
        attempt=attempt,
        items=items,
        wrong_items=wrong_items,
        percent=percent,
    )
