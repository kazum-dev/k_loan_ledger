import csv #CSVファイルを操作するためのライブラリを読み込む

#顧客管理用の関数
def create_customers_csv():
    with open('customers.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['id', 'name', 'credit_limit']) #ヘッダー行を書き込む

#顧客情報を追加する関数
def add_customer(name, credit_limit):

#CSVを読み込んで、登録されている最後のIDを取得
    try:
        with open('customers.csv', mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) #ヘッダーを飛ばす
            last_id = 0
            for row in reader:
                if row: #空行防止
                    last_id = int(row[0]) #最後に出てきたIDを覚えておく
    except FileNotFoundError:
        last_id = 0 #ファイルがない場合はIDを0にする

    new_id = last_id + 1 #新しい顧客には「最後のID+1」の番号を割り振る

#新しい顧客情報をCSVファイルに追記
    with open('customers.csv', mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([new_id, name, credit_limit]) #新しい行を書き込む

    print(f"顧客{name} を登録しました。(ID:{new_id}) ") #登録完了メッセージを表示

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

#顧客一覧表示機能
def list_customers():
    try:
        with open('customers.csv',mode='r',newline='',encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) #ヘッダーをスキップ 

            customers = list(reader) #ここで一旦すべて読み込んでリストにする

            if not customers or all(not row for row in customers): #顧客がいないか全行空っぽなら
                print("登録された顧客がいません。")
            else:    
                for row in customers:
                    if row: #空行防止
                        id, name, credit_limit = row
                        print(f"ID: {id},名前:{name},貸付上限額:{int(credit_limit):,}円")

    except FileNotFoundError:
        print("顧客データが見つかりません。")

#実行部分
customer_registration_mode()
