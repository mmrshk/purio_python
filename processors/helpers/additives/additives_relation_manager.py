#!/usr/bin/env python3
"""
Reusable class for managing additives relations between products and additives.

This class can be used in the main processing flow to create relations
when products are saved to the database.
"""

import os
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

class AdditivesRelationManager:
    def __init__(self, dry_run: bool = False):
        """
        Initialize the additives relation manager.
        
        Args:
            dry_run: If True, don't actually create relations, just simulate
        """
        self.dry_run = dry_run
        self.stats = {
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
        self.additives_lookup = {}
        self._load_additives_cache()
    
    def _load_additives_cache(self) -> None:
        """Load all additives into cache for fast lookup."""
        try:
            result = self.supabase.table('additives').select('*').execute()
            
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Error fetching additives: {result.error}")
            
            additives = result.data
            
            for additive in additives:
                code = additive.get('code')
                if code:
                    self.additives_lookup[code] = additive
                    # Also add lowercase version for case-insensitive matching
                    self.additives_lookup[code.lower()] = additive
            
            print(f"Loaded {len(additives)} additives into cache")
            
        except Exception as e:
            print(f"Error loading additives cache: {e}")
            raise
    
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
    
    def find_additive_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """
        Find an additive by its tag, trying different matching strategies.
        
        Args:
            tag: The additive tag from additives_tags
            
        Returns:
            Additive data if found, None otherwise
        """
        # Try exact match first
        if tag in self.additives_lookup:
            return self.additives_lookup[tag]
        
        # Try converting from lowercase to uppercase
        uppercase_tag = self.convert_lowercase_to_uppercase(tag)
        if uppercase_tag in self.additives_lookup:
            return self.additives_lookup[uppercase_tag]
        
        # Try lowercase match
        if tag.lower() in self.additives_lookup:
            return self.additives_lookup[tag.lower()]
        
        # Try removing common prefixes
        clean_tag = tag
        for prefix in ['en:', 'additive_', 'additive']:
            if clean_tag.startswith(prefix):
                clean_tag = clean_tag[len(prefix):]
                break
        
        if clean_tag in self.additives_lookup:
            return self.additives_lookup[clean_tag]
        
        # Try converting clean tag to uppercase
        clean_uppercase = self.convert_lowercase_to_uppercase(clean_tag)
        if clean_uppercase in self.additives_lookup:
            return self.additives_lookup[clean_uppercase]
        
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
                    'additive_id': additive_id
                }
                
                result = self.supabase.table('product_additives').insert(relation_data).execute()
                
                if hasattr(result, 'error') and result.error:
                    print(f"  ❌ Error creating relation: {result.error}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error creating relation: {e}")
            return False
    
    def create_relations_for_product(self, product_id: str, additives_tags: List[str], product_name: str = "Unknown Product") -> Dict[str, int]:
        """
        Create relations for a single product based on its additives_tags.
        
        Args:
            product_id: Product ID
            additives_tags: List of additive tags
            product_name: Product name for logging
            
        Returns:
            Dictionary with statistics: {'relations_created', 'additives_found', 'additives_not_found'}
        """
        if not additives_tags or not isinstance(additives_tags, list):
            return {'relations_created': 0, 'additives_found': 0, 'additives_not_found': 0}
        
        relations_created = 0
        additives_found = 0
        additives_not_found = 0
        
        print(f"  🏷️  Creating relations for {product_name} (ID: {product_id})")
        print(f"  📋 Additives tags: {additives_tags}")
        
        for tag in additives_tags:
            additive = self.find_additive_by_tag(tag)
            
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
        
        # Update global statistics
        self.stats['relations_created'] += relations_created
        self.stats['additives_found'] += additives_found
        self.stats['additives_not_found'] += additives_not_found
        
        print(f"  📊 Product summary: {relations_created} relations created, {additives_found} found, {additives_not_found} not found")
        
        return {
            'relations_created': relations_created,
            'additives_found': additives_found,
            'additives_not_found': additives_not_found
        }
    
    def get_statistics(self) -> Dict[str, int]:
        """Get current statistics."""
        return self.stats.copy()
    
    def print_statistics(self) -> None:
        """Print current statistics."""
        print(f"\n{'='*60}")
        print("📊 ADDITIVES RELATIONS STATISTICS")
        print(f"{'='*60}")
        print(f"Relations created: {self.stats['relations_created']}")
        print(f"Additives found: {self.stats['additives_found']}")
        print(f"Additives not found: {self.stats['additives_not_found']}")
        print(f"Errors: {self.stats['errors']}")
        
        if self.stats['additives_not_found'] > 0:
            print(f"\n⚠️  Note: {self.stats['additives_not_found']} additives were not found in the database.")
            print("This could be due to:")
            print("- Different naming conventions between additives_tags and additives.code")
            print("- Missing additives in the additives table")
            print("- Format differences (lowercase vs uppercase)") 