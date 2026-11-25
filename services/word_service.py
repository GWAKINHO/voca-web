#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 단어 등록·수정·삭제·검색 규칙 (VOCA-FR-001~002, 004)
# 파일 위치: services/word_service.py

from config import WORDS_PER_PAGE, now_iso


class WordError(ValueError):
    """사용자 입력 오류. 화면에 그대로 보여 준다."""


class DuplicateWordError(WordError):
    """같은 영단어가 이미 있다 (D-1: 대소문자·앞뒤 공백 무시)."""


class NotFoundError(WordError):
    """대상 단어가 없다."""


def normalize_key(en: str) -> str:
    """중복 판정용 키. 앞뒤 공백을 지우고 소문자로 만든다 (데이터 설계서 §5.1)."""
    return en.strip().lower()


def _clean(en, ko):
    en = (en or "").strip()
    ko = (ko or "").strip()
    if not en or not ko:
        raise WordError("영단어와 뜻을 모두 입력하세요.")
    return en, ko


def add_word(conn, en, ko) -> int:
    """단어를 등록하고 새 id 를 돌려준다 (VOCA-FR-001)."""
    en, ko = _clean(en, ko)
    key = normalize_key(en)
    if conn.execute("SELECT 1 FROM words WHERE en_key = ?", (key,)).fetchone():
        raise DuplicateWordError(f"이미 있는 단어입니다: {en}")
    cur = conn.execute(
        "INSERT INTO words (en, ko, en_key, created_at) VALUES (?, ?, ?, ?)",
        (en, ko, key, now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def get_word(conn, word_id):
    row = conn.execute(
        "SELECT id, en, ko FROM words WHERE id = ?", (word_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("단어를 찾을 수 없습니다.")
    return row


def update_word(conn, word_id, en, ko) -> None:
    """단어를 고친다 (VOCA-FR-002). 자기 자신과의 중복은 허용한다."""
    get_word(conn, word_id)
    en, ko = _clean(en, ko)
    key = normalize_key(en)
    clash = conn.execute(
        "SELECT id FROM words WHERE en_key = ? AND id != ?", (key, word_id)
    ).fetchone()
    if clash:
        raise DuplicateWordError(f"이미 있는 단어입니다: {en}")
    conn.execute(
        "UPDATE words SET en = ?, ko = ?, en_key = ? WHERE id = ?",
        (en, ko, key, word_id),
    )
    conn.commit()


def delete_word(conn, word_id) -> None:
    """단어와 배정·암기 기록을 지운다. 시험 문항은 남기고 연결만 끊는다 (D-3, 데이터 설계서 §6)."""
    get_word(conn, word_id)
    conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
    conn.commit()


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_words(conn, q: str = "", page: int = 1, per_page: int = WORDS_PER_PAGE):
    """단어 목록과 전체 개수를 돌려준다. 영단어 또는 뜻에 검색어가 들어 있으면 고른다 (VOCA-FR-004)."""
    page = max(1, page)
    offset = (page - 1) * per_page
    q = (q or "").strip()
    if q:
        pattern = _like_pattern(q)
        where = "WHERE en LIKE ? ESCAPE '\\' OR ko LIKE ? ESCAPE '\\'"
        params = (pattern, pattern)
    else:
        where = ""
        params = ()
    total = conn.execute(
        f"SELECT COUNT(*) FROM words {where}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT id, en, ko FROM words {where} ORDER BY id LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()
    return rows, total
