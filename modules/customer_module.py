import csv


def create_customers_csv():
    with open("customers.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "name", "credit_limit"])


def add_customer(name, credit_limit):
    try:
        with open("customers.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)
            last_id = 0
            for row in reader:
                if row:
                    last_id = int(row[0])
    except FileNotFoundError:
        last_id = 0

    new_id = last_id + 1

    with open("customers.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([new_id, name, credit_limit])

    print(f"顧客{name} を登録しました。(ID:{new_id})")


def list_customers():
    try:
        with open("customers.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            customers = list(reader)

            if not customers or all(not row for row in customers):
                print("登録された顧客がいません。")
            else:
                for row in customers:
                    if row:
                        print(
                            f"ID: {row['customer_id']}, 名前: {row['customer_name']}, 貸付上限額: {int(row['credit_limit']):,}円"
                        )
    except FileNotFoundError:
        print("顧客データが見つかりません。")


def customer_registration_mode():
    print("▼ 顧客登録モード（「終了」と入力）すると終了）")

    while True:
        name = input("顧客の名前を入力してください:")
        if name == "終了":
            print("顧客登録モードを終了します。\n")
            break

        while True:
            try:
                credit_limit = int(input("貸付上限額を入力してください（円）: "))
                if credit_limit <= 0:
                    print("貸付上限額は一円以上で入力してください。")
                else:
                    break
            except ValueError:
                print("有効な数字を入力してください。")
        add_customer(name, credit_limit)

    list_customers()


def search_customer(keyword):
    try:
        with open("customers.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            matches = []

            for row in reader:
                name_match = keyword.lower() in row["customer_name"].lower().strip()
                id_match = keyword.lower().strip() in row["customer_id"].lower().strip()
                if name_match or id_match:
                    matches.append(row)

            if matches:
                print(f"\n【検索結果】キーワード「{keyword}」に一致した顧客:")
                for row in matches:
                    print(
                        f"ID:{row['customer_id']}, 名前:{row['customer_name']}, 上限額:{int(row['credit_limit']):,}円"
                    )
            else:
                print("該当する顧客が見つかりませんでした。")
    except FileNotFoundError:
        print("顧客データが見つかりません。")


def get_all_customer_ids():
    customer_ids = []
    try:
        with open("customers.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)  # ヘッダーを飛ばす
            for row in reader:
                if row:
                    customer_ids.append(
                        row[0].strip()
                    )  # 文字列として扱う（intは使わない）
    except FileNotFoundError:
        print("顧客データが見つかりません。")
    except Exception as e:
        print(f"❌ID取得エラー:{e}")

    return customer_ids


def get_credit_limit(customer_id):
    try:
        with open("customers.csv", mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["customer_id"] == customer_id:
                    return int(row["credit_limit"])
        print(f"⚠顧客ID{customer_id}は見つかりませんでした。")
        return None
    except FileNotFoundError:
        print("❌ 顧客データファイルが見つかりません。")
        return None
    except Exception as e:
        print(f"❌ 上限取得時のエラー:{e}")
        return None
