#!/usr/bin/env python3
"""
Script to process multiple products without final_score through the complete pipeline.

Fetches 20 products without final_score and processes each one using SingleProductProcessor.

Usage:
    python process_products_without_score.py [--limit 20] [--dry-run]
"""

import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from process_single_product import SingleProductProcessor

# Load environment variables
load_dotenv()


def fetch_products_without_score(limit: int = 20, supabase=None) -> List[Dict[str, Any]]:
    """
    Fetch products from Supabase that don't have a final_score.
    
    Args:
        limit: Maximum number of products to fetch
        supabase: Supabase client (if None, will create one)
        
    Returns:
        List of product dictionaries
    """
    if supabase is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
        
        supabase = create_client(supabase_url, supabase_key)
    
    try:
        print(f"🔍 Fetching up to {limit} products without final_score from Supabase...")
        
        result = supabase.table('products').select('id, name, barcode, final_score').is_('final_score', 'null').limit(limit).execute()
        
        if hasattr(result, 'error') and result.error:
            print(f"❌ Error fetching products: {result.error}")
            return []
        
        products = result.data
        print(f"✅ Found {len(products)} products without final_score")
        
        return products
        
    except Exception as e:
        print(f"❌ Error fetching products: {str(e)}")
        return []


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(
        description='Process multiple products without final_score through the complete pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process 20 products without final_score (default)
  python process_products_without_score.py
  
  # Process 10 products
  python process_products_without_score.py --limit 10
  
  # Dry run to see what would be done
  python process_products_without_score.py --limit 5 --dry-run
        """
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of products to process (default: 20)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without actually updating the database'
    )
    
    args = parser.parse_args()
    
    try:
        print("=" * 80)
        print("BATCH PROCESSING PRODUCTS WITHOUT FINAL SCORE")
        print("=" * 80)
        print(f"📊 Limit: {args.limit}")
        print(f"🔒 Dry run: {args.dry_run}")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Initialize processor
        processor = SingleProductProcessor(dry_run=args.dry_run)
        
        # Fetch products without final_score
        products = fetch_products_without_score(limit=args.limit, supabase=processor.supabase)
        
        if not products:
            print("❌ No products found to process")
            sys.exit(0)
        
        print(f"\n🔄 Processing {len(products)} products...")
        print("-" * 80)
        print()
        
        # Process each product
        successful = 0
        failed = 0
        errors = []
        
        for i, product in enumerate(products, 1):
            product_id = product.get('id')
            product_name = product.get('name', 'Unknown')
            
            print(f"\n[{i}/{len(products)}] Processing: {product_name}")
            print(f"   ID: {product_id}")
            print("-" * 80)
            
            try:
                success = processor.process_product(product_id)
                
                if success:
                    successful += 1
                    print(f"✅ Product {i}/{len(products)} processed successfully")
                else:
                    failed += 1
                    error_msg = f"Product {product_id} ({product_name}): Processing failed"
                    errors.append(error_msg)
                    print(f"❌ Product {i}/{len(products)} processing failed")
                    
            except Exception as e:
                failed += 1
                error_msg = f"Product {product_id} ({product_name}): {str(e)}"
                errors.append(error_msg)
                print(f"❌ Error processing product {i}/{len(products)}: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 80)
        print(f"✅ Successful: {successful}/{len(products)}")
        print(f"❌ Failed: {failed}/{len(products)}")
        
        if errors:
            print(f"\n❌ Errors ({len(errors)}):")
            for i, error in enumerate(errors, 1):
                print(f"   {i}. {error}")
        
        print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Exit with appropriate code
        if failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

