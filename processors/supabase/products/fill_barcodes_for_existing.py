import os
import requests
from dotenv import load_dotenv
from supabase import create_client
import re
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are not set in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_product_id_from_html(product_url):
    """
    Scrape the Auchan product page to extract the productId (external_id) using BeautifulSoup.
    """
    try:
        resp = requests.get(product_url, timeout=5)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        prod_id_container = soup.find('span', class_='vtex-product-identifier-0-x-product-identifier--productId')
        if prod_id_container:
            value_span = prod_id_container.find('span', class_='vtex-product-identifier-0-x-product-identifier__value')
            if value_span:
                return value_span.text.strip()
    except Exception as e:
        print(f"  [!] Error extracting productId from HTML: {e}")
    return None

def get_ean_from_auchan_api(product_id):
    """
    Get EAN from Auchan API using productId.
    """
    try:
        api_url = f"https://www.auchan.ro/api/catalog_system/pub/products/search?fq=productId:{product_id}"
        resp = requests.get(api_url, timeout=5)
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
        print(f"Auchan API error for productId {product_id}: {e}")
        return None

def update_supabase_product(product_id, external_id, barcode, name):
    """
    Update Supabase product by id, setting external_id and barcode only if barcode is missing or empty.
    """
    try:
        update_result = supabase.table('Products').update({
            'external_id': external_id,
            'barcode': barcode
        }).eq('id', product_id).execute()
        if hasattr(update_result, 'error') and update_result.error:
            print(f"  [!] Supabase update error for '{name}': {update_result.error}")
            return False
        return True
    except Exception as e:
        print(f"  [!] Exception updating Supabase for '{name}': {e}")
        return False

def process_supabase_products():
    print("Querying Supabase for products with missing barcodes...")
    # Get all products where barcode is null or empty
    result = supabase.table('Products').select('id, name, supermarket_url, barcode, external_id').or_('barcode.is.null,barcode.eq.""').execute()
    if hasattr(result, 'error') and result.error:
        print(f"Error fetching products: {result.error}")
        return
    products = result.data
    print(f"Found {len(products)} products with missing barcodes.")
    updated = 0
    for product in products:
        name = product.get('name', '').strip()
        url = product.get('supermarket_url', '').strip()
        product_id_db = product.get('id')
        if not name or not url:
            continue
        print(f"Processing: {name}")
        product_id = get_product_id_from_html(url)
        if not product_id:
            print(f"  [!] Could not extract productId from supermarket_url: {url}")
            continue
        ean = get_ean_from_auchan_api(product_id)
        if not ean:
            print(f"  [!] Could not get EAN for productId {product_id}")
            continue
        if update_supabase_product(product_id_db, product_id, ean, name):
            print(f"  [+] Updated '{name}' with external_id={product_id}, barcode={ean}")
            updated += 1
    print(f"\nDone. Total products updated: {updated}")

def main():
    process_supabase_products()

if __name__ == "__main__":
    main() 