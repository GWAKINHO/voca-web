#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습 진척 통계 및 전체 초기화 단위 테스트 (VOCA-FR-031~034, §6.1)
# 파일 위치: tests/test_stats_service.py

import os
import random
import tempfile
import unittest
from datetime import datetime

from config import KST
from db import SCHEMA_VERSION, get_db, init_db
from services import exam_service as es
from services import stats_service as st
from services import study_service as ss
from services import word_service as ws


class StatsAndResetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "test.db")
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    # FR-031: 진도 현황 (중복 암기 기록은 단어 기준 1회로 집계)
    def test_progress_counts_distinct_studied_words(self):
        self.assertEqual(
            st.get_progress(self.conn),
            {"current_day": 0, "studied_words": 0, "total_words": 0, "percent": 0},
        )
        ids = [ws.add_word(self.conn, f"w{i}", f"뜻{i}") for i in range(4)]
        day_no = ss.assign_today(self.conn, "2026-11-25")
        ss.record_study(self.conn, ids[0], day_no)
        ss.record_study(self.conn, ids[0], day_no)  # 같은 단어 두 번 기록
        ss.record_study(self.conn, ids[1], day_no)

        prog = st.get_progress(self.conn)
        self.assertEqual(prog["current_day"], 1)
        self.assertEqual(prog["studied_words"], 2)
        self.assertEqual(prog["total_words"], 4)
        self.assertEqual(prog["percent"], 50)

    # FR-032: 회차별·날짜별 정답률 (미제출 시험은 제외)
    def test_exam_trends_ignore_unsubmitted_and_group_by_date(self):
        for i in range(4):
            ws.add_word(self.conn, f"w{i}", f"뜻{i}")

        t1 = datetime(2026, 11, 25, 10, 0, tzinfo=KST)
        t2 = datetime(2026, 11, 25, 14, 0, tzinfo=KST)
        t3 = datetime(2026, 11, 26, 9, 0, tzinfo=KST)

        # 미제출 시험 -> 통계 제외
        es.create_attempt(self.conn, 2, "en_ko", ["short"], now=t1, rng=random.Random(1))

        # 11-25 1회차: 2/2 (100%)
        a1 = es.create_attempt(self.conn, 2, "en_ko", ["short"], now=t1, rng=random.Random(2))
        items1 = es.get_items(self.conn, a1)
        es.grade(self.conn, a1, {it["id"]: it["expected"] for it in items1}, now=t1)

        # 11-25 2회차: 0/2 (0%) -> 11-25 합계 2/4 (50%)
        a2 = es.create_attempt(self.conn, 2, "en_ko", ["short"], now=t2, rng=random.Random(3))
        es.grade(self.conn, a2, {}, now=t2)

        # 11-26 3회차: 1/2 (50%)
        a3 = es.create_attempt(self.conn, 2, "en_ko", ["short"], now=t3, rng=random.Random(4))
        items3 = es.get_items(self.conn, a3)
        es.grade(self.conn, a3, {items3[0]["id"]: items3[0]["expected"]}, now=t3)

        attempts = st.get_exam_trend(self.conn)
        self.assertEqual(len(attempts), 3)
        self.assertEqual([a["id"] for a in attempts], [a3, a2, a1])
        self.assertEqual([a["percent"] for a in attempts], [50, 0, 100])

        daily = st.get_daily_exam_trend(self.conn)
        self.assertEqual(len(daily), 2)
        self.assertEqual(daily[0]["date"], "2026-11-26")
        self.assertEqual(daily[0]["percent"], 50)
        self.assertEqual(daily[1]["date"], "2026-11-25")
        self.assertEqual(daily[1]["attempts"], 2)
        self.assertEqual(daily[1]["percent"], 50)

    # FR-033: 자주 틀린 단어 상위 10개, 삭제된 단어(word_id NULL) 제외
    def test_top_wrong_words_excludes_deleted_and_limits_to_ten(self):
        ids = [ws.add_word(self.conn, f"w{i:02d}", f"뜻{i}") for i in range(12)]
        now = datetime(2026, 11, 25, 15, 0, tzinfo=KST)
        # 2회 오답 제출 (모든 단어 2회씩 틀림, w00은 3회 틀림, w01은 삭제)
        for seed in (1, 2):
            aid = es.create_attempt(self.conn, 12, "en_ko", ["short"], now=now, rng=random.Random(seed))
            es.grade(self.conn, aid, {}, now=now)
        # w00 에 오답 1회 추가
        self.conn.execute(
            "INSERT INTO exam_item (attempt_id, seq, word_id, qtype, direction, prompt, expected, is_correct, answered_at) "
            "VALUES (1, 99, ?, 'short', 'en_ko', 'w00', '뜻0', 0, ?)",
            (ids[0], now.isoformat(timespec="seconds")),
        )
        self.conn.commit()
        ws.delete_word(self.conn, ids[1])  # w01 삭제 -> word_id NULL

        top = st.get_top_wrong_words(self.conn, limit=10)
        self.assertEqual(len(top), 10)
        self.assertEqual(top[0]["en"], "w00")
        self.assertEqual(top[0]["wrong_count"], 3)
        self.assertNotIn("w01", [w["en"] for w in top])

    # 데이터 설계서 §6.1: 전체 초기화 ("전체삭제" 정확 일치 시에만 6개 테이블 삭제, 스키마 버전 유지)
    def test_reset_all_data_requires_exact_confirm_and_clears_all_tables(self):
        wid = ws.add_word(self.conn, "apple", "사과")
        day_no = ss.assign_today(self.conn, "2026-11-25")
        ss.record_study(self.conn, wid, day_no)
        aid = es.create_attempt(self.conn, 1, "en_ko", ["short"], rng=random.Random(1))
        es.grade(self.conn, aid, {})

        with self.assertRaises(ws.WordError):
            ws.reset_all_data(self.conn, "삭제")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0], 1)

        ws.reset_all_data(self.conn, "전체삭제")
        for tbl in ("exam_item", "exam_attempt", "study_log", "plan", "study_day", "words"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
