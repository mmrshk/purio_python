import os
import pandas as pd
from processors.barcodes.barcode_processor import BarcodeProcessor
import requests
import ast
import csv

def get_barcode_from_openfoodfacts(product_name):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": product_name,
        "search_simple": 1,
        "action": "process",
        "json": 1
    }
    
    # Configure headers to be more respectful to the API
    headers = {
        'User-Agent': 'FoodFacts-HealthScoring/1.0 (https://github.com/mmrshk/food_facts)',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        products = data.get('products', [])
        if products:
            return products[0].get('code')
    except requests.exceptions.Timeout:
        print(f"Timeout fetching barcode for '{product_name}'")
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching barcode for '{product_name}': {e}")
    except Exception as e:
        print(f"Open Food Facts API error for '{product_name}': {e}")
    return None

def get_ean_from_auchan_api(product_url=None, external_id=None):
    """
    Try to get EAN from Auchan API using external_id (productId) if available, otherwise fallback to slug or HTML scraping.
    """
    try:
        if external_id:
            api_url = f"https://www.auchan.ro/api/catalog_system/pub/products/search?fq=productId:{external_id}"
            resp = requests.get(api_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list):
                items = data[0].get('items', [])
                if items and 'ean' in items[0]:
                    return items[0]['ean']
                if 'productReference' in data[0]:
                    return data[0]['productReference']
        return None
    except Exception as e:
        print(f"Auchan API error for product: {e}")
        return None

def fill_barcodes_in_csv(csv_path, images_base_dir=None):
    df = pd.read_csv(csv_path)
    if 'barcode' not in df.columns:
        df['barcode'] = ''

    processor = BarcodeProcessor()
    barcode_count = 0

    # Try to load product_links.csv if it exists in the same directory
    product_links = {}
    product_links_path = os.path.join(os.path.dirname(csv_path), 'product_links.csv')
    if os.path.isfile(product_links_path):
        with open(product_links_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_links[row['Product Name'].strip()] = row['Product URL'].strip()

    for idx, row in df.iterrows():
        # Parse the string as a list
        try:
            image_paths = ast.literal_eval(row['image_paths'])
        except Exception:
            image_paths = [row['image_paths']]
        barcode_found = None

        external_id = row.get('external_id', None)
        product_name = str(row.get('name', '')).strip()

        print(f"External ID in fill_barcodes_in_csv: {external_id}")

        if pd.notna(external_id) and str(external_id).strip():
            # Convert to string and remove trailing .0 if present
            ext_id_str = str(external_id).strip()
            if ext_id_str.endswith('.0'):
                ext_id_str = ext_id_str[:-2]
            barcode_found = get_ean_from_auchan_api(external_id=ext_id_str)
            if barcode_found:
                print(f"[A] Barcode from Auchan API (external_id) for product '{product_name}': {barcode_found}")
            elif not barcode_found:
                print(f"[A] Barcode NOT FOUND for product '{product_name}' with external_id: {external_id}")

        # Fallback: try Auchan API if barcode not found
        if not barcode_found:
            for image_path in image_paths:
                image_path = image_path.strip().strip('[]\'\"')
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