import argparse
from pathlib import Path
from processors.scraper.collect_links_v2 import LinkCollectorV2
from processors.scraper.auchan_scraper import AuchanScraper
from processors.supabase.products.create import process_single_file
from processors.barcodes.barcode_filler import fill_barcodes_in_csv
from processors.helpers.map_specifications_and_nutritional_info import process_csv_columns
import os
import time
import json

# Search and put category ID on line 120
# To find the category ID, open desired category, open network, search for:
# route":{"domain":"store","id":"store.search#subcategory","params":{"id":

def process_category(category_url, category_id):
    """
    Process a category through the entire pipeline:
    1. Collect links (if needed)
    2. Scrape products (if needed)
    3. Save to CSV (if needed)
    4. Process barcodes
    5. Map specifications and nutritional info
    6. Save to Supabase
    
    Args:
        category_url (str): The URL of the category to process
        category_id (str): The category ID to use for product collection
    """
    print(f"\n=== Starting processing for category: {category_url} ===\n")
    print(f"Using category ID: {category_id}\n")
    
    # Get category and subcategory names from URL
    # Example URL: https://www.auchan.ro/bauturi-si-tutun/apa/apa-plata/c
    parts = category_url.split('/')
    category = parts[-3]  # 'apa'
    subcategory = parts[-2]  # 'apa-plata'
    
    # Initialize scraper
    scraper = AuchanScraper()
    
    # Check if category folder and CSV already exist
    category_dir = os.path.join('auchan', category, subcategory)
    csv_path = os.path.join(category_dir, f"{subcategory}.csv")
    processed_csv_path = os.path.join(category_dir, f"{subcategory}_processed.csv")
    links_file = os.path.join(category_dir, 'product_links.csv')
    
    if os.path.exists(csv_path):
        print(f"Found existing CSV file at {csv_path}")
        print("Skipping scraping steps...")
    else:
        # Step 1: Collect links
        print("Step 1: Collecting product links...")
        link_collector = LinkCollectorV2(category_id=category_id)
        link_collector.collect_links(category_url)
        
        # Get the generated links file path
        if not os.path.exists(links_file):
            print("Error: Links file not found!")
            return
        
        # Step 2: Scrape products
        print("\nStep 2: Scraping products...")
        scraper.links_file = links_file
        scraper.set_category_dir()
        scraper.set_images_dir()
        products = scraper.scrape_products()
        
        if not products:
            print("Error: No products were scraped!")
            return
        
        # Step 3: Save to CSV
        print("\nStep 3: Saving to CSV...")
        scraper.save_to_csv(f"{subcategory}.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    # Step 4: Process barcodes
    print("\nStep 4: Processing barcodes...")
    fill_barcodes_in_csv(csv_path, os.path.join(category_dir, 'images'))
    
    # Get the path to the processed CSV with barcodes
    if not os.path.exists(processed_csv_path):
        print(f"Error: Processed CSV file not found at {processed_csv_path}")
        return
    
    # Step 5: Map specifications and nutritional info
    print("\nStep 5: Mapping specifications and nutritional info...")
    df, unmapped_columns = process_csv_columns(processed_csv_path)
    
    if unmapped_columns:
        print("Warning: Found unmapped columns:")
        for col in unmapped_columns:
            print(f"  - {col}")
        
        # Save the unmapped columns to a file for reference
        unmapped_file = os.path.join(category_dir, 'unmapped_columns.json')
        with open(unmapped_file, 'w', encoding='utf-8') as f:
            json.dump(unmapped_columns, f, indent=2)
        print(f"Saved unmapped columns to {unmapped_file}")
    
    # Save the mapped data back to the processed CSV
    df.to_csv(processed_csv_path, index=False)
    print("Saved mapped data back to processed CSV")
    
    # Step 6: Save to Supabase
    print("\nStep 6: Saving to Supabase...")
    process_single_file(processed_csv_path)
    
    print(f"\n=== Completed processing for category: {category_url} ===\n")
    print("Summary:")
    print(f"- Category: {category}")
    print(f"- Subcategory: {subcategory}")
    print(f"- Total products: {len(df)}")
    print(f"- Unmapped columns: {len(unmapped_columns)}")
    print(f"- CSV file: {processed_csv_path}")
    if unmapped_columns:
        print(f"- Unmapped columns file: {unmapped_file}")

def main():
    parser = argparse.ArgumentParser(description='Process a category through the entire pipeline')
    parser.add_argument('category_url', help='The URL of the category to process')
    parser.add_argument('--category-id', required=True, help='The category ID to use for product collection')
    args = parser.parse_args()
    
    process_category(args.category_url, args.category_id)

if __name__ == "__main__":
    main() 