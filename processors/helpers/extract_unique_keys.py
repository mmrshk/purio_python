import os
import pandas as pd
import ast

def collect_keys_from_column(csv_path, column_name):
    keys = set()
    df = pd.read_csv(csv_path)
    if column_name in df.columns:
        for val in df[column_name].dropna():
            try:
                d = ast.literal_eval(val)
                if isinstance(d, dict):
                    keys.update(d.keys())
            except Exception:
                continue
    return keys

def main(root_dir='auchan'):
    all_spec_keys = set()
    all_nutri_keys = set()
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.csv'):
                csv_path = os.path.join(dirpath, filename)
                all_spec_keys.update(collect_keys_from_column(csv_path, 'specifications'))
                all_nutri_keys.update(collect_keys_from_column(csv_path, 'nutritional_info'))
    print("Unique specification keys:")
    print(sorted(all_spec_keys))
    print("\nUnique nutritional_info keys:")
    print(sorted(all_nutri_keys))

if __name__ == "__main__":
    main('auchan')