import os
import pandas as pd
from processors.barcodes.barcode_processor import BarcodeProcessor
import requests
import ast

def get_barcode_from_openfoodfacts(product_name):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": product_name,
        "search_simple": 1,
        "action": "process",
        "json": 1
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        products = data.get('products', [])
        if products:
            return products[0].get('code')
    except Exception as e:
        print(f"Open Food Facts API error for '{product_name}': {e}")
    return None

def fill_barcodes_in_csv(csv_path, images_base_dir):
    df = pd.read_csv(csv_path)
    if 'barcode' not in df.columns:
        df['barcode'] = ''
    processor = BarcodeProcessor()
    barcode_count = 0
    for idx, row in df.iterrows():
        # Parse the string as a list
        try:
            image_paths = ast.literal_eval(row['image_paths'])
        except Exception:
            image_paths = [row['image_paths']]
        barcode_found = None
        for image_path in image_paths:
            image_path = image_path.strip().strip('[]\'"')
            # Use the path as-is, do NOT join with images_base_dir
            full_image_path = image_path
            print(f"Trying to load image: {full_image_path}")
            if not os.path.isfile(full_image_path):
                print(f"File does not exist: {full_image_path}")
                continue
            barcodes, _ = processor.process_image(full_image_path)
            if barcodes:
                barcode_found = barcodes[0]['data']
                break
        if barcode_found:
            barcode_count += 1
            print(f"[{barcode_count}] Barcode added for product '{row.get('name', '')}': {barcode_found}")
        df.at[idx, 'barcode'] = barcode_found if barcode_found else ''
    # Save to new file with _processed
    base, ext = os.path.splitext(csv_path)
    new_csv_path = f"{base}_processed{ext}"
    df.to_csv(new_csv_path, index=False)
    print(f"Saved processed CSV with barcodes: {new_csv_path}")
    print(f"Total barcodes found and added: {barcode_count} / {len(df)}")

def process_auchan_directory(auchan_dir='auchan'):
    for root, dirs, files in os.walk(auchan_dir):
        if 'images' in dirs:
            subcategory = os.path.basename(root)
            csv_filename = f"{subcategory}.csv"
            csv_path = os.path.join(root, csv_filename)
            images_dir = os.path.join(root, 'images')
            if os.path.isfile(csv_path):
                print(f"Processing {csv_path} with images in {images_dir}")
                fill_barcodes_in_csv(csv_path, images_dir)

if __name__ == "__main__":
    process_auchan_directory('auchan')

    # fill_barcodes_in_csv(
    #     'auchan/dulciuri/halva-nuga-rahat-si-turta-dulce/halva-nuga-rahat-si-turta-dulce.csv',
    #     'auchan/dulciuri/halva-nuga-rahat-si-turta-dulce/images'
    # )