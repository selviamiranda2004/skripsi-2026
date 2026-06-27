"""
Database connection and utilities for Media Monitoring Dashboard
"""

import os
from dotenv import load_dotenv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# =========================
# LOAD .ENV (FIXED)
# =========================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL tidak ditemukan. Cek file .env kamu!")

print("✅ DATABASE CONNECTED TO:", DATABASE_URL.split("@")[1] if DATABASE_URL else None)


# =========================
# CONNECTION
# =========================
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("DB ERROR:", e)
        raise
    finally:
        conn.close()


@contextmanager
def get_db_cursor(connection=None):
    if connection is None:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
            finally:
                cursor.close()
    else:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()


# =========================
# USER QUERIES
# =========================

def get_user_by_username(username: str):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, username, email, password_hash, role, is_active FROM users WHERE username = %s",
            (username,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_user_by_id(user_id: int):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, username, email, full_name, role, is_active FROM users WHERE id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_all_users():
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, username, email, full_name, role, is_active FROM users WHERE is_active = TRUE ORDER BY id DESC"
        )
        results = cursor.fetchall()
        return [dict(row) for row in results] if results else []


def create_user(username: str, email: str, password_hash: str, full_name: str = None, role: str = "user"):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, full_name, role, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    RETURNING id, username, email, role
                    """,
                    (username, email, password_hash, full_name, role)
                )
                result = cursor.fetchone()
                return dict(result) if result else None

            except psycopg2.IntegrityError as e:
                if "username" in str(e):
                    raise ValueError("Username sudah digunakan")
                if "email" in str(e):
                    raise ValueError("Email sudah digunakan")
                raise
def update_user(user_id, data):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute("""
                UPDATE users
                SET username = %s,
                    email = %s,
                    role = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, username, email, role
            """, (
                data["username"],
                data["email"],
                data["role"],
                user_id
            ))

            result = cursor.fetchone()
            return dict(result) if result else None

def delete_user(user_id: int):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                "UPDATE users SET is_active = FALSE WHERE id = %s RETURNING id",
                (user_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None


def update_user_password(user_id: int, password_hash: str):
    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s RETURNING id",
                (password_hash, user_id)
            )
            result = cursor.fetchone()
            return dict(result) if result else None