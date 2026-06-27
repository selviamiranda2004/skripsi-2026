"""
Seed / reset admin user.

Pakai bcrypt yang SAMA dengan backend (Python `bcrypt` package),
jadi dijamin kompatibel dengan `bcrypt.checkpw` di endpoint /auth/login.

USAGE:
  python seed_admin.py                       # bikin/reset admin dengan password default 'admin123'
  python seed_admin.py mypassword            # custom password
  python seed_admin.py mypassword myadmin    # custom password + username
"""

import sys
import bcrypt
from database import get_db_connection, get_db_cursor


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def upsert_admin(username: str, password: str, email: str = None) -> None:
    if email is None:
        email = f"{username}@example.com"
    pw_hash = hash_password(password)

    with get_db_connection() as conn:
        with get_db_cursor(conn) as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()

            if row:
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s,
                        role          = 'admin',
                        is_active     = TRUE,
                        updated_at    = NOW()
                    WHERE username = %s
                    """,
                    (pw_hash, username),
                )
                print(f">> Admin '{username}' di-reset (id={row['id']}).")
            else:
                cursor.execute(
                    """
                    INSERT INTO users
                        (username, email, password_hash, full_name, role, is_active)
                    VALUES
                        (%s, %s, %s, %s, 'admin', TRUE)
                    RETURNING id
                    """,
                    (username, email, pw_hash, "Administrator"),
                )
                new_id = cursor.fetchone()["id"]
                print(f">> Admin '{username}' dibuat (id={new_id}).")


def main():
    args = sys.argv[1:]
    password = args[0] if len(args) >= 1 else "admin123"
    username = args[1] if len(args) >= 2 else "admin"

    print("=" * 50)
    print(" SEED / RESET ADMIN USER")
    print("=" * 50)
    print(f"Username : {username}")
    print(f"Password : {password}")

    upsert_admin(username, password)

    print("\nSelesai. Login pakai kredensial di atas via /login.")


if __name__ == "__main__":
    main()
