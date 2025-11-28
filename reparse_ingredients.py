#!/usr/bin/env python3
"""
Script to re-parse ingredients using the same logic as parse_ingredients.py.

This script:
1. Uses the same logic as ingredients/parse_ingredients.py
2. Re-parses ingredients using SupabaseIngredientsChecker
3. Saves result to parsed_ingredients field in specifications
4. Supports batch processing for all products
5. Has resume capability (skips already processed products)
6. Automatically skips products updated yesterday or today (avoids re-processing)

Usage:
    python reparse_ingredients.py [--product-id PRODUCT_ID] [--batch] [--batch-size SIZE] [--dry-run]
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from process_single_product import SingleProductProcessor

# Load environment variables
load_dotenv()

class IngredientsReparser:
    def __init__(self, dry_run: bool = False):
        """
        Initialize the ingredients reparser.
        
        Args:
            dry_run: If True, don't actually update the database
        """
        self.dry_run = dry_run
        
        # Initialize Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        
        # Statistics
        self.stats = {
            'products_found': 0,
            'products_processed': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'errors': []
        }
    
    def reparse_single_product(self, product_id: str) -> bool:
        """
        Re-parse ingredients for a single product using parse_ingredients.py logic.
        
        Args:
            product_id: Product ID to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"🔄 Processing product: {product_id}")
            
            # Fetch product from database
            result = self.supabase.table('products').select('*').eq('id', product_id).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"❌ Error fetching product: {result.error}")
                return False
            
            products = result.data
            if not products:
                print(f"❌ Product with ID {product_id} not found")
                return False
            
            product = products[0]
            product_name = product.get('name', 'Unknown Product')
            
            print(f"📋 Product: {product_name}")
            
            # Parse ingredients using the same logic as parse_ingredients.py
            from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker
            checker = SupabaseIngredientsChecker()
            
            print(f"🧪 Parsing ingredients...")
            parsing_result = checker.check_product_ingredients(product)
            
            # Log the parsing results
            print(f"\n📋 INGREDIENTS PARSING RESULTS:")
            print(f"{'-'*50}")
            
            ingredients_text = parsing_result.get('ingredients_text')
            if ingredients_text:
                print(f"Original ingredients: {ingredients_text[:100]}{'...' if len(ingredients_text) > 100 else ''}")
            else:
                print(f"No ingredients text found")
                return False
            
            extracted_ingredients = parsing_result.get('extracted_ingredients', [])
            matches = parsing_result.get('matches', [])
            
            print(f"Extracted ingredients: {len(extracted_ingredients)}")
            print(f"Matched ingredients: {len(matches)}")
            
            if matches:
                print(f"Matches found:")
                for match in matches:
                    original = match.get('original', '')
                    matched_name = match.get('matched_name', '')
                    score = match.get('score', 0)
                    nova_score = match.get('data', {}).get('nova_score', 'N/A')
                    print(f"  ✓ '{original}' → '{matched_name}' (NOVA: {nova_score}, Score: {score}%)")
            
            # Create parsed_ingredients data structure (same as parse_ingredients.py)
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
            
            print(f"\n💾 DATA STRUCTURE TO SAVE:")
            print(f"{'-'*50}")
            print(f"parsed_ingredients = {json.dumps(parsed_ingredients, indent=2, ensure_ascii=False)}")
            
            # Update database
            if not self.dry_run:
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
                    
                    print(f"🔄 Updating database with parsed ingredients...")
                    
                    result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()
                    
                    if hasattr(result, 'error') and result.error:
                        print(f"❌ Database update failed: {result.error}")
                        self.stats['failed_updates'] += 1
                        return False
                    else:
                        print(f"✅ Database updated successfully")
                        self.stats['successful_updates'] += 1
                        return True
                        
                except Exception as e:
                    print(f"❌ Database update error: {str(e)}")
                    self.stats['failed_updates'] += 1
                    return False
            else:
                print(f"🔄 DRY RUN: Would update database")
                self.stats['successful_updates'] += 1
                return True
            
        except Exception as e:
            print(f"❌ Error processing product {product_id}: {str(e)}")
            self.stats['errors'].append(f"Processing error for {product_id}: {str(e)}")
            self.stats['failed_updates'] += 1
            return False
    
    def fetch_products_batch(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch a batch of products from Supabase, excluding products updated yesterday or today.
        
        Args:
            offset: Starting index
            limit: Number of products to fetch
            
        Returns:
            List of product dictionaries
        """
        try:
            # Get yesterday's date in ISO format
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Fetch products that were NOT updated yesterday or today using date comparison
            result = self.supabase.table('products').select('id, name, updated_at').range(offset, offset + limit - 1).lt('updated_at', f'{yesterday}T00:00:00').execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"❌ Error fetching products: {result.error}")
                return []
            
            return result.data
            
        except Exception as e:
            print(f"❌ Error fetching products: {str(e)}")
            return []
    
    def get_total_products_count(self) -> int:
        """Get total number of products in the database, excluding products updated yesterday or today."""
        try:
            # Get yesterday's date in ISO format
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Count products that were NOT updated yesterday or today
            result = self.supabase.table('products').select('id', count='exact').lt('updated_at', f'{yesterday}T00:00:00').execute()
            return result.count if hasattr(result, 'count') else 0
        except Exception as e:
            print(f"❌ Error getting product count: {str(e)}")
            return 0
    
    def find_product_offset(self, product_id: str) -> Optional[int]:
        """
        Find the offset (position) of a product in the database using a more efficient approach.
        
        Args:
            product_id: Product ID to find
            
        Returns:
            Offset if found, None if not found
        """
        try:
            # Use a more efficient approach: count products with id < target_id
            result = self.supabase.table('products').select('id', count='exact').lt('id', product_id).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"❌ Error finding product offset: {result.error}")
                return None
            
            # The count gives us the number of products before this one
            offset = result.count if hasattr(result, 'count') else 0
            
            # Verify the product exists
            verify_result = self.supabase.table('products').select('id').eq('id', product_id).execute()
            if hasattr(verify_result, 'error') and verify_result.error:
                print(f"❌ Error verifying product exists: {verify_result.error}")
                return None
            
            if not verify_result.data:
                print(f"❌ Product {product_id} not found")
                return None
            
            return offset
            
        except Exception as e:
            print(f"❌ Error finding product offset: {str(e)}")
            return None
    
    def reparse_all_products(self, batch_size: int = 50, resume_from_product_id: Optional[str] = None) -> None:
        """
        Re-parse ingredients for all products in batches.
        
        Args:
            batch_size: Number of products to process in each batch
            resume_from_product_id: Optional product ID to resume from (skips products before this one)
        """
        print("=" * 80)
        print("RE-PARSE INGREDIENTS FOR ALL PRODUCTS")
        print("=" * 80)
        
        if self.dry_run:
            print("🔄 DRY RUN MODE - No database updates will be made")
        
        # Get total count
        total_products = self.get_total_products_count()
        print(f"📦 Total products in database: {total_products}")
        
        if total_products == 0:
            print("ℹ️  No products found in database")
            return
        
        # Determine starting offset if resuming from specific product
        offset = 0
        if resume_from_product_id:
            print(f"🔄 Resuming from product ID: {resume_from_product_id}")
            offset = self.find_product_offset(resume_from_product_id)
            if offset is None:
                print(f"❌ Product ID {resume_from_product_id} not found. Starting from beginning.")
                offset = 0
            else:
                print(f"📍 Found product at offset {offset}. Resuming from there.")
        
        batch_num = 1
        
        while offset < total_products:
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num} (Products {offset + 1}-{min(offset + batch_size, total_products)})")
            print(f"{'='*60}")
            
            # Fetch batch
            products = self.fetch_products_batch(offset, batch_size)
            
            if not products:
                print("❌ No products found in this batch")
                break
            
            print(f"📦 Processing {len(products)} products in this batch...")
            
            # Process each product in the batch
            for i, product in enumerate(products, 1):
                product_id = product.get('id')
                product_name = product.get('name', 'Unknown Product')
                
                print(f"\n[{i}/{len(products)}] {product_name}")
                success = self.reparse_single_product(product_id)
                
                if success:
                    self.stats['products_processed'] += 1
                else:
                    self.stats['failed_updates'] += 1
            
            # Move to next batch
            offset += batch_size
            batch_num += 1
            
            # Add delay between batches to avoid overwhelming the database
            if offset < total_products:
                print(f"\n⏳ Waiting 2 seconds before next batch...")
                import time
                time.sleep(2)
        
        # Print final summary
        self.print_summary()
    
    def print_summary(self):
        """Print processing summary."""
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        
        print(f"📦 Products found: {self.stats['products_found']}")
        print(f"✅ Products processed: {self.stats['products_processed']}")
        print(f"✅ Successful updates: {self.stats['successful_updates']}")
        print(f"❌ Failed updates: {self.stats['failed_updates']}")
        
        if self.stats['errors']:
            print(f"\n❌ Errors ({len(self.stats['errors'])}):")
            for i, error in enumerate(self.stats['errors'], 1):
                print(f"   {i}. {error}")
        else:
            print(f"\n🎉 Processing completed successfully!")
        
        print("=" * 80)

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(
        description='Re-parse ingredients and recalculate scores using existing code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Re-parse ingredients for specific product
  python reparse_ingredients.py --product-id abc123
  
  # Re-parse ingredients for all products in batches
  python reparse_ingredients.py --batch
  
  # Re-parse with custom batch size
  python reparse_ingredients.py --batch --batch-size 25
  
  # Resume from a specific product ID
  python reparse_ingredients.py --batch --resume-from 6eef068a-0444-4cea-a9c9-ce74b1983b94
  
  # Dry run to see what would be done
  python reparse_ingredients.py --product-id abc123 --dry-run
        """
    )
    
    parser.add_argument(
        '--product-id',
        help='Specific product ID to process'
    )
    
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Process all products in batches'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of products to process in each batch (default: 50)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without actually updating the database'
    )
    
    parser.add_argument(
        '--resume-from',
        help='Resume processing from a specific product ID'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.product_id and not args.batch:
        print("❌ Error: Must specify either --product-id or --batch")
        sys.exit(1)
    
    if args.product_id and args.batch:
        print("❌ Error: Cannot specify both --product-id and --batch")
        sys.exit(1)
    
    try:
        reparser = IngredientsReparser(dry_run=args.dry_run)
        
        if args.product_id:
            # Process single product
            success = reparser.reparse_single_product(args.product_id)
            
            if success:
                print(f"\n✅ Product {args.product_id} processed successfully!")
            else:
                print(f"\n❌ Product {args.product_id} processing failed!")
                sys.exit(1)
        else:
            # Process all products in batches
            reparser.reparse_all_products(args.batch_size, args.resume_from)
            
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
