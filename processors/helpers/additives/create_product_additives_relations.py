#!/usr/bin/env python3
"""
Script to create many-to-many relationships between products and additives.

This script:
1. Fetches all products from Supabase that have additives_tags
2. Fetches all additives from the additives table
3. Matches additives_tags (lowercase) with additives.code (uppercase)
4. Creates records in the product_additives junction table
"""

import os
import sys
import time
import argparse
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

class ProductAdditivesRelationCreator:
    def __init__(self, dry_run: bool = False):
        """
        Initialize the relation creator.
        
        Args:
            dry_run: If True, don't actually create relations, just simulate
        """
        self.dry_run = dry_run
        self.stats = {
            'products_processed': 0,
            'relations_created': 0,
            'additives_found': 0,
            'additives_not_found': 0,
            'errors': 0
        }
        
        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Cache for additives lookup
        self.additives_cache = {}
        
    def convert_lowercase_to_uppercase(self, lowercase: str) -> str:
        """
        Convert lowercase format to uppercase format.
        
        Examples:
        - "e968" -> "E968"
        - "e140ii" -> "E140ii"
        
        Args:
            lowercase: String in lowercase format
            
        Returns:
            String in uppercase format
        """
        if not lowercase:
            return lowercase
            
        # Remove leading/trailing whitespace and convert to uppercase
        cleaned = lowercase.strip()
        
        # Convert "e968" to "E968"
        if cleaned.startswith('e'):
            return 'E' + cleaned[1:].upper()
        
        return cleaned
    
    def fetch_all_additives(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all additives from the additives table and create a lookup cache.
        
        Returns:
            Dictionary mapping additive code to additive data
        """
        print("Fetching all additives from database...")
        
        try:
            result = self.supabase.table('additives').select('*').execute()
            
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Error fetching additives: {result.error}")
            
            additives = result.data
            additives_lookup = {}
            
            for additive in additives:
                code = additive.get('code')
                if code:
                    additives_lookup[code] = additive
                    # Also add lowercase version for case-insensitive matching
                    additives_lookup[code.lower()] = additive
            
            print(f"Loaded {len(additives)} additives into cache")
            return additives_lookup
            
        except Exception as e:
            print(f"Error fetching additives: {e}")
            raise
    
    def fetch_products_with_additives(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch products that have additives_tags from Supabase.
        
        Args:
            limit: Maximum number of products to fetch (None for all)
            
        Returns:
            List of product dictionaries
        """
        print("Fetching products with additives_tags from Supabase...")
        
        try:
            all_products = []
            page_size = 1000  # Supabase default page size
            offset = 0
            
            while True:
                # Query for products with additives_tags (not null and not empty)
                query = self.supabase.table('products').select('*').not_.is_('additives_tags', 'null')
                
                if limit and len(all_products) >= limit:
                    break
                
                query = query.range(offset, offset + page_size - 1)
                result = query.execute()
                
                if hasattr(result, 'error') and result.error:
                    raise Exception(f"Error fetching products: {result.error}")
                
                page_products = result.data
                
                if not page_products:  # No more products
                    break
                
                # Filter out products with empty additives_tags
                for product in page_products:
                    additives_tags = product.get('additives_tags')
                    if additives_tags and isinstance(additives_tags, list) and len(additives_tags) > 0:
                        all_products.append(product)
                
                print(f"Fetched {len(all_products)} products with additives so far...")
                
                if len(page_products) < page_size:  # Last page
                    break
                
                offset += page_size
            
            print(f"Total products with additives: {len(all_products)}")
            return all_products
            
        except Exception as e:
            print(f"Error fetching products: {e}")
            raise
    
    def find_additive_by_tag(self, tag: str, additives_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find an additive by its tag, trying different matching strategies.
        
        Args:
            tag: The additive tag from additives_tags
            additives_lookup: Dictionary of additives by code
            
        Returns:
            Additive data if found, None otherwise
        """
        # Try exact match first
        if tag in additives_lookup:
            return additives_lookup[tag]
        
        # Try converting from lowercase to uppercase
        uppercase_tag = self.convert_lowercase_to_uppercase(tag)
        if uppercase_tag in additives_lookup:
            return additives_lookup[uppercase_tag]
        
        # Try lowercase match
        if tag.lower() in additives_lookup:
            return additives_lookup[tag.lower()]
        
        # Try removing common prefixes
        clean_tag = tag
        for prefix in ['en:', 'additive_', 'additive']:
            if clean_tag.startswith(prefix):
                clean_tag = clean_tag[len(prefix):]
                break
        
        if clean_tag in additives_lookup:
            return additives_lookup[clean_tag]
        
        # Try converting clean tag to uppercase
        clean_uppercase = self.convert_lowercase_to_uppercase(clean_tag)
        if clean_uppercase in additives_lookup:
            return additives_lookup[clean_uppercase]
        
        return None
    
    def create_product_additive_relation(self, product_id: str, additive_id: str) -> bool:
        """
        Create a relation between product and additive in the product_additives table.
        
        Args:
            product_id: Product ID
            additive_id: Additive ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if relation already exists
            existing = self.supabase.table('product_additives').select('*').eq('product_id', product_id).eq('additive_id', additive_id).execute()
            
            if existing.data:
                # Relation already exists, skip
                return True
            
            if not self.dry_run:
                relation_data = {
                    'product_id': product_id,
                    'additive_id': additive_id,
                }
                
                result = self.supabase.table('product_additives').insert(relation_data).execute()
                
                if hasattr(result, 'error') and result.error:
                    print(f"  ❌ Error creating relation: {result.error}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error creating relation: {e}")
            return False
    
    def process_product(self, product: Dict[str, Any], additives_lookup: Dict[str, Dict[str, Any]]) -> None:
        """
        Process a single product and create relations for its additives.
        
        Args:
            product: Product data
            additives_lookup: Dictionary of additives by code
        """
        product_id = product.get('id')
        product_name = product.get('name', 'Unknown Product')
        additives_tags = product.get('additives_tags', [])
        
        print(f"\nProcessing product: {product_name}")
        print(f"  📋 ID: {product_id}")
        print(f"  🏷️  Additives tags: {additives_tags}")
        
        relations_created = 0
        additives_found = 0
        additives_not_found = 0
        
        for tag in additives_tags:
            additive = self.find_additive_by_tag(tag, additives_lookup)
            
            if additive:
                additive_id = additive.get('id')
                additive_code = additive.get('code')
                additive_name = additive.get('name', 'Unknown')
                
                print(f"    ✅ Found additive: {additive_code} - {additive_name}")
                additives_found += 1
                
                if self.create_product_additive_relation(product_id, additive_id):
                    relations_created += 1
                    print(f"      ✅ Relation created")
                else:
                    print(f"      ❌ Failed to create relation")
            else:
                print(f"    ❌ Additive not found: {tag}")
                additives_not_found += 1
        
        # Update statistics
        self.stats['products_processed'] += 1
        self.stats['relations_created'] += relations_created
        self.stats['additives_found'] += additives_found
        self.stats['additives_not_found'] += additives_not_found
        
        print(f"  📊 Product summary: {relations_created} relations created, {additives_found} found, {additives_not_found} not found")
    
    def run(self, limit: Optional[int] = None) -> None:
        """
        Run the complete relation creation process.
        
        Args:
            limit: Maximum number of products to process (None for all)
        """
        print("🚀 Starting product-additives relation creation...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        
        try:
            # Step 1: Fetch all additives
            additives_lookup = self.fetch_all_additives()
            
            # Step 2: Fetch products with additives
            products = self.fetch_products_with_additives(limit)
            
            if not products:
                print("No products with additives found!")
                return
            
            # Step 3: Process each product
            print(f"\nProcessing {len(products)} products...")
            
            for i, product in enumerate(products):
                print(f"\n{'='*60}")
                print(f"Product {i + 1}/{len(products)}")
                
                self.process_product(product, additives_lookup)
                
                # Add small delay to avoid overwhelming the database
                time.sleep(0.1)
            
            # Step 4: Print final statistics
            self.print_statistics()
            
        except Exception as e:
            print(f"❌ Error during processing: {e}")
            raise
    
    def print_statistics(self) -> None:
        """Print final statistics."""
        print(f"\n{'='*60}")
        print("📊 FINAL STATISTICS")
        print(f"{'='*60}")
        print(f"Products processed: {self.stats['products_processed']}")
        print(f"Relations created: {self.stats['relations_created']}")
        print(f"Additives found: {self.stats['additives_found']}")
        print(f"Additives not found: {self.stats['additives_not_found']}")
        print(f"Errors: {self.stats['errors']}")
        
        if self.stats['additives_not_found'] > 0:
            print(f"\n⚠️  Note: {self.stats['additives_not_found']} additives were not found in the database.")
            print("This could be due to:")
            print("- Different naming conventions between additives_tags and additives.code")
            print("- Missing additives in the additives table")
            print("- Format differences (underscored vs camelCase)")


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Create product-additives relations')
    parser.add_argument('--limit', type=int, help='Maximum number of products to process')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no database changes)')
    
    args = parser.parse_args()
    
    try:
        creator = ProductAdditivesRelationCreator(dry_run=args.dry_run)
        creator.run(limit=args.limit)
        
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 