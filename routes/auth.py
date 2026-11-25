#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 회원 가입·로그인·로그아웃 라우트 및 세션 헬퍼 (VOCA-FR-041~043)
# 파일 위치: routes/auth.py

from flask import Blueprint, g, redirect, render_template, request, session, url_for

from db import request_db
from services import auth_service as auth
from services.auth_service import AuthError

# app.py 에서 url_prefix="/auth" 로 등록한다. 주소는 모두 url_for 로 만든다 (R-04)
bp = Blueprint("auth", __name__)


def current_user():
    """현재 로그인한 사용자 dict 를 돌려준다. 비로그인이면 None."""
    if "current_user" not in g:
        uid = session.get("user_id")
        if isinstance(uid, int) and uid > 0:
            user = auth.get_user(request_db(), uid)
            if user is None:
                session.pop("user_id", None)
            g.current_user = user
        else:
            g.current_user = None
    return g.current_user


def current_user_id() -> int:
    """현재 로그인한 사용자의 id 를 돌려준다. 비로그인이면 0 (게스트)."""
    user = current_user()
    return user["id"] if user else 0


@bp.get("/register")
def register_form():
    if current_user():
        return redirect(url_for("index"))
    return render_template("auth/register.html", err=request.args.get("err", ""))


@bp.post("/register")
def register():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    is_public = request.form.get("is_public") == "1"

    if password != password_confirm:
        return redirect(url_for("auth.register_form", err="비밀번호 확인이 일치하지 않습니다."))

    try:
        user = auth.register(request_db(), username, password, is_public=is_public)
    except AuthError as e:
        return redirect(url_for("auth.register_form", err=str(e)))

    session["user_id"] = user["id"]
    g.current_user = user
    return redirect(url_for("index"))


@bp.get("/login")
def login_form():
    if current_user():
        return redirect(url_for("index"))
    return render_template(
        "auth/login.html",
        msg=request.args.get("msg", ""),
        err=request.args.get("err", ""),
    )


@bp.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    try:
        user = auth.authenticate(request_db(), username, password)
    except AuthError as e:
        return redirect(url_for("auth.login_form", err=str(e)))

    session["user_id"] = user["id"]
    g.current_user = user
    return redirect(url_for("index"))


@bp.post("/logout")
def logout():
    session.pop("user_id", None)
    g.current_user = None
    return redirect(url_for("index"))
