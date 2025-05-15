import os
import pandas as pd
import ast
import re

def fix_doubled_name(name):
    name = str(name).strip()
    words = name.split()
    n = len(words)
    if n % 2 == 0:
        first_half = ' '.join(words[:n//2])
        second_half = ' '.join(words[n//2:])
        if first_half == second_half:
            return first_half
    # Fallback: check if the name is repeated at the start and end
    half = len(name) // 2
    if name[:half].strip() == name[half:].strip():
        return name[:half].strip()
    return name

def fix_doubled_folder_in_path(path):
    # Split path into parts and fix doubled folder names
    parts = path.split(os.sep)
    fixed_parts = []
    for part in parts:
        fixed_parts.append(fix_doubled_name(part))
    return os.sep.join(fixed_parts)

def fix_doubled_image_paths(image_paths):
    try:
        paths = ast.literal_eval(image_paths)
        # Remove duplicates while preserving order and fix doubled folders
        seen = set()
        deduped = []
        for p in paths:
            fixed_p = fix_doubled_folder_in_path(p)
            if fixed_p not in seen:
                deduped.append(fixed_p)
                seen.add(fixed_p)
        return str(deduped)
    except Exception:
        return image_paths

def fix_csv_names(csv_path):
    df = pd.read_csv(csv_path)
    if 'name' in df.columns:
        df['name'] = df['name'].apply(fix_doubled_name)
    if 'image_paths' in df.columns:
        df['image_paths'] = df['image_paths'].apply(fix_doubled_image_paths)
    df.to_csv(csv_path, index=False)
    print(f"Fixed names and image_paths in {csv_path}")

def fix_image_dirs(images_dir):
    for folder in os.listdir(images_dir):
        folder_path = os.path.join(images_dir, folder)
        if os.path.isdir(folder_path):
            fixed_name = fix_doubled_name(folder)
            if fixed_name != folder:
                new_path = os.path.join(images_dir, fixed_name)
                if not os.path.exists(new_path):
                    os.rename(folder_path, new_path)
                    print(f"Renamed '{folder}' to '{fixed_name}' in {images_dir}")

def process_auchan(auchan_dir='auchan'):
    for root, dirs, files in os.walk(auchan_dir):
        if 'images' in dirs:
            subcategory = os.path.basename(root)
            csv_filename = f"{subcategory}.csv"
            csv_path = os.path.join(root, csv_filename)
            images_dir = os.path.join(root, 'images')
            if os.path.isfile(csv_path):
                fix_csv_names(csv_path)
            if os.path.isdir(images_dir):
                fix_image_dirs(images_dir)

if __name__ == "__main__":
    process_auchan('auchan') 