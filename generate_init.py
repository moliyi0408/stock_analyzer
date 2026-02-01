import os
import ast

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 子資料夾設定
SUBPACKAGES = {
    'analysis': 'functions',   # 匯入所有函數
    'indicators': 'functions',
    'strategy': 'all'

}

def parse_functions(file_path):
    """解析 Python 檔案，抓出函數名稱"""
    funcs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        node = ast.parse(f.read(), filename=file_path)
    for n in node.body:
        if isinstance(n, ast.FunctionDef):
            funcs.append(n.name)
    return funcs

def generate_init(subpackage, mode):
    folder = os.path.join(BASE_DIR, subpackage)
    init_file = os.path.join(folder, "__init__.py")
    lines = [f"# Auto-generated __init__.py for {subpackage}\n"]

    if not os.path.exists(folder):
        print(f"Warning: folder {folder} not found.")
        return

    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".py") and fname != "__init__.py":
            mod_name = fname[:-3]
            file_path = os.path.join(folder, fname)

            if mode == "functions":
                funcs = parse_functions(file_path)
                if funcs:
                    line = f"from .{mod_name} import {', '.join(funcs)}"
                    lines.append(line)
            elif mode == "all":
                lines.append(f"from .{mod_name} import *")

    # ✅ 每次覆蓋寫入 __init__.py
    with open(init_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{init_file} updated.")

if __name__ == "__main__":
    for subpkg, mode in SUBPACKAGES.items():
        generate_init(subpkg, mode)
