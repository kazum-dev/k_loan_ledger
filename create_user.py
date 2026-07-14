from getpass import getpass
from datetime import datetime

from werkzeug.security import generate_password_hash

from app import app, db, User


def main():
    with app.app_context():
        username = input("ユーザー名: ").strip()

        if not username:
            print("ユーザー名は必須です。")
            return

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user is not None:
            print("そのユーザー名は既に使用されています。")
            return

        password = getpass("パスワード: ")

        if not password:
            print("パスワードは必須です。")
            return

        role = input(
            "権限 (USER / ADMIN) [USER]: "
        ).strip().upper()

        if role == "":
            role = "USER"

        if role not in ("USER", "ADMIN"):
            print("権限は USER または ADMIN を入力してください。")
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

        print("ユーザーを作成しました。")
        print(f"user_id : {user.user_id}")
        print(f"username: {user.username}")
        print(f"role    : {user.role}")


if __name__ == "__main__":
    main()