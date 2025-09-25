import pandas as pd
from pathlib import Path
from supabase import create_client
import os
from dotenv import load_dotenv
import ast
from pprint import pprint
import argparse
import math
import json
import time
import requests
import datetime
from typing import Optional, List
from processors.helpers.additives.additives_relation_manager import AdditivesRelationManager

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
supabase = create_client(supabase_url, supabase_key)

def fetch_additives_from_off(barcode: str) -> Optional[List[str]]:
    """
    Fetch additives_tags from Open Food Facts API.
    
    Args:
        barcode: Product barcode
        
    Returns:
        List of additives tags or None if not found/error
    """
    if not barcode or barcode == 'nan' or barcode == '':
        return None
        
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            product = data.get('product', {})
            
            additives_tags = product.get('additives_tags', [])
            
            if additives_tags and isinstance(additives_tags, list):
                # Clean up the additives tags (remove 'en:' prefix if present)
                cleaned_additives = []
                for tag in additives_tags:
                    if tag.startswith('en:'):
                        cleaned_additives.append(tag[3:])  # Remove 'en:' prefix
                    else:
                        cleaned_additives.append(tag)
                
                return cleaned_additives
            else:
                return []
        else:
            return None
            
    except Exception as e:
        print(f"Error fetching additives for barcode {barcode}: {e}")
        return None

def is_processed_csv(file_path):
    """
    Check if the file is a processed CSV file.
    
    Args:
        file_path (Path): Path to the file
        
    Returns:
        bool: True if the file is a processed CSV, False otherwise
    """
    return file_path.is_file() and file_path.name.endswith('_processed.csv')

def analyze_data_structure(records, table_name):
    """
    Analyze and display the structure of data before saving to Supabase.
    
    Args:
        records (list): List of dictionaries to be saved
        table_name (str): Name of the Supabase table
    """
    if not records:
        print(f"No records to analyze for table {table_name}")
        return
    
    print(f"\nAnalyzing data structure for table '{table_name}':")
    print("-" * 50)
    
    # Get all unique keys from all records
    all_keys = set()
    for record in records:
        all_keys.update(record.keys())
    
    # Analyze each column
    print("\nColumns and their data types:")
    print("-" * 50)
    for key in sorted(all_keys):
        # Get sample values for this key
        values = [record.get(key) for record in records if key in record]
        if values:
            # Get type of first non-None value
            sample_type = type(next((v for v in values if v is not None), None))
            # Get sample value (first non-None)
            sample_value = next((v for v in values if v is not None), None)
            
            print(f"\nColumn: {key}")
            print(f"Type: {sample_type.__name__}")
            print(f"Sample value: {sample_value}")
            
            # Special handling for dictionaries and lists
            if isinstance(sample_value, (dict, list)):
                print(f"Structure: {type(sample_value).__name__} with {len(sample_value)} items")
                if isinstance(sample_value, dict):
                    print("Keys:", list(sample_value.keys()))
    
    print("\nSummary:")
    print("-" * 50)
    print(f"Total records: {len(records)}")
    print(f"Total columns: {len(all_keys)}")
    print(f"Columns: {sorted(all_keys)}")

def clean_value(value):
    """
    Clean a value to ensure it's JSON compliant.
    
    Args:
        value: The value to clean
        
    Returns:
        The cleaned value
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    elif isinstance(value, dict):
        return {k: clean_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [clean_value(item) for item in value]
    return value

def clean_record(record):
    """
    Clean a record to ensure all values are JSON compliant.
    
    Args:
        record (dict): The record to clean
        
    Returns:
        dict: The cleaned record
    """
    return {k: clean_value(v) for k, v in record.items()}

def validate_record(record):
    """
    Validate a record to ensure it matches Supabase's expected types and has required fields.
    
    Args:
        record (dict): The record to validate
        
    Returns:
        dict: The validated record, or None if required fields are missing
    """
    # Check required fields
    required_fields = ['name']
    for field in required_fields:
        if not record.get(field):
            print(f"Warning: Skipping record due to missing required field '{field}'")
            return None
    
    validated = {}
    
    # Text fields
    for field in ['name', 'description', 'barcode', 'category', 'ingredients', 'supermarket_url', 'image_front_url']:
        if field in record:
            validated[field] = str(record[field]) if record[field] is not None else None
    
    # Integer fields
    if 'health_score' in record:
        validated['health_score'] = int(record['health_score']) if record['health_score'] is not None else None
    
    # Array field
    if 'additional_images_urls' in record:
        validated['additional_images_urls'] = [str(url) for url in record['additional_images_urls']] if record['additional_images_urls'] else []
    
    # JSONB fields
    if 'specifications' in record:
        validated['specifications'] = record['specifications'] if record['specifications'] else {}
    
    if 'nutritional' in record:
        validated['nutritional'] = record['nutritional'] if record['nutritional'] else {}
    
    # Array fields
    if 'additives_tags' in record:
        validated['additives_tags'] = record['additives_tags'] if record['additives_tags'] else []
    
    # Timestamp fields
    if 'additives_updated_at' in record:
        validated['additives_updated_at'] = record['additives_updated_at'] if record['additives_updated_at'] else None
    
    if 'imported_at' in record:
        validated['imported_at'] = record['imported_at'] if record['imported_at'] else None
    
    return validated

def get_existing_products():
    """
    Fetch all existing product names from Supabase.
    
    Returns:
        set: Set of existing product names
    """
    try:
        result = supabase.table('products').select('name').execute()
        if hasattr(result, 'error') and result.error:
            print(f"Error fetching existing products: {result.error}")
            return set()
        
        # Extract names from the response and convert to lowercase for case-insensitive comparison
        existing_names = {item['name'].lower() for item in result.data if item.get('name')}
        print(f"Found {len(existing_names)} existing products")
        return existing_names
    except Exception as e:
        print(f"Error fetching existing products: {str(e)}")
        return set()

def process_csv_for_supabase(csv_path):
    """
    Process a CSV file and prepare data for Supabase insertion.
    
    Args:
        csv_path (Path): Path to the CSV file
        
    Returns:
        list: List of dictionaries ready for Supabase insertion
    """
    # Get existing products
    existing_products = get_existing_products()
    
    # Initialize additives relation manager
    additives_manager = AdditivesRelationManager()
    
    # Set the same imported_at timestamp for all products in this batch
    imported_at = datetime.datetime.now().isoformat()
    print(f"Setting imported_at timestamp for this batch: {imported_at}")
    
    # Read the CSV file with barcode as string
    df = pd.read_csv(csv_path, dtype={'barcode': str})
    
    # Convert string representations of lists/dicts to actual Python objects
    for col in ['specifications', 'nutritional_info', 'image_urls']:
        if col in df.columns:
            df[col] = df[col].apply(ast.literal_eval)
    
    # Map the data to Supabase table structure
    records = []
    skipped_records = 0
    duplicate_records = 0
    additives_fetched = 0
    additives_found = 0
    
    print(f"\nProcessing {len(df)} products for Supabase insertion...")
    print("Fetching additives from Open Food Facts API...")
    
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            # Fetch additives if barcode is available
            additives_tags = None
            if row['barcode'] and str(row['barcode']) != 'nan':
                print(f"  [{idx + 1}/{len(df)}] Fetching additives for {row['name']} (Barcode: {row['barcode']})")
                additives_tags = fetch_additives_from_off(str(row['barcode']))
                additives_fetched += 1
                
                if additives_tags is not None:
                    if additives_tags:
                        print(f"    ✅ Found {len(additives_tags)} additives: {additives_tags[:3]}...")
                        additives_found += 1
                    else:
                        print(f"    ℹ️  No additives found")
                else:
                    print(f"    ❌ Failed to fetch additives")
                
                # Add small delay to avoid overwhelming the API
                time.sleep(0.5)
            
            record = {
                'name': row['name'],
                'description': row['description'],
                'barcode': row['barcode'],
                'category': row['specifications'].get('product_type'),
                'ingredients': row['ingredients'],
                'supermarket_url': row['url'],
                'image_front_url': row['image_urls'][0] if row['image_urls'] else None,
                'additional_images_urls': row['image_urls'][1:] if len(row['image_urls']) > 1 else [],
                'specifications': row['specifications'],
                'nutritional': row['nutritional_info'],
                'health_score': row.get('health_score'),
                'external_id': row.get('external_id'),
                'additives_tags': additives_tags,
                'imported_at': imported_at,
            }
            
            # Check if product already exists
            if record['name'] and record['name'].lower() in existing_products:
                print(f"Skipping duplicate product: {record['name']}")
                duplicate_records += 1
                continue
            
            # Clean and validate the record
            cleaned_record = clean_record(record)
            validated_record = validate_record(cleaned_record)
            
            if validated_record:
                records.append(validated_record)
                # Add to existing products set to prevent duplicates within the same batch
                if validated_record['name']:
                    existing_products.add(validated_record['name'].lower())
            else:
                skipped_records += 1
                
        except Exception as e:
            print(f"Error processing row: {str(e)}")
            skipped_records += 1
            continue
    
    if skipped_records > 0:
        print(f"\nSkipped {skipped_records} records due to missing required fields or errors")
    if duplicate_records > 0:
        print(f"Skipped {duplicate_records} records due to duplicate product names")
    
    print(f"\nAdditives Summary:")
    print(f"  Products with barcodes processed: {additives_fetched}")
    print(f"  Products with additives found: {additives_found}")
    print(f"  Success rate: {(additives_found / additives_fetched * 100):.1f}%" if additives_fetched > 0 else "N/A")
    
    return records, additives_manager

def save_to_supabase(records, table_name, additives_manager=None):
    """
    Save records to Supabase table and create additives relations.
    
    Args:
        records (list): List of dictionaries to insert
        table_name (str): Name of the Supabase table
        additives_manager: AdditivesRelationManager instance for creating relations
    """
    if not records:
        print("No valid records to save")
        return
        
    try:
        # Insert records in batches of 100
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            print(f"\nSaving batch {i//batch_size + 1} of {(len(records) + batch_size - 1)//batch_size}")
            print(f"Batch size: {len(batch)} records")
            
            # Convert the batch to JSON to validate it
            try:
                json.dumps(batch)
            except Exception as e:
                print(f"JSON validation error: {str(e)}")
                print("Problematic record:", batch[0] if batch else "No records")
                raise
            
            result = supabase.table(table_name).insert(batch).execute()
            
            # Check if the response contains error information
            if hasattr(result, 'error') and result.error:
                print(f"Supabase error: {result.error}")
                raise Exception(f"Supabase error: {result.error}")
            
            # Print success message with record count
            print(f"Successfully inserted {len(batch)} records")
            
            # Create additives relations for the inserted products
            if additives_manager and result.data:
                print(f"\nCreating additives relations for {len(result.data)} products...")
                for product in result.data:
                    product_id = product.get('id')
                    additives_tags = product.get('additives_tags')
                    product_name = product.get('name', 'Unknown Product')
                    
                    if product_id and additives_tags:
                        additives_manager.create_relations_for_product(
                            product_id=product_id,
                            additives_tags=additives_tags,
                            product_name=product_name
                        )
            
    except Exception as e:
        print(f"Error saving to Supabase: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response}")
        raise

def process_single_file(csv_path):
    """
    Process a single CSV file and save to Supabase.
    
    Args:
        csv_path (Path): Path to the CSV file
    """
    print(f"\nProcessing {csv_path}")
    
    try:
        # Process CSV data
        records, additives_manager = process_csv_for_supabase(csv_path)
        
        # Get table name from the subcategory folder name
        table_name = 'Products'
        
        # Analyze data structure before saving
        analyze_data_structure(records, table_name)
        
        # Save to Supabase with additives relations
        save_to_supabase(records, table_name, additives_manager)
        print(f"Successfully saved data from {csv_path} to Supabase table '{table_name}'")
        
        # Show the imported_at timestamp for this batch
        if records:
            sample_imported_at = records[0].get('imported_at')
            print(f"All products in this batch have imported_at: {sample_imported_at}")
        
        # Print additives relations statistics
        additives_manager.print_statistics()
        
    except Exception as e:
        print(f"Error processing {csv_path}: {str(e)}")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process CSV files and save to Supabase')
    parser.add_argument('--file', type=str, help='Path to a specific CSV file to process')
    args = parser.parse_args()

    # Get the current script's directory and navigate to the auchan folder
    current_dir = Path(__file__).parent.parent.parent.parent
    base_directory = current_dir / "auchan"
    
    if not base_directory.exists():
        print(f"Error: Directory {base_directory} does not exist")
        return

    if args.file:
        # Process single file mode
        csv_path = Path(args.file)
        if not csv_path.exists():
            print(f"Error: File {csv_path} does not exist")
            return
        if not is_processed_csv(csv_path):
            print(f"Error: File {csv_path} is not a processed CSV file")
            return
        process_single_file(csv_path)
    else:
        # Process all files mode
        processed_csvs = [f for f in base_directory.rglob("*") if is_processed_csv(f)]
        
        if not processed_csvs:
            print("No processed CSV files found")
            return
        
        print(f"Found {len(processed_csvs)} processed CSV files")
        
        for csv_path in processed_csvs:
            process_single_file(csv_path)

if __name__ == "__main__":
    main() 