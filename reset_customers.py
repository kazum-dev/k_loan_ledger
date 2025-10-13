import csv


def reset_customers_csv():
    with open("customers.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([id, "name", "credit_limit"])
    print("customers.csvをリセットしました！")


reset_customers_csv()
