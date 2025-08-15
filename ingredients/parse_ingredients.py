#!/usr/bin/env python3
"""
Script to parse ingredients for products in Supabase and save parsed_ingredients to specifications.

This script:
1. Fetches products from Supabase that have ingredients but no parsed_ingredients
2. Uses the check_product_ingredients function to parse ingredients
3. Saves the parsed ingredients to the specifications column
4. Provides detailed logging and error handling
5. Supports batch processing for large datasets
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from supabase_ingredients_checker import SupabaseIngredientsChecker

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are not set in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def log_and_print(message: str, log_file):
    """Print to console and write to log file"""
    print(message)
    log_file.write(message + '\n')
    log_file.flush()  # Ensure immediate write to file

def parse_ingredients_for_products():
    """Parse ingredients for all products that need it."""
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"ingredients_parsing_{timestamp}.log"
    
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_and_print(f"Ingredients Parsing - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_file)
        log_and_print("="*80, log_file)
        
        # Initialize ingredients checker
        try:
            checker = SupabaseIngredientsChecker()
            log_and_print(f"✅ Ingredients checker initialized with {len(checker.ingredients_data)//2} ingredients from Supabase", log_file)
        except Exception as e:
            log_and_print(f"❌ Failed to initialize ingredients checker: {str(e)}", log_file)
            return
        
        # Fetch products that have ingredients but no parsed_ingredients
        log_and_print("\n🔍 Fetching products from Supabase...", log_file)
        
        try:
            # Get products with ingredients but no parsed_ingredients
            result = supabase.table('products').select('*').not_.is_('specifications->ingredients', 'null').is_('specifications->parsed_ingredients', 'null').execute()
            
            if hasattr(result, 'error') and result.error:
                error_msg = f"Error fetching products: {result.error}"
                log_and_print(error_msg, log_file)
                return
            
            products = result.data
            log_and_print(f"Found {len(products)} products to process", log_file)
            
        except Exception as e:
            log_and_print(f"❌ Error fetching products: {str(e)}", log_file)
            return
        
        if not products:
            log_and_print("No products found that need ingredients parsing", log_file)
            return
        
        # Track statistics
        successful_updates = 0
        failed_updates = 0
        skipped_products = 0
        
        for i, product in enumerate(products, 1):
            product_name = product.get('name', 'Unknown')
            product_id = product.get('id', 'N/A')
            
            log_and_print(f"\n{'='*80}", log_file)
            log_and_print(f"PRODUCT {i}/{len(products)}: {product_name} (ID: {product_id})", log_file)
            log_and_print(f"{'='*80}", log_file)
            
            try:
                # Parse ingredients using the checker
                parsing_result = checker.check_product_ingredients(product)
                
                # Log the parsing results
                log_and_print(f"\n📋 INGREDIENTS PARSING RESULTS:", log_file)
                log_and_print(f"{'-'*50}", log_file)
                
                ingredients_text = parsing_result.get('ingredients_text')
                if ingredients_text:
                    log_and_print(f"Original ingredients: {ingredients_text[:100]}{'...' if len(ingredients_text) > 100 else ''}", log_file)
                else:
                    log_and_print(f"No ingredients text found", log_file)
                    skipped_products += 1
                    continue
                
                extracted_ingredients = parsing_result.get('extracted_ingredients', [])
                matches = parsing_result.get('matches', [])
                
                log_and_print(f"Extracted ingredients: {len(extracted_ingredients)}", log_file)
                log_and_print(f"Matched ingredients: {len(matches)}", log_file)
                
                if matches:
                    log_and_print(f"Matches found:", log_file)
                    for match in matches:
                        original = match.get('original', '')
                        matched_name = match.get('matched_name', '')
                        score = match.get('score', 0)
                        nova_score = match.get('data', {}).get('nova_score', 'N/A')
                        log_and_print(f"  ✓ '{original}' → '{matched_name}' (NOVA: {nova_score}, Score: {score}%)", log_file)
                
                # Create parsed_ingredients data structure
                parsed_ingredients = {
                    'extracted_ingredients': extracted_ingredients,
                    'matches': [
                        {
                            'original': match.get('original'),
                            'matched_name': match.get('matched_name'),
                            'matched_ingredient_id': match.get('data', {}).get('id'),
                            'nova_score': match.get('data', {}).get('nova_score'),
                            'english_name': match.get('data', {}).get('name'),
                            'romanian_name': match.get('data', {}).get('name_ro')
                        }
                        for match in matches
                    ],
                    'parsed_at': datetime.now().isoformat()
                }
                
                # Print the data structure being saved
                log_and_print(f"\n💾 DATA STRUCTURE TO SAVE:", log_file)
                log_and_print(f"{'-'*50}", log_file)
                log_and_print(f"parsed_ingredients = {json.dumps(parsed_ingredients, indent=2, ensure_ascii=False)}", log_file)
                
                # Update Supabase
                if product_id != 'N/A':
                    try:
                        # Get current specifications
                        current_specs = product.get('specifications', {})
                        if isinstance(current_specs, str):
                            try:
                                current_specs = json.loads(current_specs)
                            except:
                                current_specs = {}
                        
                        # Add parsed_ingredients to specifications
                        current_specs['parsed_ingredients'] = parsed_ingredients
                        
                        # Update the product
                        update_data = {
                            'specifications': current_specs,
                            'updated_at': datetime.now().isoformat()
                        }
                        
                        log_and_print(f"🔄 Updating database with parsed ingredients...", log_file)
                        
                        result = supabase.table('products').update(update_data).eq('id', product_id).execute()
                        
                        if hasattr(result, 'error') and result.error:
                            log_and_print(f"❌ Database update failed: {result.error}", log_file)
                            failed_updates += 1
                        else:
                            log_and_print(f"✅ Database updated successfully", log_file)
                            successful_updates += 1
                            
                    except Exception as e:
                        log_and_print(f"❌ Database update error: {str(e)}", log_file)
                        failed_updates += 1
                else:
                    log_and_print(f"⚠️  Skipped database update (no product ID)", log_file)
                    skipped_products += 1
                    
            except Exception as e:
                log_and_print(f"❌ Error processing product: {str(e)}", log_file)
                failed_updates += 1
            
            log_and_print(f"\n{'='*80}\n", log_file)
        
        # Summary at the end
        log_and_print(f"\n{'='*80}", log_file)
        log_and_print(f"PARSING COMPLETE - {len(products)} products processed", log_file)
        log_and_print(f"✅ Successful updates: {successful_updates}", log_file)
        log_and_print(f"❌ Failed updates: {failed_updates}", log_file)
        log_and_print(f"⚠️  Skipped products: {skipped_products}", log_file)
        log_and_print(f"Log file saved as: {log_filename}", log_file)
        log_and_print(f"{'='*80}", log_file)
    
    print(f"\n✅ Parsing complete! Results saved to: {log_filename}")
    print(f"📊 Summary: {successful_updates} updated, {failed_updates} failed, {skipped_products} skipped")

if __name__ == "__main__":
    parse_ingredients_for_products()
