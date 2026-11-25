#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - CSV 일괄 가져오기 단위 테스트 (VOCA-FR-003, D-1)
# 파일 위치: tests/test_word_import.py

import os
import tempfile
import unittest

from db import get_db, init_db
from services import word_import as wi
from services import word_service as ws


class WordImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "test.db")
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    # FR-003: 헤더(영단어,뜻 / 단어,뜻 / word,meaning)는 건너뛴다
    def test_skips_header_variants(self):
        for header in ("영단어,뜻", "단어,뜻", "word,meaning"):
            with self.subTest(header=header):
                self.conn.execute("DELETE FROM words")
                self.conn.commit()
                res = wi.import_csv_text(self.conn, f"{header}\napple,사과\nbanana,바나나\n")
                self.assertEqual(res["added"], 2)
                self.assertEqual(res["duplicates"], 0)
                self.assertEqual(res["errors"], [])

    # FR-003: UTF-8 BOM 이 남아 있어도 제거하고 헤더·첫 행을 정상 처리한다
    def test_strips_bom_with_and_without_header(self):
        res1 = wi.import_csv_text(self.conn, "\ufeff단어,뜻\napple,사과\n")
        self.assertEqual(res1["added"], 1)
        self.assertEqual(res1["errors"], [])

        res2 = wi.import_csv_text(self.conn, "\ufeffbanana,바나나\n")
        self.assertEqual(res2["added"], 1)
        rows, total = ws.list_words(self.conn)
        self.assertEqual(total, 2)
        self.assertEqual([r["en"] for r in rows], ["apple", "banana"])

    # D-1: 같은 영단어(대소문자·앞뒤 공백 무시)는 처음 행만 등록하고 나머지는 건너뛴다
    def test_duplicates_keep_first_row_only(self):
        csv_text = "영단어,뜻\nApple,사과\n  apple ,능금\nAPPLE,사과2\nbanana,바나나\n"
        res = wi.import_csv_text(self.conn, csv_text)
        self.assertEqual(res["added"], 2)
        self.assertEqual(res["duplicates"], 2)
        self.assertEqual(res["errors"], [])

        rows, _ = ws.list_words(self.conn, q="apple")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["en"], "Apple")
        self.assertEqual(rows[0]["ko"], "사과")

    # D-1: DB 에 이미 있는 영단어는 건너뛰고 기존 뜻을 유지한다
    def test_skips_existing_words_in_db(self):
        ws.add_word(self.conn, "Apple", "기존 사과")
        res = wi.import_csv_text(self.conn, "단어,뜻\n apple ,새 사과\norange,오렌지\n")
        self.assertEqual(res["added"], 1)
        self.assertEqual(res["duplicates"], 1)
        self.assertEqual(res["errors"], [])

        rows, _ = ws.list_words(self.conn, q="apple")
        self.assertEqual(rows[0]["ko"], "기존 사과")

    # 형식 오류 행은 행 번호와 함께 보고하고, 빈 줄은 무시하며 정상 행은 계속 등록한다
    def test_reports_format_error_line_numbers_and_continues(self):
        csv_text = (
            "단어,뜻\n"
            "apple,사과\n"
            "\n"
            "only_one_col\n"
            "  ,뜻만 있음\n"
            "empty_ko,   \n"
            "grape,\"포도, 포도알\"\n"
        )
        res = wi.import_csv_text(self.conn, csv_text)
        self.assertEqual(res["added"], 2)
        self.assertEqual(res["duplicates"], 0)
        self.assertEqual(len(res["errors"]), 3)
        self.assertTrue(res["errors"][0].startswith("4행:"))
        self.assertTrue(res["errors"][1].startswith("5행:"))
        self.assertTrue(res["errors"][2].startswith("6행:"))


if __name__ == "__main__":
    unittest.main()
