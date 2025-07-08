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

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
supabase = create_client(supabase_url, supabase_key)

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
    
    for _, row in df.iterrows():
        try:
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
    
    return records

def save_to_supabase(records, table_name):
    """
    Save records to Supabase table.
    
    Args:
        records (list): List of dictionaries to insert
        table_name (str): Name of the Supabase table
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
        records = process_csv_for_supabase(csv_path)
        
        # Get table name from the subcategory folder name
        table_name = 'Products'
        
        # Analyze data structure before saving
        analyze_data_structure(records, table_name)
        
        # Ask for confirmation before saving
        # response = input("\nDo you want to save this data to Supabase? (y/n): ")
        # if response.lower() != 'y':
        #     print("Skipping this file...")
        #     return
        
        # Save to Supabase
        save_to_supabase(records, table_name)
        print(f"Successfully saved data from {csv_path} to Supabase table '{table_name}'")
        
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