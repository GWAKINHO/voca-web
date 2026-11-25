#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 시험 설정·출제·풀이·채점·결과 라우트 (VOCA-FR-021~026)
# 파일 위치: routes/exam.py

from flask import Blueprint, abort, redirect, render_template, request, url_for

from db import request_db
from services import exam_service as es
from services.exam_service import ExamError, NotFoundError

# app.py 에서 url_prefix="/exam" 로 등록한다. 주소는 모두 url_for 로 만든다 (R-04)
bp = Blueprint("exam", __name__)


@bp.get("/new")
def new_form():
    conn = request_db()
    word_count = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    return render_template(
        "exam/new.html",
        word_count=word_count,
        err=request.args.get("err", ""),
    )


@bp.post("")
def create():
    conn = request_db()
    raw_count = request.form.get("count", "").strip()
    try:
        count = int(raw_count)
    except ValueError:
        return redirect(url_for("exam.new_form", err="문제 수는 숫자로 입력하세요."))

    direction = request.form.get("direction", "en_ko")
    qtypes = request.form.getlist("qtype")

    try:
        attempt_id = es.create_attempt(conn, count, direction, qtypes)
    except ExamError as e:
        return redirect(url_for("exam.new_form", err=str(e)))

    attempt = es.get_attempt(conn, attempt_id)
    if attempt["total"] < count:
        return redirect(url_for("exam.take", attempt_id=attempt_id, requested=count))
    return redirect(url_for("exam.take", attempt_id=attempt_id))


@bp.get("/<int:attempt_id>")
def take(attempt_id):
    conn = request_db()
    try:
        attempt = es.get_attempt(conn, attempt_id)
    except NotFoundError:
        abort(404)

    # 이미 제출된 시험은 결과 화면으로 보낸다 (데이터 설계서 §4.5)
    if attempt["submitted_at"] is not None:
        return redirect(url_for("exam.result", attempt_id=attempt_id))

    items = es.get_items(conn, attempt_id)
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
    try:
        items = es.get_items(conn, attempt_id)
    except NotFoundError:
        abort(404)

    answers = {item["id"]: request.form.get(f"ans_{item['id']}", "") for item in items}
    es.grade(conn, attempt_id, answers)
    return redirect(url_for("exam.result", attempt_id=attempt_id))


@bp.get("/<int:attempt_id>/result")
def result(attempt_id):
    conn = request_db()
    try:
        attempt = es.get_attempt(conn, attempt_id)
    except NotFoundError:
        abort(404)

    if attempt["submitted_at"] is None:
        return redirect(url_for("exam.take", attempt_id=attempt_id))

    items = es.get_items(conn, attempt_id)
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
