#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - SQLite 연결, 테이블 생성(데이터 설계서 기준), 요청별 연결 관리
# 파일 위치: db.py

import os
import sqlite3

from config import DB_PATH

SCHEMA_VERSION = 2  # PRAGMA user_version 에 기록한다 (데이터 설계서 §1)

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  en TEXT NOT NULL,
  ko TEXT NOT NULL,
  en_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS study_day (
  day_no INTEGER PRIMARY KEY,
  study_date TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan (
  word_id INTEGER PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
  day_no INTEGER NOT NULL REFERENCES study_day(day_no)
);
CREATE INDEX IF NOT EXISTS idx_plan_day ON plan(day_no);
CREATE TABLE IF NOT EXISTS study_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  day_no INTEGER NOT NULL,
  studied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_study_word ON study_log(word_id);
CREATE INDEX IF NOT EXISTS idx_study_day ON study_log(day_no);
CREATE TABLE IF NOT EXISTS exam_attempt (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  submitted_at TEXT,
  direction TEXT NOT NULL CHECK (direction IN ('en_ko', 'ko_en', 'mixed')),
  total INTEGER NOT NULL,
  correct INTEGER
);
CREATE INDEX IF NOT EXISTS idx_attempt_submitted ON exam_attempt(submitted_at);
CREATE TABLE IF NOT EXISTS exam_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id INTEGER NOT NULL REFERENCES exam_attempt(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  word_id INTEGER REFERENCES words(id) ON DELETE SET NULL,
  qtype TEXT NOT NULL CHECK (qtype IN ('short', 'choice')),
  direction TEXT NOT NULL CHECK (direction IN ('en_ko', 'ko_en')),
  prompt TEXT NOT NULL,
  expected TEXT NOT NULL,
  choices TEXT,
  answer_given TEXT,
  is_correct INTEGER CHECK (is_correct IN (0, 1)),
  answered_at TEXT,
  UNIQUE (attempt_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_item_attempt ON exam_item(attempt_id);
CREATE INDEX IF NOT EXISTS idx_item_word ON exam_item(word_id);
CREATE TABLE IF NOT EXISTS user_settings (
  user_id INTEGER PRIMARY KEY,
  daily_count INTEGER NOT NULL DEFAULT 10,
  review_ratio INTEGER NOT NULL DEFAULT 50,
  review_wrong_count INTEGER NOT NULL DEFAULT 3,
  exam_count INTEGER NOT NULL DEFAULT 10,
  exam_direction TEXT NOT NULL DEFAULT 'en_ko' CHECK (exam_direction IN ('en_ko', 'ko_en', 'mixed')),
  exam_qtypes TEXT NOT NULL DEFAULT 'short,choice',
  updated_at TEXT NOT NULL
);
"""


def get_db(path=None):
    """SQLite 연결을 연다. 외래키 제약을 켜고, 잠금 대기 5초를 설정한다 (아키텍처 §8)."""
    path = path or DB_PATH
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=None):
    """테이블이 없으면 만든다. 여러 번 실행해도 안전하다 (VOCA-NFR-003)."""
    conn = get_db(path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def request_db():
    """요청마다 하나의 연결을 `flask.g` 에 보관해 돌려준다."""
    from flask import g

    if "db" not in g:
        g.db = get_db()
    return g.db


def close_request_db(_exc=None):
    """요청이 끝나면 연결을 닫는다. app.teardown_appcontext 에 등록한다."""
    from flask import g

    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
