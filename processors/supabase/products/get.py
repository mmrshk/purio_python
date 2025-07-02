import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
supabase = create_client(supabase_url, supabase_key)

def get_products_with_barcodes():
    """
    Get all products that have barcodes from Supabase and list them.
    """
    try:
        # Print the API URL being used
        print(f"\nUsing Supabase URL: {supabase_url}/rest/v1/Products?select=*&barcode=not.is.null")
        
        # Get all products with barcodes
        result = supabase.table('Products').select('*').not_.is_('barcode', 'null').execute()
        
        if hasattr(result, 'error') and result.error:
            print(f"Error fetching products: {result.error}")
            return
        
        products = result.data
        print(f"\nFound {len(products)} products with barcodes")
        
        # Convert to DataFrame for easier display
        df = pd.DataFrame(products)
        
        # Sort by name for better readability
        df = df.sort_values('name')
        
        # Print each product with its barcode
        print("\nProducts with barcodes:")
        print("-" * 80)
        for _, row in df.iterrows():
            print(f"Name: {row['name']}")
            print(f"Barcode: {row['barcode']} (Type: {type(row['barcode'])})")
            print("-" * 80)
        
        # Print summary
        print(f"\nTotal products with barcodes: {len(products)}")
        print("\nBarcode types distribution:")
        print(df['barcode'].apply(type).value_counts())
        
    except Exception as e:
        print(f"Error getting products: {str(e)}")
        import traceback
        print(traceback.format_exc())

def main():
    print("Starting to fetch products with barcodes...")
    get_products_with_barcodes()
    print("Process completed.")

if __name__ == "__main__":
    main() 