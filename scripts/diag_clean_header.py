# sys.path に project root を追加
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from modules.utils import get_project_paths, clean_header_if_quoted

def read_head(p: Path, n=2) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return "".join([next(f) for _ in range(n)])

def main():
    paths = get_project_paths()
    csv_path = Path(paths["loans_csv"])
    print("target:", csv_path)

    print("[before]")
    print(read_head(csv_path, 2))

    result = clean_header_if_quoted(csv_path)
    print("result:", result)

    print("[after]")
    print(read_head(csv_path, 2))

if __name__ == "__main__":
    main()
