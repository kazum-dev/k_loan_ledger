import csv

def list_customers():
    try:
        with open('customers.csv',mode='r',newline='',encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) #ヘッダーをスキップ 

            customers = list(reader) #ここで一旦すべて読み込んでリストにする

            if not customers or all(not row for row in customers): #顧客がいないか全行空っぽなら
                print("登録された顧客がいません。")
            else:    
                for row in reader:
                    if row: #空行防止
                        id, name, credit_limit = row
                        print(f"ID: {id},名前:{name},貸付上限額:{int(credit_limit):,}円")

    except FileNotFoundError:
        print("顧客データが見つかりません。")

list_customers()