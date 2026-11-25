#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 공개 사용자 순위표 및 읽기 전용 통계 조회 서비스 (VOCA-FR-051~053)
# 파일 위치: services/ranking_service.py

from services import stats_service as st


def list_public_ranking(conn) -> list[dict]:
    """공개를 허용한(is_public = 1) 사용자들의 학습 진척 요약 순위표를 반환한다 (FR-051, FR-052).

    비공개 사용자(is_public = 0)는 절대 포함하지 않는다.
    """
    users = conn.execute(
        "SELECT id, username, created_at FROM users WHERE is_public = 1 ORDER BY id ASC"
    ).fetchall()
    total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    ranking = []
    for u in users:
        uid = u["id"]
        prog = st.get_progress(conn, user_id=uid)
        exam_row = conn.execute(
            "SELECT COUNT(*) AS attempts, COALESCE(SUM(total), 0) AS total, "
            "COALESCE(SUM(correct), 0) AS correct "
            "FROM exam_attempt "
            "WHERE user_id = ? AND submitted_at IS NOT NULL",
            (uid,),
        ).fetchone()
        exam_total = exam_row["total"] or 0
        exam_correct = exam_row["correct"] or 0
        avg_accuracy = round(exam_correct * 100 / exam_total) if exam_total else 0

        ranking.append(
            {
                "id": uid,
                "username": u["username"],
                "current_day": prog["current_day"],
                "studied_words": prog["studied_words"],
                "total_words": total_words,
                "progress_percent": prog["percent"],
                "exam_attempts": exam_row["attempts"] or 0,
                "avg_accuracy": avg_accuracy,
            }
        )

    ranking.sort(
        key=lambda r: (-r["studied_words"], -r["avg_accuracy"], -r["exam_attempts"], r["id"])
    )
    return ranking


def get_public_user_stats(conn, target_user_id: int):
    """공개된(is_public = 1) 특정 사용자의 학습 진척 통계를 읽기 전용으로 반환한다 (FR-051~053).

    존재하지 않거나 비공개(is_public = 0) 사용자이면 None 을 반환한다.
    """
    row = conn.execute(
        "SELECT id, username, is_public, created_at FROM users WHERE id = ?",
        (target_user_id,),
    ).fetchone()
    if row is None or not row["is_public"]:
        return None

    uid = row["id"]
    return {
        "user": {"id": uid, "username": row["username"]},
        "progress": st.get_progress(conn, user_id=uid),
        "attempts": st.get_exam_trend(conn, user_id=uid),
        "daily": st.get_daily_exam_trend(conn, user_id=uid),
        "top_wrong": st.get_top_wrong_words(conn, user_id=uid),
    }
