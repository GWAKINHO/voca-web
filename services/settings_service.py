#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습·시험 설정 조회·검증·DB 영속 저장 서비스 (VOCA-FR-061~062)
# 파일 위치: services/settings_service.py

from config import DAILY_COUNT, REVIEW_WRONG_COUNT, now_iso

DEFAULT_USER_ID = 0
DIRECTIONS = ("en_ko", "ko_en", "mixed")
QTYPES = ("short", "choice")

DEFAULTS = {
    "daily_count": DAILY_COUNT,
    "review_ratio": 50,
    "review_wrong_count": REVIEW_WRONG_COUNT,
    "exam_count": 10,
    "exam_direction": "en_ko",
    "exam_qtypes": "short,choice",
}


class SettingsError(ValueError):
    """설정 입력값 규칙 위반."""


def _with_computed(data: dict) -> dict:
    res = dict(data)
    res["exam_qtypes_list"] = [t for t in QTYPES if t in res["exam_qtypes"].split(",")]
    if not res["exam_qtypes_list"]:
        res["exam_qtypes_list"] = list(QTYPES)
    res["review_prev_count"] = round(res["daily_count"] * res["review_ratio"] / 100)
    return res


def get_settings(conn, user_id: int = DEFAULT_USER_ID) -> dict:
    """사용자의 학습·시험 설정을 돌려준다. 저장된 행이 없으면 기본값을 돌려준다."""
    row = conn.execute(
        "SELECT daily_count, review_ratio, review_wrong_count, "
        "exam_count, exam_direction, exam_qtypes "
        "FROM user_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return _with_computed(DEFAULTS)
    return _with_computed(dict(row))


def save_settings(
    conn,
    *,
    daily_count: int,
    review_ratio: int,
    review_wrong_count: int,
    exam_count: int,
    exam_direction: str,
    exam_qtypes,
    user_id: int = DEFAULT_USER_ID,
) -> dict:
    """설정값을 검증한 뒤 DB 에 영속 저장한다 (VOCA-FR-061~062)."""
    if not isinstance(daily_count, int) or not (1 <= daily_count <= 100):
        raise SettingsError("하루 학습량은 1~100 사이의 정수여야 합니다.")
    if not isinstance(review_ratio, int) or not (0 <= review_ratio <= 100):
        raise SettingsError("복습 비율은 0~100 사이의 정수여야 합니다.")
    if not isinstance(review_wrong_count, int) or not (0 <= review_wrong_count <= 20):
        raise SettingsError("자주 틀린 단어 복습 수는 0~20 사이의 정수여야 합니다.")
    if not isinstance(exam_count, int) or not (1 <= exam_count <= 50):
        raise SettingsError("시험 기본 문제 수는 1~50 사이의 정수여야 합니다.")
    if exam_direction not in DIRECTIONS:
        raise SettingsError("올바른 기본 출제 방향을 선택하세요.")

    selected = [t for t in QTYPES if t in (exam_qtypes or ())]
    if not selected:
        raise SettingsError("시험 기본 출제 형식을 하나 이상 선택하세요.")
    qtypes_str = ",".join(selected)

    conn.execute(
        "INSERT INTO user_settings "
        "(user_id, daily_count, review_ratio, review_wrong_count, "
        " exam_count, exam_direction, exam_qtypes, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "daily_count = excluded.daily_count, "
        "review_ratio = excluded.review_ratio, "
        "review_wrong_count = excluded.review_wrong_count, "
        "exam_count = excluded.exam_count, "
        "exam_direction = excluded.exam_direction, "
        "exam_qtypes = excluded.exam_qtypes, "
        "updated_at = excluded.updated_at",
        (
            user_id,
            daily_count,
            review_ratio,
            review_wrong_count,
            exam_count,
            exam_direction,
            qtypes_str,
            now_iso(),
        ),
    )
    conn.commit()
    return get_settings(conn, user_id=user_id)


def reset_settings(conn, user_id: int = DEFAULT_USER_ID) -> dict:
    """설정을 기본값으로 되돌린다."""
    conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
    conn.commit()
    return get_settings(conn, user_id=user_id)
