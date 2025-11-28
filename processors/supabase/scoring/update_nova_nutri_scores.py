#!/usr/bin/env python3
"""
Script to calculate and update Nova scores and Nutri-Scores for products in Supabase.

This script:
1. Fetches all products from Supabase
2. Calculates Nova scores (food processing classification)
3. Calculates Nutri-Scores (nutritional quality)
4. Updates the database with the calculated scores
5. Provides detailed logging and error handling
6. Supports batch processing for large datasets

Usage:
    python update_nova_nutri_scores.py [--batch-size BATCH_SIZE] [--dry-run]
"""

import os
import sys
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from processors.scoring.types.nova_score import NovaScoreCalculator
from processors.scoring.types.nutri_score import NutriScoreCalculator

# Load environment variables
load_dotenv()

class SupabaseScoreUpdater:
    def __init__(self, batch_size: int = 50, dry_run: bool = False):
        """
        Initialize the Supabase score updater.
        
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
        
        # Initialize calculators
        self.nova_calculator = NovaScoreCalculator()
        self.nutri_calculator = NutriScoreCalculator()
        
        # Statistics
        self.stats = {
            'total_products': 0,
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'nova_api': 0,
            'nova_local': 0,
            'nutri_api': 0,
            'nutri_local': 0
        }
    
    def fetch_products(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch products from Supabase.
        
        Args:
            limit: Maximum number of products to fetch (None for all)
            
        Returns:
            List of product dictionaries
        """
        print("Fetching products from Supabase...")
        
        try:
            query = self.supabase.table('products').select('*')
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Error fetching products: {result.error}")
            
            products = result.data
            self.stats['total_products'] = len(products)
            print(f"Fetched {len(products)} products")
            return products
            
        except Exception as e:
            print(f"Error fetching products: {e}")
            raise
    
    def calculate_scores_for_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate Nova and Nutri-Scores for a single product.
        
        Args:
            product: Product dictionary from Supabase
            
        Returns:
            Dictionary with calculated scores and metadata
        """
        try:
            # Calculate Nova score
            nova_score, nova_source = self.nova_calculator.calculate(product)
            if nova_source == 'api':
                self.stats['nova_api'] += 1
            else:
                self.stats['nova_local'] += 1
            
            # Calculate Nutri-Score
            nutri_score, nutri_source = self.nutri_calculator.calculate(product)
            if nutri_source == 'api':
                self.stats['nutri_api'] += 1
            else:
                self.stats['nutri_local'] += 1
            
            return {
                'id': product['id'],
                'nova_score': nova_score,
                'nova_score_set_by': nova_source,
                'nutri_score': nutri_score,
                'nutri_score_set_by': nutri_source,
                'success': True
            }
            
        except Exception as e:
            print(f"Error calculating scores for product {product.get('name', 'Unknown')} (ID: {product.get('id', 'N/A')}): {e}")
            return {
                'id': product.get('id'),
                'nova_score': None,
                'nova_score_set_by': None,
                'nutri_score': None,
                'nutri_score_set_by': None,
                'success': False,
                'error': str(e)
            }
    
    def update_product_scores(self, score_data: Dict[str, Any]) -> bool:
        """
        Update a single product's scores in Supabase.
        
        Args:
            score_data: Dictionary with product ID and calculated scores
            
        Returns:
            True if successful, False otherwise
        """
        if not score_data['success']:
            return False
        
        try:
            update_data = {
                'nova_score': score_data['nova_score'],
                'nova_score_set_by': score_data['nova_score_set_by'],
                'nutri_score': score_data['nutri_score'],
                'nutri_score_set_by': score_data['nutri_score_set_by'],
                'updated_at': time.time()
            }
            
            if not self.dry_run:
                result = self.supabase.table('products').update(update_data).eq('id', score_data['id']).execute()
                
                if hasattr(result, 'error') and result.error:
                    print(f"Error updating product {score_data['id']}: {result.error}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error updating product {score_data['id']}: {e}")
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
            
            # Show nutritional info if available
            nutritional = product.get('nutritional', {})
            if nutritional and isinstance(nutritional, dict):
                print(f"  🥗 Nutritional info: {nutritional}")
            elif nutritional:
                print(f"  🥗 Nutritional info: {str(nutritional)[:100]}...")
            else:
                print(f"  🥗 No nutritional information available")
            
            # Show ingredients if available
            ingredients = product.get('ingredients', '')
            if ingredients:
                print(f"  📝 Ingredients: {str(ingredients)[:100]}...")
            else:
                print(f"  📝 No ingredients information available")
            
            # Calculate scores
            score_data = self.calculate_scores_for_product(product)
            
            # Print calculated scores
            if score_data['success']:
                print(f"  ✅ Nova Score: {score_data['nova_score']}/100 (source: {score_data['nova_score_set_by']})")
                print(f"  ✅ Nutri-Score: {score_data['nutri_score']}/100 (source: {score_data['nutri_score_set_by']})")
            else:
                print(f"  ❌ Error calculating scores: {score_data.get('error', 'Unknown error')}")
            
            # Update database
            if self.update_product_scores(score_data):
                self.stats['updated'] += 1
                print(f"  ✅ Database updated successfully")
            else:
                self.stats['errors'] += 1
                print(f"  ❌ Failed to update database")
            
            # Print progress summary
            if (i + 1) % 10 == 0 or i == len(products) - 1:
                print(f"\n  📊 Batch Progress: {i + 1}/{len(products)} products processed")
            
            # Add small delay to avoid overwhelming the API
            time.sleep(0.1)
    
    def run(self, limit: Optional[int] = None) -> None:
        """
        Run the complete score update process.
        
        Args:
            limit: Maximum number of products to process (None for all)
        """
        print("=" * 60)
        print("Nova Score and Nutri-Score Update Script")
        print("=" * 60)
        
        if self.dry_run:
            print("DRY RUN MODE - No database updates will be made")
        
        # Fetch products
        products = self.fetch_products(limit)
        
        if not products:
            print("No products found to process")
            return
        
        # Print initial product information
        print(f"\n📦 Found {len(products)} products to process")
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
            print(f"  Successfully updated: {sum(1 for p in batch_products if self.update_product_scores(self.calculate_scores_for_product(p)))}")
            print(f"  Nova API calls: {self.stats['nova_api']}")
            print(f"  Nutri API calls: {self.stats['nutri_api']}")
            
            # Add delay between batches
            if batch_num < total_batches - 1:
                print("⏳ Waiting 2 seconds before next batch...")
                time.sleep(2)
        
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
        print("Score Sources:")
        print(f"  Nova scores from API: {self.stats['nova_api']}")
        print(f"  Nova scores calculated locally: {self.stats['nova_local']}")
        print(f"  Nutri-Scores from API: {self.stats['nutri_api']}")
        print(f"  Nutri-Scores calculated locally: {self.stats['nutri_local']}")
        print("=" * 60)


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(
        description='Calculate and update Nova scores and Nutri-Scores for products in Supabase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all products with default batch size (50)
  python update_nova_nutri_scores.py
  
  # Update first 100 products with batch size of 25
  python update_nova_nutri_scores.py --limit 100 --batch-size 25
  
  # Dry run to see what would be updated without making changes
  python update_nova_nutri_scores.py --dry-run
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
        updater = SupabaseScoreUpdater(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        updater.run(limit=args.limit)
        
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 