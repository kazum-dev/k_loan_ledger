import os, csv, importlib
from tempfile import TemporaryDirectory

def test_c45_register_sets_late_base(monkeypatch):
    with TemporaryDirectory() as tmp:
        data_dir = os.path.join(tmp, "data")
        os.makedirs(data_dir, exist_ok=True)
        loans_csv = os.path.join(data_dir, "loan_v3.csv")
        audit_csv = os.path.join(data_dir, "audit_log.csv")

        import loan_module as lm
        # 監査先を差し替え
        monkeypatch.setattr(lm, "AUDIT_PATH", audit_csv, raising=False)

        # get_project_paths を temp ディレクトリに固定（loan_module と modules.utils の両方）
        def fake_paths(_hint=None):
            return {"root": tmp, "modules": os.path.join(tmp,"modules"),
                    "data": data_dir, "loans_csv": loans_csv,
                    "repayments_csv": os.path.join(data_dir,"repayments.csv")}
        import modules.utils as u
        monkeypatch.setattr(u, "get_project_paths", fake_paths, raising=False)
        monkeypatch.setattr(lm, "get_project_paths", fake_paths, raising=False)

        lid = lm.register_loan("CUST001", 12345, "2025-10-06")
        with open(loans_csv, newline="", encoding="utf-8") as f:
            row = list(csv.DictReader(f))[0]
        assert int(row["loan_amount"]) == 12345
        assert int(row["late_base_amount"]) == 12345
