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

def load_loans(file_path):
    loans = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            loans.append(row)
    return loans    

def load_repayments(file_path):
    repayments = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            repayments.append(row)
    return repayments

def load_customers(file_path):
    customers = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            customers.append(row)
    return customers

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

@app.route("/loans")
def loan_list():
    loans = load_loans("data/loan_v3.csv")
    return render_template("loan_list.html", loans=loans)

@app.route("/repayments")
def repayment_list():
    repayments = load_repayments("data/repayments.csv")
    return render_template("repayment_list.html", repayments=repayments)

@app.route("/customers")
def customer_list():
    customers = load_customers("data/customers.csv")
    return render_template("customer_list.html", customers=customers)

if __name__ == "__main__":
    app.run(debug=True)