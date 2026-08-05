import os
import sys
from datetime import datetime

from werkzeug.security import generate_password_hash

from app import User, app, db


def create_initial_user() -> None:
    """環境変数が設定されている場合のみ、初期ユーザーを作成する。"""

    username = os.environ.get("INITIAL_USERNAME", "").strip()
    password = os.environ.get("INITIAL_PASSWORD", "")
    role = os.environ.get("INITIAL_ROLE", "ADMIN").strip().upper()

    if not username and not password:
        print("初期ユーザー用の環境変数は設定されていません。")
        return

    if not username or not password:
        print(
            "INITIAL_USERNAMEとINITIAL_PASSWORDは"
            "両方設定してください。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if role not in ("USER", "ADMIN"):
        print(
            "INITIAL_ROLEはUSERまたはADMINを指定してください。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    existing_user = User.query.filter_by(username=username).first()

    if existing_user is not None:
        print(f"初期ユーザーは既に存在します: {username}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    db.session.add(user)
    db.session.commit()

    print(f"初期ユーザーを作成しました: {username}")


def main() -> None:
    with app.app_context():
        db.create_all()
        print("データベースのテーブルを確認・作成しました。")

        create_initial_user()


if __name__ == "__main__":
    main()
