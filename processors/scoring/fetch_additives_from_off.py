#!/usr/bin/env python3
"""
Script to fetch additives_tags from Open Food Facts API and update Supabase products.

This script:
1. Fetches products from Supabase that have barcodes but no additives_tags
2. Calls Open Food Facts API for each product using the barcode
3. Extracts additives_tags from the API response
4. Updates the Supabase database with the additives_tags
5. Provides detailed logging and error handling
6. Supports batch processing for large datasets

Usage:
    python fetch_additives_from_off.py [--batch-size BATCH_SIZE] [--dry-run]
"""

import os
import sys
import time
import argparse
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

class OpenFoodFactsAdditivesFetcher:
    def __init__(self, batch_size: int = 50, dry_run: bool = False):
        """
        Initialize the Open Food Facts additives fetcher.

        Args:
            batch_size: Number of products to process in each batch
            dry_run: If True, don't actually update the database
        """
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Initialize Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")

        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Open Food Facts API base URL
        self.off_api_url = "https://world.openfoodfacts.org/api/v0/product"

        # Statistics
        self.stats = {
            'total_products': 0,
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'api_calls': 0,
            'found_additives': 0,
            'no_additives': 0,
            'api_errors': 0
        }

    def fetch_products_without_additives(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch products from Supabase that have barcodes but no additives_tags.

        Args:
            limit: Maximum number of products to fetch (None for all)

        Returns:
            List of product dictionaries
        """
        print("Fetching products from Supabase that need additives data...")

        try:
            all_products = []
            page_size = 1000  # Supabase default page size
            offset = 0

            print("Fetching all products with barcodes using pagination...")

            while True:
                # Query for products with barcodes, using pagination
                query = self.supabase.table('products').select('*').not_.is_('barcode', 'null').range(offset, offset + page_size - 1)

                if limit and len(all_products) >= limit:
                    break

                result = query.execute()

                if hasattr(result, 'error') and result.error:
                    raise Exception(f"Error fetching products: {result.error}")

                page_products = result.data

                if not page_products:  # No more products
                    break

                all_products.extend(page_products)
                print(f"Fetched {len(all_products)} products so far...")

                if len(page_products) < page_size:  # Last page
                    break

                offset += page_size

            products = all_products

            # Filter out products that already have additives_tags
            products_without_additives = []
            products_with_additives = 0
            products_null_additives = 0

            for product in products:
                additives_tags = product.get('additives_tags')
                barcode = product.get('barcode')

                # Skip products without barcodes
                if not barcode or str(barcode).strip() == '':
                    continue

                # Check if additives_tags is NULL, empty, or doesn't exist
                if additives_tags is None:
                    products_null_additives += 1
                    products_without_additives.append(product)
                elif isinstance(additives_tags, list) and len(additives_tags) == 0:
                    # Skip products with empty array - they've been processed and confirmed to have no additives
                    products_with_additives += 1
                elif not additives_tags:
                    products_without_additives.append(product)
                else:
                    products_with_additives += 1

            self.stats['total_products'] = len(products_without_additives)
            print(f"Total products with barcodes: {len(products)}")
            print(f"Products already processed (with additives or confirmed no additives): {products_with_additives}")
            print(f"Products with NULL additives: {products_null_additives}")
            print(f"Products needing additives: {len(products_without_additives)}")
            return products_without_additives

        except Exception as e:
            print(f"Error fetching products: {e}")
            raise

    def fetch_additives_from_off(self, barcode: str) -> Optional[List[str]]:
        """
        Fetch additives_tags from Open Food Facts API.

        Args:
            barcode: Product barcode

        Returns:
            List of additives tags or None if not found/error
        """
        try:
            url = f"{self.off_api_url}/{barcode}.json"

            # Configure headers to be more respectful to the API
            headers = {
                'User-Agent': 'FoodFacts-HealthScoring/1.0 (https://github.com/mmrshk/food_facts)',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            # Timeout set to 15 seconds for Open Food Facts API
            response = requests.get(url, headers=headers, timeout=15)
            self.stats['api_calls'] += 1

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
                print(f"  ⚠️  API returned status {response.status_code} for barcode {barcode}")
                return None

        except requests.exceptions.Timeout:
            print(f"  ⏰ Timeout for barcode {barcode}")
            self.stats['api_errors'] += 1
            return None
        except requests.exceptions.RequestException as e:
            print(f"  🌐 Network error for barcode {barcode}: {e}")
            self.stats['api_errors'] += 1
            return None
        except Exception as e:
            print(f"  ❌ Error fetching additives for barcode {barcode}: {e}")
            self.stats['api_errors'] += 1
            return None

    def update_product_additives(self, product_id: str, additives_tags: List[str]) -> bool:
        """
        Update a product's additives_tags in Supabase.

        Args:
            product_id: Product ID
            additives_tags: List of additives tags

        Returns:
            True if successful, False otherwise
        """
        try:
            update_data = {
                'additives_tags': additives_tags
            }

            if not self.dry_run:
                result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()

                if hasattr(result, 'error') and result.error:
                    print(f"  ❌ Error updating product {product_id}: {result.error}")
                    return False

            return True

        except Exception as e:
            print(f"  ❌ Error updating product {product_id}: {e}")
            return False

    def process_batch(self, products: List[Dict[str, Any]]) -> None:
        """
        Process a batch of products.

        Args:
            products: List of product dictionaries to process
        """
        print(f"\nProcessing batch of {len(products)} products...")

        for i, product in enumerate(products):
            self.stats['processed'] += 1

            # Print product info
            product_name = product.get('name', 'Unknown Product')
            product_id = product.get('id', 'N/A')
            barcode = product.get('barcode', 'No barcode')
            print(f"\n[{i + 1}] Processing: {product_name}")
            print(f"  📋 ID: {product_id} | Barcode: {barcode}")

            # Fetch additives from Open Food Facts
            print(f"  🔍 Fetching additives from Open Food Facts...")
            additives_tags = self.fetch_additives_from_off(barcode)

            if additives_tags is not None:
                if additives_tags:
                    print(f"  ✅ Found {len(additives_tags)} additives: {additives_tags}")
                    self.stats['found_additives'] += 1
                else:
                    print(f"  ℹ️  No additives found for this product")
                    self.stats['no_additives'] += 1

                # Update database
                if self.update_product_additives(product_id, additives_tags):
                    self.stats['updated'] += 1
                    print(f"  ✅ Database updated successfully")
                else:
                    self.stats['errors'] += 1
                    print(f"  ❌ Failed to update database")
            else:
                self.stats['errors'] += 1
                print(f"  ❌ Failed to fetch additives data")

            # Print progress summary
            if (i + 1) % 10 == 0 or i == len(products) - 1:
                print(f"\n  📊 Batch Progress: {i + 1}/{len(products)} products processed")

            # Add delay to avoid overwhelming the API
            time.sleep(1)  # 1 second delay between API calls

    def run(self, limit: Optional[int] = None) -> None:
        """
        Run the complete additives fetching process.

        Args:
            limit: Maximum number of products to process (None for all)
        """
        print("=" * 60)
        print("Open Food Facts Additives Fetcher")
        print("=" * 60)

        if self.dry_run:
            print("DRY RUN MODE - No database updates will be made")

        # Fetch products
        products = self.fetch_products_without_additives(limit)

        if not products:
            print("No products found that need additives data")
            return

        # Print initial product information
        print(f"\n📦 Found {len(products)} products without additives data")
        if len(products) <= 10:
            print("Products to be processed:")
            for i, product in enumerate(products, 1):
                name = product.get('name', 'Unknown Product')
                barcode = product.get('barcode', 'No barcode')
                print(f"  {i}. {name} (Barcode: {barcode})")
        else:
            print("First 5 products:")
            for i, product in enumerate(products[:5], 1):
                name = product.get('name', 'Unknown Product')
                barcode = product.get('barcode', 'No barcode')
                print(f"  {i}. {name} (Barcode: {barcode})")
            print(f"  ... and {len(products) - 5} more products")

        # Process in batches
        total_batches = (len(products) + self.batch_size - 1) // self.batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(products))
            batch_products = products[start_idx:end_idx]

            print(f"\nBatch {batch_num + 1}/{total_batches} ({start_idx + 1}-{end_idx} of {len(products)})")
            self.process_batch(batch_products)

            # Print batch summary
            print(f"\n📋 Batch {batch_num + 1} Summary:")
            print(f"  Products processed: {len(batch_products)}")
            print(f"  API calls made: {self.stats['api_calls']}")
            print(f"  Additives found: {self.stats['found_additives']}")
            print(f"  No additives: {self.stats['no_additives']}")
            print(f"  API errors: {self.stats['api_errors']}")

            # Add delay between batches
            if batch_num < total_batches - 1:
                print("⏳ Waiting 3 seconds before next batch...")
                time.sleep(3)

        # Print final statistics
        self.print_statistics()

    def print_statistics(self) -> None:
        """Print final statistics about the processing."""
        print("\n" + "=" * 60)
        print("PROCESSING STATISTICS")
        print("=" * 60)
        print(f"Total products: {self.stats['total_products']}")
        print(f"Processed: {self.stats['processed']}")
        print(f"Successfully updated: {self.stats['updated']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Success rate: {(self.stats['updated'] / self.stats['processed'] * 100):.1f}%" if self.stats['processed'] > 0 else "N/A")
        print()
        print("API Statistics:")
        print(f"  Total API calls: {self.stats['api_calls']}")
        print(f"  Products with additives found: {self.stats['found_additives']}")
        print(f"  Products with no additives: {self.stats['no_additives']}")
        print(f"  API errors: {self.stats['api_errors']}")
        print("=" * 60)


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(
        description='Fetch additives_tags from Open Food Facts API and update Supabase products',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch additives for all products with barcodes but no additives_tags
  python fetch_additives_from_off.py

  # Fetch additives for first 100 products with batch size of 25
  python fetch_additives_from_off.py --limit 100 --batch-size 25

  # Dry run to see what would be updated without making changes
  python fetch_additives_from_off.py --dry-run
        """
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Number of products to process in each batch (default: 50)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of products to process (default: all products)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without actually updating the database'
    )

    args = parser.parse_args()

    try:
        fetcher = OpenFoodFactsAdditivesFetcher(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        fetcher.run(limit=args.limit)

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()