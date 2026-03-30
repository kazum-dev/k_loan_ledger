from flask import Flask, render_template
import csv

app = Flask(__name__)

def count_csv_rows(file_path):
    count = 0
    with open(file_path, "r", encoding= "utf-8") as file:
        reader = csv.reader(file)
        next(reader)
        for row in  reader:
            count += 1
    return count

@app.route("/")
def home():
    customer_count = count_csv_rows("data/customers.csv")
    loan_count = count_csv_rows("data/loan_v3.csv")
    repayment_count = count_csv_rows("data/repayments.csv")
    
    return render_template(
        "index.html",
        customer_count=customer_count,
        loan_count=loan_count,
        repayment_count=repayment_count
    )

if __name__ == "__main__":
    app.run(debug=True)