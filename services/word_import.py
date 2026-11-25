#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 제공 CSV(영단어,뜻) 일괄 가져오기 규칙 (VOCA-FR-003, D-1)
# 파일 위치: services/word_import.py

import csv
import io

from config import now_iso
from services.word_service import normalize_key

# 첫 행이 이 이름이면 헤더로 보고 건너뛴다 (수업 예시의 "단어,뜻" 도 받는다)
HEADER_EN = {"영단어", "단어", "word", "en"}
HEADER_KO = {"뜻", "meaning", "ko"}


def _is_header(row):
    return (
        len(row) >= 2
        and row[0].strip().lower() in HEADER_EN
        and row[1].strip().lower() in HEADER_KO
    )


def import_csv_text(conn, text: str) -> dict:
    """CSV 본문 문자열을 읽어 단어를 등록하고 결과를 돌려준다.

    규칙 (D-1):
    - 같은 영단어(대소문자·앞뒤 공백 무시)는 처음 나온 행만 쓰고 나머지는 건너뛴다.
    - 이미 DB 에 있는 영단어도 건너뛴다.
    - 형식이 틀린 행은 행 번호와 함께 오류 목록에 넣고, 나머지 행은 계속 등록한다.
    반환: {"added": 등록 수, "duplicates": 건너뛴 수, "errors": ["N행: ..."]}
    """
    text = text.lstrip("﻿")  # BOM 이 남아 있으면 제거한다
    reader = csv.reader(io.StringIO(text, newline=""))

    existing = {r[0] for r in conn.execute("SELECT en_key FROM words")}
    seen = set()
    to_insert = []
    result = {"added": 0, "duplicates": 0, "errors": []}
    stamp = now_iso()

    for index, row in enumerate(reader):
        line = reader.line_num
        if index == 0 and _is_header(row):
            continue
        if not any(cell.strip() for cell in row):
            continue  # 빈 줄
        if len(row) < 2 or not row[0].strip() or not row[1].strip():
            result["errors"].append(f"{line}행: 영단어와 뜻이 모두 있어야 합니다.")
            continue

        en = row[0].strip()
        ko = row[1].strip()
        key = normalize_key(en)
        if key in existing or key in seen:
            result["duplicates"] += 1
            continue
        seen.add(key)
        to_insert.append((en, ko, key, stamp))

    if to_insert:
        conn.executemany(
            "INSERT INTO words (en, ko, en_key, created_at) VALUES (?, ?, ?, ?)",
            to_insert,
        )
        conn.commit()
    result["added"] = len(to_insert)
    return result
