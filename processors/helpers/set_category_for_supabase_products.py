import os
from dotenv import load_dotenv
from supabase import create_client
import time
import pandas as pd
from pathlib import Path

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
supabase = create_client(supabase_url, supabase_key)

def determine_category(product):
    """
    Determine the category path for a product.
    This logic can be customized. For now, try to use the existing 'category' field or fallback to 'specifications.product_type'.
    """
    # If already has a category, return it
    if product.get('category'):
        return product['category']
    # Try to build from specifications
    specs = product.get('specifications')
    if isinstance(specs, dict):
        # Example: use product_type or other keys to build a path
        product_type = specs.get('product_type')
        if product_type:
            return product_type
    # Fallback: return None
    return None

# --- NEW: Build product name to category path mapping from processed CSVs ---
def build_name_to_category_mapping(auchan_dir="auchan"):
    """
    Recursively find all *_processed.csv files in auchan_dir and build a mapping:
    product name -> category path (e.g., carne/carne-de-vita-si-manzat)
    """
    mapping = {}
    auchan_path = Path(auchan_dir)
    for csv_path in auchan_path.rglob("*_processed.csv"):
        # Get category path relative to auchan/
        category_path = str(csv_path.parent.relative_to(auchan_path))
        try:
            df = pd.read_csv(csv_path)
            if 'name' in df.columns:
                for name in df['name'].dropna():
                    mapping[str(name).strip()] = category_path
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")
    print(f"Built mapping for {len(mapping)} products from processed CSVs.")
    return mapping

# --- UPDATED: Use mapping to set category in Supabase ---
def set_category_for_all_products():
    """
    Update the 'category' field for all products in Supabase using the mapping from processed CSVs.
    """
    name_to_category = build_name_to_category_mapping()
    try:
        updated_count = 0
        skipped_count = 0
        matched_count = 0
        total_processed = 0
        page = 0
        page_size = 1000
        while True:
            # Fetch products with pagination
            result = supabase.table('Products').select('id, name, category').range(
                page * page_size,
                (page + 1) * page_size - 1
            ).execute()
            if hasattr(result, 'error') and result.error:
                print(f"Error fetching products: {result.error}")
                return
            products = result.data
            if not products:
                break
            print(f"\nProcessing page {page + 1} ({len(products)} products)")
            for product in products:
                name = str(product.get('name', '')).strip()
                category = name_to_category.get(name)
                if category and category != product.get('category'):
                    matched_count += 1
                    update_result = supabase.table('Products').update({
                        'category': category
                    }).eq('id', product['id']).execute()
                    if hasattr(update_result, 'error') and update_result.error:
                        print(f"Error updating product {product['id']}: {update_result.error}")
                        skipped_count += 1
                    else:
                        updated_count += 1
                        print(f"Updated category for product: {name} -> {category}")
                else:
                    skipped_count += 1
                    print(f"Skipped product: {name} (no category to set, already set, or not found in mapping)")
                total_processed += 1
            page += 1
            time.sleep(0.5)  # Be gentle to the API
        print(f"\nSummary:")
        print(f"Total products processed: {total_processed}")
        print(f"Matched and updated: {updated_count}")
        print(f"Matched but failed to update: {matched_count - updated_count}")
        print(f"Skipped: {skipped_count}")
    except Exception as e:
        print(f"Error setting categories: {str(e)}")
        import traceback
        print(traceback.format_exc())

def main():
    print("Starting to set category for all products in Supabase using processed CSVs...")
    set_category_for_all_products()
    print("Process completed.")

if __name__ == "__main__":
    main() 