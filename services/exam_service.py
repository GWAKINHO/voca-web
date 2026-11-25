#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 시험 가중치 출제, 보기 생성, 채점 서비스 (VOCA-FR-021~026, D-6)
# 파일 위치: services/exam_service.py

import json
import random
from datetime import datetime, timedelta

from config import KST

MIN_QUESTIONS = 1
MAX_QUESTIONS = 50
DIRECTIONS = ("en_ko", "ko_en", "mixed")
QTYPES = ("short", "choice")
STALE_DAYS = 7


class ExamError(ValueError):
    """시험 입력·진행 규칙 위반."""


class NotFoundError(ExamError):
    """요청한 시험 회차가 없음."""


def _now(now=None) -> datetime:
    if now is None:
        return datetime.now(KST)
    return now.astimezone(KST) if now.tzinfo else now.replace(tzinfo=KST)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def word_weights(conn, now=None, user_id: int = 0) -> dict[int, int]:
    """모든 단어의 출제 가중치를 계정별로 계산한다 (D-6, FR-043).

    기본 1점 + 답한 기록 없음 +3 + 마지막 답변 7일 이상 전 +2 + 오답률 50% 이상 +2.
    """
    current = _now(now)
    word_ids = [r[0] for r in conn.execute("SELECT id FROM words ORDER BY id")]
    stats = {}
    rows = conn.execute(
        "SELECT ei.word_id, COUNT(*) AS total, "
        "SUM(CASE WHEN ei.is_correct = 0 THEN 1 ELSE 0 END) AS wrong, "
        "MAX(ei.answered_at) AS last_at "
        "FROM exam_item ei "
        "JOIN exam_attempt ea ON ea.id = ei.attempt_id "
        "WHERE ea.user_id = ? AND ei.word_id IS NOT NULL AND ei.is_correct IS NOT NULL "
        "GROUP BY ei.word_id",
        (user_id,),
    )
    for r in rows:
        stats[r["word_id"]] = r

    weights = {}
    for wid in word_ids:
        score = 1
        st = stats.get(wid)
        if st is None or st["total"] == 0:
            score += 3
        else:
            if st["last_at"]:
                last_dt = datetime.fromisoformat(st["last_at"])
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=KST)
                if current - last_dt >= timedelta(days=STALE_DAYS):
                    score += 2
            if st["wrong"] * 2 >= st["total"]:
                score += 2
        weights[wid] = score
    return weights


def _weighted_sample(words, weights_map, count, rng):
    """가중치 비례, 중복 없이 count 개를 추출한다."""
    pool = list(words)
    pool_w = [weights_map.get(w["id"], 1) for w in pool]
    picked = []
    for _ in range(min(count, len(pool))):
        chosen_idx = rng.choices(range(len(pool)), weights=pool_w, k=1)[0]
        picked.append(pool.pop(chosen_idx))
        pool_w.pop(chosen_idx)
    return picked


def _build_item(word, all_words, direction, qtype, rng):
    """문항 1개의 prompt, expected, choices(JSON) 스냅샷을 만든다."""
    actual_dir = rng.choice(("en_ko", "ko_en")) if direction == "mixed" else direction
    if actual_dir == "en_ko":
        prompt, expected = word["en"], word["ko"]
        distractors = list({w["ko"] for w in all_words if w["id"] != word["id"] and w["ko"] != expected})
    else:
        prompt, expected = word["ko"], word["en"]
        distractors = list({w["en"] for w in all_words if w["id"] != word["id"] and w["en"] != expected})

    actual_qtype = qtype
    choices_json = None
    if actual_qtype == "choice":
        if len(distractors) < 3:
            actual_qtype = "short"  # 보기 부족 시 단답형으로 전환 (FR-024)
        else:
            options = rng.sample(distractors, 3) + [expected]
            rng.shuffle(options)
            choices_json = json.dumps(options, ensure_ascii=False)

    return actual_qtype, actual_dir, prompt, expected, choices_json


def create_attempt(conn, count, direction, qtypes, *, now=None, rng=None, user_id: int = 0) -> int:
    """시험 1회를 출제해 exam_attempt 와 exam_item 을 저장하고 attempt_id 를 돌려준다."""
    if not isinstance(count, int) or count < MIN_QUESTIONS or count > MAX_QUESTIONS:
        raise ExamError(f"문제 수는 {MIN_QUESTIONS}~{MAX_QUESTIONS} 사이 정수여야 합니다.")
    if direction not in DIRECTIONS:
        raise ExamError("올바른 출제 방향을 선택하세요.")
    selected_types = [t for t in QTYPES if t in (qtypes or ())]
    if not selected_types:
        raise ExamError("출제 형식을 하나 이상 선택하세요.")

    all_words = [dict(r) for r in conn.execute("SELECT id, en, ko FROM words ORDER BY id")]
    if not all_words:
        raise ExamError("등록된 단어가 없습니다. 먼저 단어를 등록하세요.")

    current = _now(now)
    rand = rng or random.Random()
    weights_map = word_weights(conn, now=current, user_id=user_id)
    picked = _weighted_sample(all_words, weights_map, count, rand)

    stamp = _iso(current)
    cur = conn.execute(
        "INSERT INTO exam_attempt (user_id, created_at, submitted_at, direction, total, correct) "
        "VALUES (?, ?, NULL, ?, ?, NULL)",
        (user_id, stamp, direction, len(picked)),
    )
    attempt_id = cur.lastrowid

    items = []
    for seq, w in enumerate(picked, start=1):
        chosen_qtype = rand.choice(selected_types) if len(selected_types) > 1 else selected_types[0]
        actual_qtype, actual_dir, prompt, expected, choices_json = _build_item(
            w, all_words, direction, chosen_qtype, rand
        )
        items.append((attempt_id, seq, w["id"], actual_qtype, actual_dir, prompt, expected, choices_json))

    conn.executemany(
        "INSERT INTO exam_item "
        "(attempt_id, seq, word_id, qtype, direction, prompt, expected, choices) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        items,
    )
    conn.commit()
    return attempt_id


def get_attempt(conn, attempt_id: int, user_id: int | None = None) -> dict:
    row = conn.execute("SELECT * FROM exam_attempt WHERE id = ?", (attempt_id,)).fetchone()
    if row is None or (user_id is not None and row["user_id"] != user_id):
        raise NotFoundError("존재하지 않는 시험입니다.")
    return dict(row)


def get_items(conn, attempt_id: int, user_id: int | None = None) -> list[dict]:
    get_attempt(conn, attempt_id, user_id=user_id)  # 존재 및 소유 여부 확인
    rows = conn.execute(
        "SELECT * FROM exam_item WHERE attempt_id = ? ORDER BY seq", (attempt_id,)
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["choices_list"] = json.loads(item["choices"]) if item["choices"] else []
        result.append(item)
    return result


def _is_correct(item: dict, given: str) -> bool:
    ans = (given or "").strip()
    if not ans:
        return False
    if item["qtype"] == "choice":
        return ans == item["expected"]
    # 단답형 (D-10)
    if item["direction"] == "en_ko":
        targets = {part.strip().lower() for part in item["expected"].split(",") if part.strip()}
        return ans.lower() in targets
    return ans.lower() == item["expected"].strip().lower()


def grade(conn, attempt_id: int, answers: dict, *, now=None, user_id: int | None = None) -> dict:
    """시험 답안을 채점해 저장한다. 이미 제출된 시험은 재채점하지 않는다."""
    attempt = get_attempt(conn, attempt_id, user_id=user_id)
    if attempt["submitted_at"] is not None:
        return attempt

    items = get_items(conn, attempt_id, user_id=user_id)
    stamp = _iso(_now(now))
    correct_count = 0
    updates = []
    for item in items:
        raw_ans = answers.get(item["id"])
        if raw_ans is None:
            raw_ans = answers.get(str(item["id"]), "")
        given = str(raw_ans).strip()
        ok = 1 if _is_correct(item, given) else 0
        correct_count += ok
        updates.append((given, ok, stamp, item["id"]))

    conn.executemany(
        "UPDATE exam_item SET answer_given = ?, is_correct = ?, answered_at = ? WHERE id = ?",
        updates,
    )
    conn.execute(
        "UPDATE exam_attempt SET correct = ?, submitted_at = ? WHERE id = ?",
        (correct_count, stamp, attempt_id),
    )
    conn.commit()
    return get_attempt(conn, attempt_id)
