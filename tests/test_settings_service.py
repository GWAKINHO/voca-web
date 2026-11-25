#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 학습·시험 설정 단위 테스트 (VOCA-FR-061~062)
# 파일 위치: tests/test_settings_service.py

import os
import tempfile
import unittest

from db import get_db, init_db
from services import settings_service as ssvc
from services import study_service as ss
from services import word_service as ws


class SettingsServiceTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_defaults_returned_when_no_row_exists(self):
        cfg = ssvc.get_settings(self.conn)
        self.assertEqual(cfg["daily_count"], 10)
        self.assertEqual(cfg["review_ratio"], 50)
        self.assertEqual(cfg["review_prev_count"], 5)
        self.assertEqual(cfg["review_wrong_count"], 3)
        self.assertEqual(cfg["exam_count"], 10)
        self.assertEqual(cfg["exam_direction"], "en_ko")
        self.assertEqual(cfg["exam_qtypes_list"], ["short", "choice"])

    def test_save_and_persist_across_connections(self):
        saved = ssvc.save_settings(
            self.conn,
            daily_count=20,
            review_ratio=30,
            review_wrong_count=5,
            exam_count=15,
            exam_direction="mixed",
            exam_qtypes=["choice"],
        )
        self.assertEqual(saved["daily_count"], 20)
        self.assertEqual(saved["review_prev_count"], 6)
        self.assertEqual(saved["exam_qtypes_list"], ["choice"])

        # 새 연결에서도 설정이 유지되어야 한다 (VOCA-FR-062)
        conn2 = get_db(self.path)
        try:
            loaded = ssvc.get_settings(conn2)
            self.assertEqual(loaded["daily_count"], 20)
            self.assertEqual(loaded["review_ratio"], 30)
            self.assertEqual(loaded["review_wrong_count"], 5)
            self.assertEqual(loaded["exam_count"], 15)
            self.assertEqual(loaded["exam_direction"], "mixed")
            self.assertEqual(loaded["exam_qtypes_list"], ["choice"])
        finally:
            conn2.close()

    def test_validation_rejects_invalid_values(self):
        with self.assertRaises(ssvc.SettingsError):
            ssvc.save_settings(
                self.conn,
                daily_count=0,
                review_ratio=50,
                review_wrong_count=3,
                exam_count=10,
                exam_direction="en_ko",
                exam_qtypes=["short"],
            )
        with self.assertRaises(ssvc.SettingsError):
            ssvc.save_settings(
                self.conn,
                daily_count=10,
                review_ratio=120,
                review_wrong_count=3,
                exam_count=10,
                exam_direction="en_ko",
                exam_qtypes=["short"],
            )
        with self.assertRaises(ssvc.SettingsError):
            ssvc.save_settings(
                self.conn,
                daily_count=10,
                review_ratio=50,
                review_wrong_count=3,
                exam_count=10,
                exam_direction="en_ko",
                exam_qtypes=[],
            )

    def test_study_assignment_and_review_respect_saved_settings(self):
        for idx in range(1, 26):
            ws.add_word(self.conn, f"word{idx}", f"뜻{idx}")

        ssvc.save_settings(
            self.conn,
            daily_count=6,
            review_ratio=50,  # 직전 일차에서 3개 복습
            review_wrong_count=0,
            exam_count=5,
            exam_direction="ko_en",
            exam_qtypes=["short"],
        )

        day1 = ss.assign_today(self.conn, "2026-11-25")
        self.assertEqual(day1, 1)
        cards1 = ss.build_cards(self.conn, day1)
        self.assertEqual(len(cards1), 6)

        day2 = ss.assign_today(self.conn, "2026-11-26")
        self.assertEqual(day2, 2)
        cards2 = ss.build_cards(self.conn, day2)
        # 2일차 6개 + 1일차 복습 3개 = 9개
        self.assertEqual(len(cards2), 9)

    def test_reset_settings_restores_defaults(self):
        ssvc.save_settings(
            self.conn,
            daily_count=30,
            review_ratio=10,
            review_wrong_count=1,
            exam_count=25,
            exam_direction="ko_en",
            exam_qtypes=["short"],
        )
        restored = ssvc.reset_settings(self.conn)
        self.assertEqual(restored["daily_count"], 10)
        self.assertEqual(restored["review_ratio"], 50)
        self.assertEqual(restored["exam_direction"], "en_ko")


if __name__ == "__main__":
    unittest.main()
