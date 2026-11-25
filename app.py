#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 단어장 웹 앱의 첫 화면을 제공하는 Flask 진입점
# 파일 위치: app.py

from flask import Flask, render_template

# gunicorn 은 "app:app" 으로 이 객체를 실행한다 (Dockerfile CMD 참고)
app = Flask(__name__)


@app.get("/")
def index():
    # 첫 화면. 링크·주소는 모두 "/" 기준 상대 경로로 쓴다 (VOCA-SUB-033)
    return render_template("index.html")
