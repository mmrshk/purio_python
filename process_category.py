import argparse
from pathlib import Path
from processors.scraper.collect_links_v2 import LinkCollectorV2
from processors.scraper.auchan_scraper import AuchanScraper
from processors.supabase.products.create import process_single_file
from processors.barcodes.barcode_filler import fill_barcodes_in_csv
from processors.helpers.map_specifications_and_nutritional_info import process_csv_columns
from processors.scoring.health_score_filler import fill_health_scores_in_csv
from processors.supabase.scoring.update_scores import update_all_scores
import os
import time
import json
import pandas as pd
import datetime

# Search and put category ID on line 120
# To find the category ID, open desired category, open network, search for:
# route":{"domain":"store","id":"store.search#subcategory","params":{"id":

def scrape_products(category_url, category_id, subcategory, scraper, category_dir):
    """Scrape products from the category URL."""
    # Step 1: Collect links
    print("Step 1: Collecting product links...")
    link_collector = LinkCollectorV2(category_id=category_id)
    link_collector.collect_links(category_url)
    
    # Get the generated links file path
    links_file = os.path.join(category_dir, 'product_links.csv')
    if not os.path.exists(links_file):
        print("Error: Links file not found!")
        return False
    
    # Step 2: Scrape products
    print("\nStep 2: Scraping products...")
    scraper.links_file = links_file
    scraper.set_category_dir()
    scraper.set_images_dir()
    products = scraper.scrape_products()
    
    if not products:
        print("Error: No products were scraped!")
        return False
    
    # Step 3: Save to CSV
    print("\nStep 3: Saving to CSV...")
    scraper.save_to_csv(f"{subcategory}.csv")
    return True

def process_barcodes(csv_path, category_dir):
    """Process barcodes for the CSV file."""
    print("Step 4: Processing barcodes...")
    fill_barcodes_in_csv(csv_path, os.path.join(category_dir, 'images'))

def map_specifications(processed_csv_path, category_dir):
    """Map specifications and nutritional info, return df, unmapped_columns, and unmapped_file."""
    print("Step 5: Mapping specifications and nutritional info...")
    df, unmapped_columns = process_csv_columns(processed_csv_path)
    
    unmapped_file = None
    if unmapped_columns:
        print("Warning: Found unmapped columns:")
        for col in unmapped_columns:
            print(f"  - {col}")
        
        # Save the unmapped columns to a file for reference
        unmapped_file = os.path.join(category_dir, 'unmapped_columns.json')
        with open(unmapped_file, 'w', encoding='utf-8') as f:
            json.dump(unmapped_columns, f, indent=2)
        print(f"Saved unmapped columns to {unmapped_file}")
    
    # Add imported_at column if it doesn't exist
    if 'imported_at' not in df.columns:
        current_timestamp = datetime.datetime.now().isoformat()
        df['imported_at'] = current_timestamp
        print(f"Added imported_at column with timestamp: {current_timestamp}")
    
    # Save the mapped data back to the processed CSV
    df.to_csv(processed_csv_path, index=False)
    print("Saved mapped data back to processed CSV")
    
    return df, unmapped_columns, unmapped_file

def process_category(category_url, category_id, start_from="scraping"):
    """
    Process a category through the entire pipeline:
    1. Collect links (if needed)
    2. Scrape products (if needed)
    3. Save to CSV (if needed)
    4. Process barcodes
    5. Map specifications and nutritional info
    6. Save to Supabase
    7. Calculate health scores
    
    Args:
        category_url (str): The URL of the category to process
        category_id (str): The category ID to use for product collection
        start_from (str): Which step to start from. Options:
            - "scraping" (default - full pipeline)
            - "barcodes" (skip scraping)
            - "supabase" (skip scraping + barcodes + mapping)
            - "health-scoring" (skip everything except health scoring)
    """
    print(f"\n=== Starting processing for category: {category_url} ===\n")
    print(f"Using category ID: {category_id}\n")
    print(f"Starting from step: {start_from}\n")
    
    # Get category and subcategory names from URL
    # Handle both formats:
    # 3-level: https://www.auchan.ro/bauturi-si-tutun/apa/apa-plata/c
    # 2-level: https://www.auchan.ro/bacanie/c
    parts = category_url.split('/')
    if len(parts) >= 4 and parts[-1] == 'c':
        if parts[-3] == 'c':  # 2-level URL like /bacanie/c
            category = parts[-2]  # 'bacanie'
            subcategory = parts[-2]  # Use same as category for 2-level URLs
        else:  # 3-level URL like /bauturi-si-tutun/apa/apa-plata/c
            category = parts[-3]  # 'apa'
            subcategory = parts[-2]  # 'apa-plata'
    else:
        raise ValueError(f"Invalid category URL format: {category_url}")
    
    # Initialize scraper
    scraper = AuchanScraper()
    
    # Check if category folder and CSV already exist
    category_dir = os.path.join('auchan', category, subcategory)
    csv_path = os.path.join(category_dir, f"{subcategory}.csv")
    processed_csv_path = os.path.join(category_dir, f"{subcategory}_processed.csv")
    links_file = os.path.join(category_dir, 'product_links.csv')
    
    # Print start point information
    if start_from == "health-scoring":
        print("Starting from health scoring only...")
        print("Skipping steps 1-6 (scraping, barcodes, mapping, Supabase)...")
    elif start_from == "supabase":
        print("Starting from Supabase insertion...")
        print("Skipping steps 1-5 (scraping, barcodes, mapping)...")
    elif start_from == "barcodes":
        print("Starting from barcode processing...")
        print("Skipping steps 1-3 (scraping)...")
    else:  # start_from == "scraping" (default)
        print("Starting from full pipeline...")
    
    # Handle different start points
    df = None
    unmapped_columns = None
    unmapped_file = None
    
    if start_from == "scraping":
        # Full pipeline - do everything
        if os.path.exists(csv_path):
            print(f"Found existing CSV file at {csv_path}")
            print("Skipping scraping steps...")
        else:
            if not scrape_products(category_url, category_id, subcategory, scraper, category_dir):
                return
        
        if not os.path.exists(csv_path):
            print(f"Error: CSV file not found at {csv_path}")
            return
        
        process_barcodes(csv_path, category_dir)
        
        if not os.path.exists(processed_csv_path):
            print(f"Error: Processed CSV file not found at {processed_csv_path}")
            return
        
        df, unmapped_columns, unmapped_file = map_specifications(processed_csv_path, category_dir)
        
    elif start_from == "barcodes":
        # Start from barcodes - skip scraping
        if not os.path.exists(csv_path):
            print(f"Error: CSV file not found at {csv_path}")
            return
        
        process_barcodes(csv_path, category_dir)
        
        if not os.path.exists(processed_csv_path):
            print(f"Error: Processed CSV file not found at {processed_csv_path}")
            return
        
        df, unmapped_columns, unmapped_file = map_specifications(processed_csv_path, category_dir)
        
    elif start_from == "supabase":
        # Start from Supabase - skip scraping, barcodes, mapping
        if not os.path.exists(processed_csv_path):
            print(f"Error: Processed CSV file not found at {processed_csv_path}")
            return
        
        # Load df for summary
        df = pd.read_csv(processed_csv_path)
        
        # Add imported_at column if it doesn't exist
        if 'imported_at' not in df.columns:
            current_timestamp = datetime.datetime.now().isoformat()
            df['imported_at'] = current_timestamp
            df.to_csv(processed_csv_path, index=False)
            print(f"Added imported_at column with timestamp: {current_timestamp}")
        
    elif start_from == "health-scoring":
        # Start from health scoring - skip everything except health scoring
        if not os.path.exists(processed_csv_path):
            print(f"Error: Processed CSV file not found at {processed_csv_path}")
            return
        
        # Load df for summary
        df = pd.read_csv(processed_csv_path)
    
    # Step 6: Save to Supabase (includes additives fetching and relations creation)
    if start_from != "health-scoring":
        print("\nStep 6: Saving to Supabase (with additives fetching and relations creation)...")
        process_single_file(processed_csv_path)
    else:
        print("Skipping Supabase insertion (starting from health scoring)...")
    
    # Step 7: Calculate health scores (after products have IDs and additives relations)
    print("\nStep 7: Calculating health scores...")

    df_check = pd.read_csv(processed_csv_path)
    if 'imported_at' in df_check.columns and len(df_check) > 0:
        imported_at_timestamp = df_check['imported_at'].iloc[0]
        print(f"Filtering products by imported_at timestamp: {imported_at_timestamp}")
        update_all_scores(imported_at_timestamp)
    else:
        print("No imported_at timestamp found, processing all products")
        update_all_scores()
    
    print(f"\n=== Completed processing for category: {category_url} ===\n")
    print("Summary:")
    print(f"- Category: {category}")
    print(f"- Subcategory: {subcategory}")
    print(f"- Total products: {len(df)}")
    if unmapped_columns is not None:
        print(f"- Unmapped columns: {len(unmapped_columns)}")
        if unmapped_columns:
            print(f"- Unmapped columns file: {unmapped_file}")
    print(f"- CSV file: {processed_csv_path}")

def main():
    parser = argparse.ArgumentParser(description='Process a category through the entire pipeline')
    parser.add_argument('category_url', help='The URL of the category to process')
    parser.add_argument('--category-id', required=True, help='The category ID to use for product collection')
    parser.add_argument('--start-from', 
                       choices=['scraping', 'barcodes', 'supabase', 'health-scoring'],
                       default='scraping',
                       help='Which step to start from (default: scraping)')
    args = parser.parse_args()
    
    process_category(args.category_url, args.category_id, args.start_from)

if __name__ == "__main__":
    main() 