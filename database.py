import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "loan_ledger.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
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


if __name__ == "__main__":
    init_db()
    print("SQLite DBとテーブルを作成しました。")

conn = get_connection()

cursor = conn.cursor()

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table';
""")

for table in cursor.fetchall():
    print(table[0])

conn.close()