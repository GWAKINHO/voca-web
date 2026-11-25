#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습 진척 통계 집계 서비스 (VOCA-FR-031~034, FR-043)
# 파일 위치: services/stats_service.py

TOP_WRONG_LIMIT = 10


def get_progress(conn, user_id: int = 0) -> dict:
    """현재 일차와 암기한 단어 수 / 전체 단어 수를 계정별로 계산한다 (FR-031, FR-034, FR-043)."""
    current_day = conn.execute(
        "SELECT COALESCE(MAX(day_no), 0) FROM study_day WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    studied_words = conn.execute(
        "SELECT COUNT(DISTINCT word_id) FROM study_log WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    percent = round(studied_words * 100 / total_words) if total_words else 0
    return {
        "current_day": current_day,
        "studied_words": studied_words,
        "total_words": total_words,
        "percent": percent,
    }


def get_exam_trend(conn, user_id: int = 0) -> list[dict]:
    """제출된 시험의 회차별 날짜와 정답률을 계정별로 반환한다 (FR-032, FR-034, FR-043)."""
    rows = conn.execute(
        "SELECT id, submitted_at, direction, total, correct "
        "FROM exam_attempt "
        "WHERE user_id = ? AND submitted_at IS NOT NULL "
        "ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    result = []
    for r in rows:
        total = r["total"] or 0
        correct = r["correct"] or 0
        result.append(
            {
                "id": r["id"],
                "date": r["submitted_at"][:10],
                "submitted_at": r["submitted_at"],
                "direction": r["direction"],
                "total": total,
                "correct": correct,
                "percent": round(correct * 100 / total) if total else 0,
            }
        )
    return result


def get_daily_exam_trend(conn, user_id: int = 0) -> list[dict]:
    """제출된 시험을 한국 시간 날짜(YYYY-MM-DD)별로 묶어 정답률을 계산한다 (FR-032, FR-043)."""
    rows = conn.execute(
        "SELECT substr(submitted_at, 1, 10) AS exam_date, "
        "COUNT(*) AS attempts, SUM(total) AS total, SUM(correct) AS correct "
        "FROM exam_attempt "
        "WHERE user_id = ? AND submitted_at IS NOT NULL "
        "GROUP BY exam_date "
        "ORDER BY exam_date DESC",
        (user_id,),
    ).fetchall()
    result = []
    for r in rows:
        total = r["total"] or 0
        correct = r["correct"] or 0
        result.append(
            {
                "date": r["exam_date"],
                "attempts": r["attempts"],
                "total": total,
                "correct": correct,
                "percent": round(correct * 100 / total) if total else 0,
            }
        )
    return result


def get_top_wrong_words(conn, limit: int = TOP_WRONG_LIMIT, user_id: int = 0) -> list[dict]:
    """오답이 많은 단어를 계정별 상위 N개 반환한다. 삭제된 단어는 제외한다 (FR-033, FR-043)."""
    rows = conn.execute(
        "SELECT w.id, w.en, w.ko, "
        "SUM(CASE WHEN ei.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count, "
        "COUNT(*) AS total_count "
        "FROM exam_item ei "
        "JOIN exam_attempt ea ON ea.id = ei.attempt_id "
        "JOIN words w ON w.id = ei.word_id "
        "WHERE ea.user_id = ? AND ei.word_id IS NOT NULL AND ei.is_correct IS NOT NULL "
        "GROUP BY w.id, w.en, w.ko "
        "HAVING wrong_count > 0 "
        "ORDER BY wrong_count DESC, total_count DESC, w.id ASC "
        "LIMIT ?",
        (user_id, limit),
    ).fetchall()
    result = []
    for r in rows:
        total = r["total_count"] or 0
        wrong = r["wrong_count"] or 0
        result.append(
            {
                "id": r["id"],
                "en": r["en"],
                "ko": r["ko"],
                "wrong_count": wrong,
                "total_count": total,
                "wrong_rate": round(wrong * 100 / total) if total else 0,
            }
        )
    return result
