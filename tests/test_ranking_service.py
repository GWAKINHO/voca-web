#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 공개 순위표 및 비공개 차단 단위 테스트 (VOCA-FR-051~053)
# 파일 위치: tests/test_ranking_service.py

import os
import random
import tempfile
import unittest

from db import get_db, init_db
from services import auth_service as auth
from services import exam_service as es
from services import ranking_service as rk
from services import study_service as ss
from services import word_service as ws


class RankingServiceTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.path)
        self.conn = get_db(self.path)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_only_public_users_appear_in_ranking_and_detail(self):
        for i in range(1, 6):
            ws.add_word(self.conn, f"word{i}", f"뜻{i}")

        pub1 = auth.register(self.conn, "pub_alpha", "pw1111", is_public=True)
        pub2 = auth.register(self.conn, "pub_beta", "pw2222", is_public=True)
        priv = auth.register(self.conn, "priv_gamma", "pw3333", is_public=False)

        # pub1: 3단어 암기, 시험 100%
        d1 = ss.assign_today(self.conn, "2026-11-25", user_id=pub1["id"])
        for c in ss.build_cards(self.conn, d1, user_id=pub1["id"])[:3]:
            ss.record_study(self.conn, c["id"], d1, user_id=pub1["id"])
        aid = es.create_attempt(
            self.conn, 2, "en_ko", ["short"], rng=random.Random(1), user_id=pub1["id"]
        )
        items = es.get_items(self.conn, aid, user_id=pub1["id"])
        es.grade(
            self.conn,
            aid,
            {it["id"]: it["expected"] for it in items},
            user_id=pub1["id"],
        )

        # priv: 5단어 암기했지만 비공개
        dp = ss.assign_today(self.conn, "2026-11-25", user_id=priv["id"])
        for c in ss.build_cards(self.conn, dp, user_id=priv["id"]):
            ss.record_study(self.conn, c["id"], dp, user_id=priv["id"])

        ranking = rk.list_public_ranking(self.conn)
        names = [r["username"] for r in ranking]
        self.assertEqual(names, ["pub_alpha", "pub_beta"])
        self.assertNotIn("priv_gamma", names)
        self.assertEqual(ranking[0]["studied_words"], 3)
        self.assertEqual(ranking[0]["avg_accuracy"], 100)

        # 공개 사용자 상세 조회 가능, 비공개 사용자는 None (VOCA-FR-052)
        pub_detail = rk.get_public_user_stats(self.conn, pub1["id"])
        self.assertIsNotNone(pub_detail)
        self.assertEqual(pub_detail["progress"]["studied_words"], 3)
        self.assertIsNone(rk.get_public_user_stats(self.conn, priv["id"]))
        self.assertIsNone(rk.get_public_user_stats(self.conn, 9999))

    def test_privacy_toggle_updates_visibility(self):
        u = auth.register(self.conn, "toggle_user", "pw1234", is_public=False)
        self.assertIsNone(rk.get_public_user_stats(self.conn, u["id"]))

        auth.set_public(self.conn, u["id"], True)
        self.assertIsNotNone(rk.get_public_user_stats(self.conn, u["id"]))
        self.assertEqual([r["username"] for r in rk.list_public_ranking(self.conn)], ["toggle_user"])

        auth.set_public(self.conn, u["id"], False)
        self.assertIsNone(rk.get_public_user_stats(self.conn, u["id"]))
        self.assertEqual(rk.list_public_ranking(self.conn), [])


if __name__ == "__main__":
    unittest.main()
