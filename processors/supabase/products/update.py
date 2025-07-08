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

def clean_barcode(barcode):
    """
    Clean up barcode by removing .0 suffix and validating format.
    Returns None for invalid barcodes (URLs, websites, etc).
    """
    if not barcode:
        return None
        
    # Skip URLs and websites
    if isinstance(barcode, str) and ('http' in barcode or 'www.' in barcode):
        return None
        
    # Remove .0 suffix if present
    if isinstance(barcode, str) and barcode.endswith('.0'):
        barcode = str(int(float(barcode)))
        
    # Validate barcode format (should be numeric)
    if isinstance(barcode, str) and barcode.isdigit():
        return barcode
        
    return None

def fix_barcodes():
    """
    Update barcodes in Supabase by cleaning them up.
    """
    try:
        updated_count = 0
        skipped_count = 0
        total_processed = 0
        
        # Start with first page
        page = 0
        page_size = 1000
        
        while True:
            # Get products with pagination
            result = supabase.table('products').select('id, name, barcode').range(
                page * page_size, 
                (page + 1) * page_size - 1
            ).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"Error fetching products: {result.error}")
                return
            
            products = result.data
            if not products:  # No more products to process
                break
                
            print(f"\nProcessing page {page + 1} ({len(products)} products)")
            
            for product in products:
                barcode = product.get('barcode')
                if barcode:
                    print(f"\nProcessing product {product['name']}:")
                    print(f"Original barcode: {barcode} (Type: {type(barcode)})")
                    
                    new_barcode = clean_barcode(barcode)
                    
                    if new_barcode:
                        # Update the product
                        update_result = supabase.table('products').update({
                            'barcode': new_barcode
                        }).eq('id', product['id']).execute()
                        
                        if hasattr(update_result, 'error') and update_result.error:
                            print(f"Error updating product {product['id']}: {update_result.error}")
                        else:
                            updated_count += 1
                            print(f"Updated barcode: {barcode} -> {new_barcode}")
                    else:
                        skipped_count += 1
                        print(f"Skipping invalid barcode: {barcode}")
                else:
                    print(f"\nSkipping product {product['name']}: No barcode")
                
                total_processed += 1
            
            page += 1
        
        print(f"\nSummary:")
        print(f"Total products processed: {total_processed}")
        print(f"Successfully updated: {updated_count}")
        print(f"Skipped invalid barcodes: {skipped_count}")
        
    except Exception as e:
        print(f"Error fixing barcodes: {str(e)}")
        import traceback
        print(traceback.format_exc())

def main():
    print("Starting barcode update process...")
    fix_barcodes()
    print("Barcode update process completed.")

if __name__ == "__main__":
    main() 