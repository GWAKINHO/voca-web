#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - Flask 앱 생성(create_app), DB 초기화, Blueprint 등록, 첫 화면
# 파일 위치: app.py

from flask import Flask, render_template

from config import DB_PATH, MAX_CONTENT_LENGTH, SECRET_KEY
from db import close_request_db, init_db
from routes.study import bp as study_bp
from routes.words import bp as words_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY=SECRET_KEY, MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH)

    # 처음 실행하면 테이블을 자동으로 만든다 (VOCA-NFR-003)
    init_db(DB_PATH)
    app.teardown_appcontext(close_request_db)

    app.register_blueprint(words_bp, url_prefix="/words")
    app.register_blueprint(study_bp, url_prefix="/study")

    @app.get("/")
    def index():
        # 첫 화면. 링크·주소는 "/" 기준 상대 경로로 쓴다 (VOCA-SUB-033)
        return render_template("index.html")

    return app


# gunicorn 은 "app:app" 으로 이 객체를 실행한다 (Dockerfile CMD 참고)
app = create_app()
