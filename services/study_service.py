#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 일차 배정, 오늘 카드 목록(복습 포함), 암기 기록 규칙 (VOCA-FR-011~014)
# 파일 위치: services/study_service.py

import sqlite3

from config import WRONG_THRESHOLD, now_iso
from services.settings_service import get_settings


def assign_today(conn, today: str, daily_count: int | None = None):
    """오늘 날짜의 일차를 돌려준다. 없으면 새 일차를 배정한다 (VOCA-FR-011, D-4).

    반환값이 None 이면 배정할 단어가 더 없다는 뜻이다.
    같은 날짜는 study_date UNIQUE 로 한 번만 배정된다 (데이터 설계서 §4.2).
    """
    row = conn.execute(
        "SELECT day_no FROM study_day WHERE study_date = ?", (today,)
    ).fetchone()
    if row:
        return row["day_no"]

    limit_count = daily_count if daily_count is not None else get_settings(conn)["daily_count"]

    # plan 에 없는 단어를 id 순으로 하루치만 뽑는다
    words = conn.execute(
        "SELECT w.id FROM words w LEFT JOIN plan p ON p.word_id = w.id "
        "WHERE p.word_id IS NULL ORDER BY w.id LIMIT ?",
        (limit_count,),
    ).fetchall()
    if not words:
        return None

    try:
        day_no = conn.execute(
            "SELECT COALESCE(MAX(day_no), 0) + 1 FROM study_day"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO study_day (day_no, study_date, created_at) VALUES (?, ?, ?)",
            (day_no, today, now_iso()),
        )
        conn.executemany(
            "INSERT INTO plan (word_id, day_no) VALUES (?, ?)",
            [(w["id"], day_no) for w in words],
        )
        conn.commit()
        return day_no
    except sqlite3.IntegrityError:
        # 다른 요청이 같은 날짜를 먼저 배정했다. 그 결과를 쓴다
        conn.rollback()
        row = conn.execute(
            "SELECT day_no FROM study_day WHERE study_date = ?", (today,)
        ).fetchone()
        return row["day_no"] if row else None


def build_cards(
    conn,
    day_no: int,
    review_prev_count: int | None = None,
    review_wrong_count: int | None = None,
):
    """오늘 보여 줄 카드 목록을 만든다. 순서는 오늘 일차, 직전 일차 복습, 자주 틀린 단어 복습.

    - 오늘 일차 단어 전부 (FR-011)
    - 2일차부터 직전 일차 단어 중 id 순 최대 review_prev_count 개 (FR-013, FR-061)
    - 자주 틀린 단어 최대 review_wrong_count 개: 시험 문항에서 오답 2회 이상, 오답 많은 순 (FR-013, D-5)
    같은 단어는 한 번만 넣는다.
    """
    cfg = get_settings(conn)
    prev_limit = cfg["review_prev_count"] if review_prev_count is None else review_prev_count
    wrong_limit = cfg["review_wrong_count"] if review_wrong_count is None else review_wrong_count

    cards = conn.execute(
        "SELECT w.id, w.en, w.ko FROM plan p JOIN words w ON w.id = p.word_id "
        "WHERE p.day_no = ? ORDER BY w.id",
        (day_no,),
    ).fetchall()
    seen = {r["id"] for r in cards}

    if day_no > 1 and prev_limit > 0:
        prev = conn.execute(
            "SELECT w.id, w.en, w.ko FROM plan p JOIN words w ON w.id = p.word_id "
            "WHERE p.day_no = ? ORDER BY w.id LIMIT ?",
            (day_no - 1, prev_limit),
        ).fetchall()
        for r in prev:
            if r["id"] not in seen:
                cards.append(r)
                seen.add(r["id"])

    if wrong_limit > 0:
        # 후보를 넉넉히 가져온 뒤 중복을 거르고 상한만큼 자른다
        wrong = conn.execute(
            "SELECT w.id, w.en, w.ko FROM exam_item i JOIN words w ON w.id = i.word_id "
            "WHERE i.is_correct = 0 GROUP BY w.id HAVING COUNT(*) >= ? "
            "ORDER BY COUNT(*) DESC, w.id LIMIT ?",
            (WRONG_THRESHOLD, wrong_limit + len(seen)),
        ).fetchall()
        added = 0
        for r in wrong:
            if added >= wrong_limit:
                break
            if r["id"] not in seen:
                cards.append(r)
                seen.add(r["id"])
                added += 1

    return cards


def record_study(conn, word_id: int, day_no: int) -> None:
    """카드를 넘길 때 암기 기록을 남긴다 (VOCA-FR-014). 기록 일차는 오늘 일차다 (D-8)."""
    conn.execute(
        "INSERT INTO study_log (word_id, day_no, studied_at) VALUES (?, ?, ?)",
        (word_id, day_no, now_iso()),
    )
    conn.commit()
