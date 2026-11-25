#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 시험 출제 가중치, 보기 생성, 채점 단위 테스트 (VOCA-FR-021~026)
# 파일 위치: tests/test_exam_service.py

import os
import random
import tempfile
import unittest
from datetime import datetime, timedelta

from config import KST
from db import get_db, init_db
from services import exam_service as es
from services import word_service as ws


def _add_words(conn, pairs):
    return [ws.add_word(conn, en, ko) for en, ko in pairs]


class ExamServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "test.db")
        init_db(self.path)
        self.conn = get_db(self.path)
        self.now = datetime(2026, 11, 25, 16, 0, 0, tzinfo=KST)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    # FR-022, D-6: 기본 1 + 미시험 +3 / 7일 경과 +2 / 오답률 50% 이상 +2
    def test_word_weights_follow_d6_rules(self):
        w1, w2, w3, w4 = _add_words(
            self.conn,
            [("w1", "뜻1"), ("w2", "뜻2"), ("w3", "뜻3"), ("w4", "뜻4")],
        )
        # w1: 기록 없음 -> 1 + 3 = 4
        # w2: 최근(1일 전) 정답 1/1 -> 1
        # w3: 7일 전 정답 1/1 -> 1 + 2 = 3
        # w4: 8일 전 오답 1, 정답 1 (오답률 50%) -> 1 + 2 + 2 = 5
        recent = (self.now - timedelta(days=1)).isoformat(timespec="seconds")
        seven_days = (self.now - timedelta(days=7)).isoformat(timespec="seconds")
        eight_days = (self.now - timedelta(days=8)).isoformat(timespec="seconds")

        cur = self.conn.execute(
            "INSERT INTO exam_attempt (created_at, submitted_at, direction, total, correct) "
            "VALUES (?, ?, 'en_ko', 4, 3)",
            (recent, recent),
        )
        aid = cur.lastrowid
        self.conn.executemany(
            "INSERT INTO exam_item (attempt_id, seq, word_id, qtype, direction, prompt, expected, is_correct, answered_at) "
            "VALUES (?, ?, ?, 'short', 'en_ko', 'p', 'e', ?, ?)",
            [
                (aid, 1, w2, 1, recent),
                (aid, 2, w3, 1, seven_days),
                (aid, 3, w4, 0, eight_days),
                (aid, 4, w4, 1, eight_days),
            ],
        )
        self.conn.commit()

        weights = es.word_weights(self.conn, now=self.now)
        self.assertEqual(weights[w1], 4)
        self.assertEqual(weights[w2], 1)
        self.assertEqual(weights[w3], 3)
        self.assertEqual(weights[w4], 5)

    # FR-021: 단어 부족 시 가능한 수만큼 중복 없이 출제, 입력 범위 검증
    def test_create_attempt_shortage_and_validation(self):
        with self.assertRaises(es.ExamError):
            es.create_attempt(self.conn, 5, "en_ko", ["short"])  # 단어 0개

        _add_words(self.conn, [("apple", "사과"), ("banana", "바나나")])
        with self.assertRaises(es.ExamError):
            es.create_attempt(self.conn, 0, "en_ko", ["short"])
        with self.assertRaises(es.ExamError):
            es.create_attempt(self.conn, 51, "en_ko", ["short"])
        with self.assertRaises(es.ExamError):
            es.create_attempt(self.conn, 2, "invalid", ["short"])
        with self.assertRaises(es.ExamError):
            es.create_attempt(self.conn, 2, "en_ko", [])

        aid = es.create_attempt(self.conn, 10, "en_ko", ["short"], now=self.now, rng=random.Random(1))
        attempt = es.get_attempt(self.conn, aid)
        items = es.get_items(self.conn, aid)
        self.assertEqual(attempt["total"], 2)
        self.assertIsNone(attempt["submitted_at"])
        self.assertEqual(len({it["word_id"] for it in items}), 2)

    # FR-024: 4지선다 보기 부족(다른 단어 뜻 3개 미만)이면 단답형으로 전환
    def test_choice_falls_back_to_short_when_fewer_than_three_distractors(self):
        _add_words(self.conn, [("a", "뜻A"), ("b", "뜻B"), ("c", "뜻C")])  # 다른 뜻 2개뿐
        aid = es.create_attempt(self.conn, 3, "en_ko", ["choice"], now=self.now, rng=random.Random(2))
        items = es.get_items(self.conn, aid)
        self.assertTrue(all(it["qtype"] == "short" for it in items))
        self.assertTrue(all(it["choices"] is None for it in items))

    # FR-024: 단어가 4개 이상이면 4지선다 보기 4개(정답 포함, 중복 없음) 생성
    def test_choice_creates_four_distinct_options_including_expected(self):
        _add_words(
            self.conn,
            [("apple", "사과"), ("banana", "바나나"), ("grape", "포도"), ("pear", "배")],
        )
        aid = es.create_attempt(self.conn, 4, "en_ko", ["choice"], now=self.now, rng=random.Random(3))
        items = es.get_items(self.conn, aid)
        for it in items:
            self.assertEqual(it["qtype"], "choice")
            self.assertEqual(len(it["choices_list"]), 4)
            self.assertEqual(len(set(it["choices_list"])), 4)
            self.assertIn(it["expected"], it["choices_list"])

    # FR-023: mixed 방향은 문항마다 en_ko / ko_en 으로 풀어서 저장
    def test_mixed_direction_resolves_per_item(self):
        _add_words(self.conn, [(f"w{i}", f"뜻{i}") for i in range(10)])
        aid = es.create_attempt(self.conn, 10, "mixed", ["short", "choice"], now=self.now, rng=random.Random(42))
        items = es.get_items(self.conn, aid)
        self.assertTrue(all(it["direction"] in ("en_ko", "ko_en") for it in items))
        self.assertEqual({it["direction"] for it in items}, {"en_ko", "ko_en"})
        self.assertEqual({it["qtype"] for it in items}, {"short", "choice"})

    # FR-025, FR-026, D-10: 단답형(쉼표 복수 뜻·대소문자·공백 무시) & 4지선다 채점 + 재채점 방지
    def test_grade_short_and_choice_and_no_regrade(self):
        _add_words(
            self.conn,
            [
                ("Apple", "사과, 능금"),
                ("banana", "바나나"),
                ("grape", "포도"),
                ("pear", "배"),
            ],
        )
        aid = es.create_attempt(self.conn, 4, "en_ko", ["short"], now=self.now, rng=random.Random(7))
        items = es.get_items(self.conn, aid)
        answers = {}
        for it in items:
            if it["prompt"] == "Apple":
                answers[it["id"]] = "  능금 "  # 복수 뜻 중 하나 일치 -> 정답
            elif it["prompt"] == "banana":
                answers[it["id"]] = "바나나"
            else:
                answers[it["id"]] = "틀린답"

        done = es.grade(self.conn, aid, answers, now=self.now)
        self.assertEqual(done["correct"], 2)
        self.assertIsNotNone(done["submitted_at"])

        # 이미 제출된 시험은 다른 답으로 다시 호출해도 재채점하지 않는다
        all_right = {it["id"]: it["expected"].split(",")[0] for it in items}
        again = es.grade(self.conn, aid, all_right, now=self.now)
        self.assertEqual(again["correct"], 2)

    # ko_en 단답형은 대소문자·공백 무시로 영단어 채점
    def test_grade_ko_en_short_ignores_case_and_spaces(self):
        _add_words(self.conn, [("Apple", "사과")])
        aid = es.create_attempt(self.conn, 1, "ko_en", ["short"], now=self.now, rng=random.Random(1))
        item = es.get_items(self.conn, aid)[0]
        res = es.grade(self.conn, aid, {item["id"]: "  aPpLe "}, now=self.now)
        self.assertEqual(res["correct"], 1)

    # 4지선다 채점은 선택한 보기가 expected 와 정확히 같아야 정답
    def test_grade_choice_exact_match(self):
        _add_words(
            self.conn,
            [("apple", "사과, 능금"), ("banana", "바나나"), ("grape", "포도"), ("pear", "배")],
        )
        aid = es.create_attempt(self.conn, 4, "en_ko", ["choice"], now=self.now, rng=random.Random(5))
        items = es.get_items(self.conn, aid)
        answers = {it["id"]: it["expected"] for it in items}
        res = es.grade(self.conn, aid, answers, now=self.now)
        self.assertEqual(res["correct"], 4)


if __name__ == "__main__":
    unittest.main()
