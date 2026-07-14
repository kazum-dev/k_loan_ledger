# database.py
import getpass
import sqlite3
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "loan_ledger.db"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_column_names(conn, table_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


def init_db():
    """
    DBファイルと各テーブルを作成する。

    CREATE TABLE IF NOT EXISTSでは、
    既存テーブルへのカラム追加は行われない。
    既存usersテーブルの更新はmigrate_users_tableで行う。
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'USER',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        credit_limit INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        loan_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        customer_id TEXT NOT NULL,
        loan_amount INTEGER NOT NULL,
        loan_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        interest_rate_percent REAL NOT NULL,
        repayment_expected INTEGER NOT NULL,
        repayment_method TEXT NOT NULL,
        grace_period_days INTEGER NOT NULL,
        late_fee_rate_percent REAL NOT NULL,
        late_base_amount INTEGER NOT NULL,
        contract_status TEXT NOT NULL,
        cancelled_at TEXT,
        cancel_reason TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repayments (
        repayment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        loan_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        repayment_amount INTEGER NOT NULL,
        repayment_date TEXT NOT NULL,
        payment_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (loan_id) REFERENCES loans(loan_id),
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    )
    """)

    conn.commit()
    conn.close()


def migrate_users_table():
    """
    既存usersテーブルへF-6認証用カラムを追加する。

    追加対象:
    - password_hash
    - role
    - is_active
    - updated_at
    """
    conn = get_connection()

    try:
        columns = get_column_names(conn, "users")

        if "password_hash" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''
            """)
            print("password_hashカラムを追加しました。")

        if "role" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN role TEXT NOT NULL DEFAULT 'USER'
            """)
            print("roleカラムを追加しました。")

        if "is_active" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
            """)
            print("is_activeカラムを追加しました。")

        if "updated_at" not in columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''
            """)
            print("updated_atカラムを追加しました。")

        conn.commit()

        user = conn.execute("""
            SELECT
                user_id,
                username,
                password_hash
            FROM users
            WHERE user_id = 1
        """).fetchone()

        if user is None:
            initial_password = getpass.getpass(
                "初期管理者パスワードを入力してください: "
            )

            conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    password_hash,
                    role,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                1,
                "admin",
                generate_password_hash(initial_password),
                "ADMIN",
                1,
                now_str(),
                now_str(),
            ))

            print("user_id=1の管理者ユーザーを作成しました。")

        elif not user[2]:
            initial_password = getpass.getpass(
                "初期管理者パスワードを入力してください: "
            )

            conn.execute("""
                UPDATE users
                SET
                    username = ?,
                    password_hash = ?,
                    role = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                "admin",
                generate_password_hash(initial_password),
                "ADMIN",
                1,
                now_str(),
                1,
            ))

            print("user_id=1へ管理者認証情報を設定しました。")

        else:
            conn.execute("""
                UPDATE users
                SET
                    username = ?,
                    role = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                "admin",
                "ADMIN",
                1,
                now_str(),
                1,
            ))

            print(
                "認証情報は設定済みです。"
                "パスワードハッシュは変更していません。"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    migrate_users_table()

    print("SQLite DBとテーブルの更新が完了しました。")