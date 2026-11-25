#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 단어 서비스와 DB 초기화 단위 테스트 (VOCA-FR-001~004, NFR-003)
# 파일 위치: tests/test_word_service.py

import os
import tempfile
import unittest

from db import SCHEMA_VERSION, get_db, init_db
from services import word_service as ws


class WordServiceTest(unittest.TestCase):
    def setUp(self):
        # 테스트마다 빈 임시 DB 를 쓴다. 실제 data/ 는 건드리지 않는다
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "test.db")
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    # VOCA-NFR-003: 빈 DB 에서 테이블이 자동으로 생긴다
    def test_init_creates_tables_and_is_repeatable(self):
        init_db(self.path)  # 두 번 실행해도 오류가 없어야 한다
        names = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {"words", "study_day", "plan", "study_log", "exam_attempt", "exam_item", "user_settings"}
            <= names
        )
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)

    # VOCA-FR-001: 등록
    def test_add_word_and_normalize_key(self):
        word_id = ws.add_word(self.conn, "  Apple ", "사과")
        row = ws.get_word(self.conn, word_id)
        self.assertEqual(row["en"], "Apple")
        self.assertEqual(row["ko"], "사과")

    def test_add_word_rejects_empty(self):
        with self.assertRaises(ws.WordError):
            ws.add_word(self.conn, "  ", "사과")
        with self.assertRaises(ws.WordError):
            ws.add_word(self.conn, "apple", "")

    # D-1: 대소문자와 앞뒤 공백을 무시한 중복 판정
    def test_duplicate_ignores_case_and_spaces(self):
        ws.add_word(self.conn, "Apple", "사과")
        with self.assertRaises(ws.DuplicateWordError):
            ws.add_word(self.conn, " apple ", "능금")

    # VOCA-FR-002: 수정
    def test_update_word_allows_same_key_for_itself(self):
        word_id = ws.add_word(self.conn, "apple", "사과")
        ws.update_word(self.conn, word_id, "APPLE", "능금")
        row = ws.get_word(self.conn, word_id)
        self.assertEqual(row["en"], "APPLE")
        self.assertEqual(row["ko"], "능금")

    def test_update_word_rejects_clash_with_other_word(self):
        ws.add_word(self.conn, "apple", "사과")
        other = ws.add_word(self.conn, "banana", "바나나")
        with self.assertRaises(ws.DuplicateWordError):
            ws.update_word(self.conn, other, "Apple", "바나나")

    # VOCA-FR-002 + D-3: 삭제하면 배정과 암기 기록도 함께 지워진다
    def test_delete_word_removes_plan_and_study_log(self):
        word_id = ws.add_word(self.conn, "apple", "사과")
        self.conn.execute(
            "INSERT INTO study_day (day_no, study_date, created_at) VALUES (1, '2026-11-25', 'x')"
        )
        self.conn.execute(
            "INSERT INTO plan (word_id, day_no) VALUES (?, 1)", (word_id,)
        )
        self.conn.execute(
            "INSERT INTO study_log (word_id, day_no, studied_at) VALUES (?, 1, 'x')",
            (word_id,),
        )
        self.conn.commit()

        ws.delete_word(self.conn, word_id)

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM plan").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM study_log").fetchone()[0], 0)

    # D-3 보완 (데이터 설계서 §6): 시험 문항은 남기고 단어 연결만 끊는다
    def test_delete_word_keeps_exam_item_with_null_word(self):
        word_id = ws.add_word(self.conn, "apple", "사과")
        self.conn.execute(
            "INSERT INTO exam_attempt (created_at, direction, total, correct) "
            "VALUES ('x', 'en_ko', 1, 0)"
        )
        self.conn.execute(
            "INSERT INTO exam_item (attempt_id, seq, word_id, qtype, direction, prompt, expected) "
            "VALUES (1, 1, ?, 'short', 'en_ko', 'apple', '사과')",
            (word_id,),
        )
        self.conn.commit()

        ws.delete_word(self.conn, word_id)

        row = self.conn.execute("SELECT word_id, expected FROM exam_item").fetchone()
        self.assertIsNone(row["word_id"])
        self.assertEqual(row["expected"], "사과")

    def test_get_missing_word_raises(self):
        with self.assertRaises(ws.NotFoundError):
            ws.get_word(self.conn, 999)

    # VOCA-FR-004: 영단어 또는 뜻으로 검색, 대소문자 무시
    def test_search_matches_english_or_korean(self):
        ws.add_word(self.conn, "apple", "사과")
        ws.add_word(self.conn, "banana", "바나나")
        ws.add_word(self.conn, "grape", "포도")

        rows, total = ws.list_words(self.conn, q="APP")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["en"], "apple")

        rows, total = ws.list_words(self.conn, q="바나")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["en"], "banana")

    def test_search_treats_percent_and_underscore_literally(self):
        ws.add_word(self.conn, "apple", "사과")
        _, total = ws.list_words(self.conn, q="%")
        self.assertEqual(total, 0)

    def test_list_pagination(self):
        for i in range(5):
            ws.add_word(self.conn, f"word{i}", f"뜻{i}")
        rows, total = ws.list_words(self.conn, page=2, per_page=2)
        self.assertEqual(total, 5)
        self.assertEqual([r["en"] for r in rows], ["word2", "word3"])


if __name__ == "__main__":
    unittest.main()
