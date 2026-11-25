#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 일차 배정, 복습 카드 구성, 암기 기록 단위 테스트 (VOCA-FR-011~014)
# 파일 위치: tests/test_study_service.py

import os
import tempfile
import unittest

from db import get_db, init_db
from services import study_service as ss
from services import word_service as ws


def _add_words(conn, n):
    for i in range(1, n + 1):
        ws.add_word(conn, f"word{i:02d}", f"뜻{i}")


def _add_wrong_answers(conn, word_id, times):
    """시험 문항에서 해당 단어를 times 번 틀린 기록을 만든다."""
    cur = conn.execute(
        "INSERT INTO exam_attempt (created_at, direction, total, correct) "
        "VALUES ('x', 'en_ko', ?, 0)",
        (times,),
    )
    attempt_id = cur.lastrowid
    for seq in range(1, times + 1):
        conn.execute(
            "INSERT INTO exam_item (attempt_id, seq, word_id, qtype, direction, "
            "prompt, expected, is_correct) VALUES (?, ?, ?, 'short', 'en_ko', 'p', 'e', 0)",
            (attempt_id, seq, word_id),
        )
    conn.commit()


class StudyServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "test.db")
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _plan_ids(self, day_no):
        rows = self.conn.execute(
            "SELECT word_id FROM plan WHERE day_no = ? ORDER BY word_id", (day_no,)
        ).fetchall()
        return [r["word_id"] for r in rows]

    # FR-011: 단어가 없으면 배정하지 않는다
    def test_assign_returns_none_without_words(self):
        self.assertIsNone(ss.assign_today(self.conn, "2026-11-25"))
        count = self.conn.execute("SELECT COUNT(*) FROM study_day").fetchone()[0]
        self.assertEqual(count, 0)

    # FR-011, D-4: 하루 10개씩 일차를 배정한다
    def test_assign_first_day_takes_ten_words(self):
        _add_words(self.conn, 25)
        self.assertEqual(ss.assign_today(self.conn, "2026-11-25"), 1)
        self.assertEqual(self._plan_ids(1), list(range(1, 11)))

    # 같은 날 다시 열어도 재배정되지 않는다 (study_date UNIQUE)
    def test_assign_same_day_is_idempotent(self):
        _add_words(self.conn, 25)
        ss.assign_today(self.conn, "2026-11-25")
        self.assertEqual(ss.assign_today(self.conn, "2026-11-25"), 1)
        self.assertEqual(len(self._plan_ids(1)), 10)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM plan").fetchone()[0], 10)

    # FR-011: 다음 날은 다음 일차, 남은 단어만큼만 배정한다
    def test_next_day_takes_next_words_and_partial_last_day(self):
        _add_words(self.conn, 25)
        ss.assign_today(self.conn, "2026-11-25")
        self.assertEqual(ss.assign_today(self.conn, "2026-11-26"), 2)
        self.assertEqual(self._plan_ids(2), list(range(11, 21)))
        self.assertEqual(ss.assign_today(self.conn, "2026-11-27"), 3)
        self.assertEqual(self._plan_ids(3), list(range(21, 26)))
        self.assertIsNone(ss.assign_today(self.conn, "2026-11-28"))

    # FR-011: 첫 일차에는 복습 카드가 붙지 않는다
    def test_build_cards_day_one_has_no_review(self):
        _add_words(self.conn, 25)
        ss.assign_today(self.conn, "2026-11-25")
        cards = ss.build_cards(self.conn, 1)
        self.assertEqual([c["id"] for c in cards], list(range(1, 11)))

    # FR-013: 2일차에는 직전 일차 단어 중 최대 5개가 섞인다
    def test_build_cards_day_two_adds_five_from_previous_day(self):
        _add_words(self.conn, 25)
        ss.assign_today(self.conn, "2026-11-25")
        ss.assign_today(self.conn, "2026-11-26")
        ids = [c["id"] for c in ss.build_cards(self.conn, 2)]
        self.assertEqual(len(ids), 15)
        self.assertEqual(ids[:10], list(range(11, 21)))
        self.assertEqual(ids[10:], [1, 2, 3, 4, 5])
        self.assertEqual(len(set(ids)), len(ids))

    # FR-013, D-5: 오답 2회 이상인 단어를 최대 3개 섞고, 이미 있는 단어는 중복하지 않는다
    def test_build_cards_adds_frequent_wrong_words_without_duplicates(self):
        _add_words(self.conn, 25)
        for day in ("2026-11-25", "2026-11-26", "2026-11-27"):
            ss.assign_today(self.conn, day)
        _add_wrong_answers(self.conn, 4, 3)   # 3회: 가장 먼저
        _add_wrong_answers(self.conn, 3, 2)
        _add_wrong_answers(self.conn, 5, 2)
        _add_wrong_answers(self.conn, 6, 2)   # 상한 3개를 넘어 제외
        _add_wrong_answers(self.conn, 25, 2)  # 오늘 일차 단어라 중복 제외
        _add_wrong_answers(self.conn, 7, 1)   # 1회라 제외

        ids = [c["id"] for c in ss.build_cards(self.conn, 3)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(4, ids)
        self.assertIn(3, ids)
        self.assertIn(5, ids)
        self.assertNotIn(6, ids)
        self.assertNotIn(7, ids)
        # 오늘 일차 단어 5개 + 직전 일차 복습 5개 + 자주 틀린 단어 3개
        self.assertEqual(len(ids), 5 + 5 + 3)

    # FR-014: 카드를 넘기면 암기 기록에 단어, 일차, 시각이 남는다
    def test_record_study_saves_word_day_and_time(self):
        _add_words(self.conn, 3)
        ss.assign_today(self.conn, "2026-11-25")
        ss.record_study(self.conn, 2, 1)
        row = self.conn.execute("SELECT word_id, day_no, studied_at FROM study_log").fetchone()
        self.assertEqual(row["word_id"], 2)
        self.assertEqual(row["day_no"], 1)
        self.assertTrue(row["studied_at"].endswith("+09:00"))


if __name__ == "__main__":
    unittest.main()
