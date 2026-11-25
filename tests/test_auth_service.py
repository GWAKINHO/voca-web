#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 회원 가입·로그인·계정별 이력 분리·마이그레이션 단위 테스트 (VOCA-FR-041~043)
# 파일 위치: tests/test_auth_service.py

import os
import random
import sqlite3
import tempfile
import unittest

from db import SCHEMA_VERSION, get_db, init_db
from services import auth_service as auth
from services import exam_service as es
from services import settings_service as ssvc
from services import stats_service as st
from services import study_service as ss
from services import word_service as ws


class AuthServiceTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_register_hashes_password_and_authenticates(self):
        user = auth.register(self.conn, "Alice", "secret1234")
        self.assertEqual(user["username"], "Alice")
        self.assertFalse(user["is_public"])

        # VOCA-FR-042: DB 에는 평문이 아닌 해시가 저장되어야 한다
        row = self.conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        self.assertNotEqual(row["password_hash"], "secret1234")
        self.assertNotIn("secret1234", row["password_hash"])
        self.assertTrue(row["password_hash"].startswith("pbkdf2:sha256:"))

        ok = auth.authenticate(self.conn, "alice", "secret1234")
        self.assertEqual(ok["id"], user["id"])

        with self.assertRaises(auth.AuthError):
            auth.authenticate(self.conn, "Alice", "wrongpw")

    def test_register_validation_and_duplicate_check(self):
        auth.register(self.conn, "student01", "pass1234")
        with self.assertRaises(auth.DuplicateUserError):
            auth.register(self.conn, "STUDENT01", "other1234")
        with self.assertRaises(auth.AuthError):
            auth.register(self.conn, "a", "pass1234")
        with self.assertRaises(auth.AuthError):
            auth.register(self.conn, "bad name!", "pass1234")
        with self.assertRaises(auth.AuthError):
            auth.register(self.conn, "valid_user", "123")

    def test_per_user_isolation_for_study_exam_stats_and_settings(self):
        for i in range(1, 11):
            ws.add_word(self.conn, f"word{i}", f"뜻{i}")

        u1 = auth.register(self.conn, "user_one", "pw1111")["id"]
        u2 = auth.register(self.conn, "user_two", "pw2222")["id"]

        # 설정 분리 (VOCA-FR-062)
        ssvc.save_settings(
            self.conn,
            daily_count=3,
            review_ratio=50,
            review_wrong_count=1,
            exam_count=4,
            exam_direction="ko_en",
            exam_qtypes=["short"],
            user_id=u1,
        )
        self.assertEqual(ssvc.get_settings(self.conn, user_id=u1)["daily_count"], 3)
        self.assertEqual(ssvc.get_settings(self.conn, user_id=u2)["daily_count"], 10)

        # 암기 일차·기록 분리 (VOCA-FR-043)
        d1 = ss.assign_today(self.conn, "2026-11-25", user_id=u1)
        cards_u1 = ss.build_cards(self.conn, d1, user_id=u1)
        self.assertEqual(len(cards_u1), 3)
        ss.record_study(self.conn, cards_u1[0]["id"], d1, user_id=u1)

        d2 = ss.assign_today(self.conn, "2026-11-25", user_id=u2)
        cards_u2 = ss.build_cards(self.conn, d2, user_id=u2)
        self.assertEqual(len(cards_u2), 10)

        self.assertEqual(st.get_progress(self.conn, user_id=u1)["studied_words"], 1)
        self.assertEqual(st.get_progress(self.conn, user_id=u2)["studied_words"], 0)

        # 시험 이력 및 소유권 분리 (VOCA-FR-043)
        aid = es.create_attempt(
            self.conn, 2, "en_ko", ["short"], rng=random.Random(1), user_id=u1
        )
        with self.assertRaises(es.NotFoundError):
            es.get_attempt(self.conn, aid, user_id=u2)

        items = es.get_items(self.conn, aid, user_id=u1)
        es.grade(self.conn, aid, {items[0]["id"]: items[0]["expected"]}, user_id=u1)
        self.assertEqual(len(st.get_exam_trend(self.conn, user_id=u1)), 1)
        self.assertEqual(len(st.get_exam_trend(self.conn, user_id=u2)), 0)
        self.assertEqual(len(st.get_top_wrong_words(self.conn, user_id=u1)), 1)
        self.assertEqual(len(st.get_top_wrong_words(self.conn, user_id=u2)), 0)

    def test_v1_database_auto_migrates_to_v3_preserving_rows(self):
        fd, legacy_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            raw = sqlite3.connect(legacy_path)
            raw.executescript(
                """
                CREATE TABLE words (id INTEGER PRIMARY KEY AUTOINCREMENT, en TEXT NOT NULL, ko TEXT NOT NULL, en_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
                CREATE TABLE study_day (day_no INTEGER PRIMARY KEY, study_date TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
                CREATE TABLE plan (word_id INTEGER PRIMARY KEY, day_no INTEGER NOT NULL);
                CREATE TABLE study_log (id INTEGER PRIMARY KEY AUTOINCREMENT, word_id INTEGER NOT NULL, day_no INTEGER NOT NULL, studied_at TEXT NOT NULL);
                CREATE TABLE exam_attempt (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, submitted_at TEXT, direction TEXT NOT NULL, total INTEGER NOT NULL, correct INTEGER);
                CREATE TABLE exam_item (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, seq INTEGER NOT NULL, word_id INTEGER, qtype TEXT NOT NULL, direction TEXT NOT NULL, prompt TEXT NOT NULL, expected TEXT NOT NULL, choices TEXT, answer_given TEXT, is_correct INTEGER, answered_at TEXT);
                INSERT INTO words (id, en, ko, en_key, created_at) VALUES (1, 'apple', '사과', 'apple', '2026-11-25T10:00:00+09:00');
                INSERT INTO study_day (day_no, study_date, created_at) VALUES (1, '2026-11-25', '2026-11-25T10:00:00+09:00');
                INSERT INTO plan (word_id, day_no) VALUES (1, 1);
                INSERT INTO study_log (word_id, day_no, studied_at) VALUES (1, 1, '2026-11-25T10:01:00+09:00');
                PRAGMA user_version = 1;
                """
            )
            raw.commit()
            raw.close()

            init_db(legacy_path)
            migrated = get_db(legacy_path)
            try:
                self.assertEqual(
                    migrated.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION
                )
                self.assertEqual(st.get_progress(migrated, user_id=0)["studied_words"], 1)
                new_u = auth.register(migrated, "fresh_user", "pw9999")["id"]
                self.assertEqual(st.get_progress(migrated, user_id=new_u)["studied_words"], 0)
            finally:
                migrated.close()
        finally:
            if os.path.exists(legacy_path):
                os.remove(legacy_path)


if __name__ == "__main__":
    unittest.main()
