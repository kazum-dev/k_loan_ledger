import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))  # project root を import path に追加

from modules.utils import get_project_paths

def main():
    paths = get_project_paths()
    # 期待キー: root, data, loans_csv, repayments_csv（環境で多少違ってOK）
    for k in ["root", "data", "loans_csv", "repayments_csv"]:
        v = paths.get(k)
        print(f"{k}:", v)

if __name__ == "__main__":
    main()
