#!/usr/bin/env python3
"""
Script to recalculate all scoring values for products:
- Ingredients parsing
- Additives checking and fetching
- Health scoring (Nova, Nutri, Additives, Final, Display)

This script reuses the logic from process_single_product.py and reparse_ingredients.py
to provide a comprehensive recalculation tool.

Usage:
    python recalculate_scores.py --product-id PRODUCT_ID [--dry-run]
    python recalculate_scores.py --batch [--batch-size SIZE] [--dry-run]
    python recalculate_scores.py --all [--dry-run]
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

class ScoreRecalculator:
    def __init__(self, dry_run: bool = False):
        """
        Initialize the score recalculator.

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

        # Initialize processor
        self.processor = SingleProductProcessor(dry_run=dry_run)

        # Statistics
        self.stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

    def recalculate_single_product(self, product_id: str, *, standalone: bool = True) -> bool:
        """
        Recalculate all scores for a single product.

        Args:
            product_id: Product ID to recalculate

        Returns:
            True if successful, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"🔄 RECALCULATING SCORES FOR PRODUCT: {product_id}")
        print(f"{'='*80}")

        # Ensure standalone runs get their own timestamp
        if standalone:
            self.processor.set_batch_ai_parsed_time(None)

        try:
            # Step 1: Fetch product
            product = self.processor.fetch_product(product_id)
            if not product:
                print(f"❌ Product not found: {product_id}")
                self.stats['failed'] += 1
                return False

            # Step 2: Parse ingredients
            print(f"\n📝 Step 1: Parsing ingredients...")
            ingredients_result = self.processor.parse_ingredients(product)
            if not ingredients_result:
                print(f"❌ Ingredients parsing failed")
                self.stats['failed'] += 1
                return False

            # Step 3: Fetch additives
            print(f"\n🧪 Step 2: Fetching additives...")
            additives_success = self.processor.fetch_additives(product)
            if not additives_success:
                print(f"❌ Additives fetching failed")
                self.stats['failed'] += 1
                return False

            # Step 4: Calculate health scores
            print(f"\n📊 Step 3: Calculating health scores...")
            scoring_result = self.processor.calculate_health_scores(product)
            if not scoring_result:
                print(f"❌ Health scoring failed")
                self.stats['failed'] += 1
                return False

            # Step 5: Update database
            print(f"\n💾 Step 4: Updating database...")
            update_success = self.processor.update_database(product_id, scoring_result)
            if not update_success:
                print(f"❌ Database update failed")
                self.stats['failed'] += 1
                return False

            print(f"\n✅ SUCCESS: All scores recalculated for product {product_id}")
            self.stats['successful'] += 1
            return True

        except Exception as e:
            print(f"❌ Error recalculating product {product_id}: {str(e)}")
            self.stats['failed'] += 1
            self.stats['errors'].append(f"Product {product_id}: {str(e)}")
            return False

    def get_products_to_recalculate(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get products that need recalculation.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of products to recalculate
        """
        try:
            # Get products that have been processed before (have any score)
            query = self.supabase.table('products').select('id, name, barcode, final_score, display_score, nutri_score, additives_score, nova_score').not_.is_('final_score', 'null')

            if limit:
                query = query.limit(limit)

            result = query.execute()

            if hasattr(result, 'error') and result.error:
                print(f"❌ Error fetching products: {result.error}")
                return []

            products = result.data
            print(f"📊 Found {len(products)} products with existing scores")
            return products

        except Exception as e:
            print(f"❌ Error fetching products: {str(e)}")
            return []

    def recalculate_batch(self, batch_size: int = 10) -> None:
        """
        Recalculate scores for a batch of products.

        Args:
            batch_size: Number of products to process
        """
        print(f"\n🔄 BATCH RECALCULATION (batch size: {batch_size})")
        print(f"{'='*80}")

        products = self.get_products_to_recalculate(limit=batch_size)

        if not products:
            print("❌ No products found to recalculate")
            return

        print(f"📋 Processing {len(products)} products...")

        batch_ai_parsed_time = datetime.now().isoformat()
        self.processor.set_batch_ai_parsed_time(batch_ai_parsed_time)

        for i, product in enumerate(products, 1):
            product_id = product['id']
            product_name = product.get('name', 'Unknown')
            barcode = product.get('barcode', 'No barcode')

            print(f"\n[{i}/{len(products)}] Processing: {product_name}")
            print(f"  📋 ID: {product_id}")
            print(f"  🏷️  Barcode: {barcode}")

            success = self.recalculate_single_product(product_id, standalone=False)
            self.stats['processed'] += 1

            if not success:
                print(f"❌ Failed to recalculate product {product_id}")

        # Reset after batch run
        self.processor.set_batch_ai_parsed_time(None)

    def recalculate_all(self) -> None:
        """
        Recalculate scores for all products.
        """
        print(f"\n🔄 FULL RECALCULATION")
        print(f"{'='*80}")

        products = self.get_products_to_recalculate()

        if not products:
            print("❌ No products found to recalculate")
            return

        print(f"📋 Processing {len(products)} products...")

        batch_ai_parsed_time = datetime.now().isoformat()
        self.processor.set_batch_ai_parsed_time(batch_ai_parsed_time)

        for i, product in enumerate(products, 1):
            product_id = product['id']
            product_name = product.get('name', 'Unknown')
            barcode = product.get('barcode', 'No barcode')

            print(f"\n[{i}/{len(products)}] Processing: {product_name}")
            print(f"  📋 ID: {product_id}")
            print(f"  🏷️  Barcode: {barcode}")

            success = self.recalculate_single_product(product_id, standalone=False)
            self.stats['processed'] += 1

            if not success:
                print(f"❌ Failed to recalculate product {product_id}")

        # Reset after full run
        self.processor.set_batch_ai_parsed_time(None)

    def print_summary(self) -> None:
        """Print processing summary."""
        print(f"\n{'='*80}")
        print(f"📊 RECALCULATION SUMMARY")
        print(f"{'='*80}")
        print(f"✅ Successful: {self.stats['successful']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print(f"📊 Total processed: {self.stats['processed']}")

        if self.stats['errors']:
            print(f"\n❌ Errors encountered:")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more errors")

def main():
    parser = argparse.ArgumentParser(description='Recalculate all scoring values for products')
    parser.add_argument('--product-id', help='Product ID to recalculate')
    parser.add_argument('--batch', action='store_true', help='Recalculate a batch of products')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for batch processing')
    parser.add_argument('--all', action='store_true', help='Recalculate all products')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database updates)')

    args = parser.parse_args()

    if not any([args.product_id, args.batch, args.all]):
        parser.error("Must specify one of: --product-id, --batch, or --all")

    if args.dry_run:
        print("🔍 DRY RUN MODE: No database updates will be made")

    try:
        recalculator = ScoreRecalculator(dry_run=args.dry_run)

        if args.product_id:
            print(f"🔄 Recalculating single product: {args.product_id}")
            success = recalculator.recalculate_single_product(args.product_id)
            if success:
                print("✅ Recalculation completed successfully")
            else:
                print("❌ Recalculation failed")
                sys.exit(1)

        elif args.batch:
            print(f"🔄 Recalculating batch of {args.batch_size} products")
            recalculator.recalculate_batch(args.batch_size)

        elif args.all:
            print("🔄 Recalculating all products")
            recalculator.recalculate_all()

        recalculator.print_summary()

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
