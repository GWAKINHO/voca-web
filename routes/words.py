#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 단어 목록·등록·수정·삭제 라우트 (VOCA-FR-001, 002, 004)
# 파일 위치: routes/words.py

from flask import Blueprint, redirect, render_template, request, url_for

from config import WORDS_PER_PAGE
from db import request_db
from services import word_import as wi
from services import word_service as ws
from services.word_service import WordError

MAX_ERRORS_SHOWN = 20  # 가져오기 오류는 최대 이만큼만 화면에 보인다

# app.py 에서 url_prefix="/words" 로 등록한다. 주소는 모두 url_for 로 만든다 (R-04)
bp = Blueprint("words", __name__)


def _back(msg="", err=""):
    """목록 화면으로 돌아간다. 검색어와 페이지는 유지하지 않는다 (단순함 우선)."""
    return redirect(url_for("words.list_words", msg=msg, err=err))


def _render_list(**extra):
    q = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", default=1, type=int))
    rows, total = ws.list_words(request_db(), q=q, page=page)
    pages = max(1, -(-total // WORDS_PER_PAGE))  # 올림 나눗셈
    context = dict(
        rows=rows,
        q=q,
        page=page,
        pages=pages,
        total=total,
        msg=request.args.get("msg", ""),
        err=request.args.get("err", ""),
    )
    context.update(extra)
    return render_template("words/list.html", **context)


@bp.get("")
def list_words():
    return _render_list()


@bp.post("/import")
def import_csv():
    """CSV 파일을 메모리에서 읽어 일괄 등록한다 (FR-003). 디스크에 저장하지 않는다 (A-7)."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _render_list(err="CSV 파일을 선택하세요.")
    raw = upload.stream.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _render_list(err="UTF-8 인코딩 CSV 파일만 가져올 수 있습니다.")

    result = wi.import_csv_text(request_db(), text)
    result["error_total"] = len(result["errors"])
    result["errors"] = result["errors"][:MAX_ERRORS_SHOWN]
    return _render_list(import_result=result)


@bp.post("")
def create_word():
    try:
        ws.add_word(request_db(), request.form.get("en"), request.form.get("ko"))
    except WordError as e:
        return _back(err=str(e))
    return _back(msg="단어를 등록했습니다.")


@bp.post("/<int:word_id>/edit")
def edit_word(word_id):
    try:
        ws.update_word(
            request_db(), word_id, request.form.get("en"), request.form.get("ko")
        )
    except WordError as e:
        return _back(err=str(e))
    return _back(msg="단어를 수정했습니다.")


@bp.post("/<int:word_id>/delete")
def delete_word(word_id):
    try:
        ws.delete_word(request_db(), word_id)
    except WordError as e:
        return _back(err=str(e))
    return _back(msg="단어와 관련 이력을 삭제했습니다.")


@bp.post("/reset")
def reset_all():
    """단어장과 모든 학습·시험 이력을 초기화한다 (데이터 설계서 §6.1)."""
    try:
        ws.reset_all_data(request_db(), request.form.get("confirm_text", ""))
    except WordError as e:
        return _back(err=str(e))
    return _back(msg="단어장과 모든 학습·시험 이력을 초기화했습니다.")
