#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습·시험 설정 화면 및 저장 라우트 (VOCA-FR-061~062)
# 파일 위치: routes/settings.py

from flask import Blueprint, g, redirect, render_template, request, url_for

from db import request_db
from routes.auth import current_user, current_user_id
from services import auth_service as auth
from services import settings_service as ssvc
from services.auth_service import AuthError
from services.settings_service import SettingsError

# app.py 에서 url_prefix="/settings" 로 등록한다. 주소는 모두 url_for 로 만든다 (R-04)
bp = Blueprint("settings", __name__)


def _parse_int(name: str, label: str) -> int:
    raw = request.form.get(name, "").strip()
    try:
        return int(raw)
    except ValueError:
        raise SettingsError(f"{label}은(는) 숫자로 입력하세요.")


@bp.get("")
def index():
    conn = request_db()
    uid = current_user_id()
    return render_template(
        "settings/index.html",
        settings=ssvc.get_settings(conn, user_id=uid),
        msg=request.args.get("msg", ""),
        err=request.args.get("err", ""),
    )


@bp.post("")
def save():
    conn = request_db()
    uid = current_user_id()
    try:
        daily_count = _parse_int("daily_count", "하루 학습량")
        review_ratio = _parse_int("review_ratio", "복습 비율")
        review_wrong_count = _parse_int("review_wrong_count", "자주 틀린 단어 복습 수")
        exam_count = _parse_int("exam_count", "시험 기본 문제 수")
        exam_direction = request.form.get("exam_direction", "en_ko")
        exam_qtypes = request.form.getlist("exam_qtypes")

        ssvc.save_settings(
            conn,
            daily_count=daily_count,
            review_ratio=review_ratio,
            review_wrong_count=review_wrong_count,
            exam_count=exam_count,
            exam_direction=exam_direction,
            exam_qtypes=exam_qtypes,
            user_id=uid,
        )
    except SettingsError as e:
        return redirect(url_for("settings.index", err=str(e)))
    return redirect(url_for("settings.index", msg="설정을 저장했습니다."))


@bp.post("/reset")
def reset():
    conn = request_db()
    ssvc.reset_settings(conn, user_id=current_user_id())
    return redirect(url_for("settings.index", msg="설정을 기본값으로 되돌렸습니다."))


@bp.post("/privacy")
def update_privacy():
    """로그인 사용자의 학습 통계 공개/비공개 여부를 변경한다 (VOCA-FR-052)."""
    user = current_user()
    if user is None:
        return redirect(url_for("settings.index", err="로그인한 사용자만 공개 설정을 변경할 수 있습니다."))
    is_public = request.form.get("is_public") == "1"
    try:
        auth.set_public(request_db(), user["id"], is_public)
        g.current_user = auth.get_user(request_db(), user["id"])
    except AuthError as e:
        return redirect(url_for("settings.index", err=str(e)))
    status_label = "공개" if is_public else "비공개"
    return redirect(url_for("settings.index", msg=f"학습 통계 공개 설정을 '{status_label}'로 변경했습니다."))
