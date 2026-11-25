#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - voca-web - 회원 가입·로그인·비밀번호 해시 검증 서비스 (VOCA-FR-041~043)
# 파일 위치: services/auth_service.py

import re
from werkzeug.security import check_password_hash, generate_password_hash

from config import now_iso

USERNAME_RE = re.compile(r"^[A-Za-z0-9가-힣_-]{2,24}$")
MIN_PASSWORD_LEN = 4
MAX_PASSWORD_LEN = 100


class AuthError(ValueError):
    """회원 가입·로그인 입력 또는 인증 오류."""


class DuplicateUserError(AuthError):
    """이미 존재하는 아이디."""


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def register(conn, username: str, password: str, *, is_public: bool = False) -> dict:
    """새 계정을 생성하고 비밀번호는 해시로만 저장한다 (VOCA-FR-041, 042)."""
    clean_name = (username or "").strip()
    if not USERNAME_RE.match(clean_name):
        raise AuthError("아이디는 2~24자의 영문·숫자·한글·밑줄(_)·하이픈(-)만 사용할 수 있습니다.")
    raw_pw = password or ""
    if len(raw_pw) < MIN_PASSWORD_LEN or len(raw_pw) > MAX_PASSWORD_LEN:
        raise AuthError(f"비밀번호는 {MIN_PASSWORD_LEN}~{MAX_PASSWORD_LEN}자로 입력하세요.")

    key = normalize_username(clean_name)
    if conn.execute("SELECT 1 FROM users WHERE username_key = ?", (key,)).fetchone():
        raise DuplicateUserError(f"이미 사용 중인 아이디입니다: {clean_name}")

    # 평문 저장 금지: PBKDF2-SHA256 솔트 해시 사용 (VOCA-FR-042)
    pw_hash = generate_password_hash(raw_pw, method="pbkdf2:sha256")
    cur = conn.execute(
        "INSERT INTO users (username, username_key, password_hash, is_public, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (clean_name, key, pw_hash, 1 if is_public else 0, now_iso()),
    )
    conn.commit()
    return get_user(conn, cur.lastrowid)


def authenticate(conn, username: str, password: str) -> dict:
    """아이디와 비밀번호를 검증하고 일치하면 사용자 정보를 돌려준다."""
    key = normalize_username(username)
    raw_pw = password or ""
    if not key or not raw_pw:
        raise AuthError("아이디와 비밀번호를 모두 입력하세요.")
    row = conn.execute(
        "SELECT id, username, password_hash, is_public, created_at "
        "FROM users WHERE username_key = ?",
        (key,),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], raw_pw):
        raise AuthError("아이디 또는 비밀번호가 올바르지 않습니다.")
    return {
        "id": row["id"],
        "username": row["username"],
        "is_public": bool(row["is_public"]),
        "created_at": row["created_at"],
    }


def get_user(conn, user_id: int):
    """user_id 로 사용자 정보를 조회한다. 없으면 None."""
    if not user_id or user_id <= 0:
        return None
    row = conn.execute(
        "SELECT id, username, is_public, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "is_public": bool(row["is_public"]),
        "created_at": row["created_at"],
    }


def set_public(conn, user_id: int, is_public: bool) -> bool:
    """사용자의 학습 통계 공개 여부를 변경한다 (VOCA-FR-052)."""
    if not user_id or user_id <= 0:
        raise AuthError("로그인한 사용자만 공개 설정을 변경할 수 있습니다.")
    conn.execute(
        "UPDATE users SET is_public = ? WHERE id = ?",
        (1 if is_public else 0, user_id),
    )
    conn.commit()
    return bool(is_public)
