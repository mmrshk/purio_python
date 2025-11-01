#!/usr/bin/env python3
"""
Script to process a single product by ID through the complete pipeline:
- Ingredients parsing
- Additives checking and fetching
- Health scoring (Nova, Nutri, Additives, Final)

Usage:
    python process_single_product.py <product_id> [--dry-run]
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from processors.scoring.types.nutri_score import NutriScoreCalculator
from processors.scoring.types.additives_score import AdditivesScoreCalculator
from processors.scoring.types.nova_score import NovaScoreCalculator
from processors.scoring.fetch_additives_from_off import OpenFoodFactsAdditivesFetcher
from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker

# Load environment variables
load_dotenv()

class SingleProductProcessor:
    def __init__(self, dry_run: bool = False):
        """
        Initialize the single product processor.
        
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
        
        # Initialize calculators
        self.nutri_calc = NutriScoreCalculator()
        self.additives_calc = AdditivesScoreCalculator()
        self.nova_calc = NovaScoreCalculator()
        self.ingredients_checker = SupabaseIngredientsChecker(auto_insert_new_ingredients=True)
        self.additives_fetcher = OpenFoodFactsAdditivesFetcher(dry_run=dry_run)
        
        # Statistics
        self.stats = {
            'product_found': False,
            'ingredients_parsed': False,
            'additives_fetched': False,
            'additives_relations_created': False,
            'scores_calculated': False,
            'database_updated': False,
            'errors': []
        }
    
    def _check_product_high_risk_additives(self, product_id: str) -> bool:
        """
        Check if a product has high-risk additives using relations in the database.
        """
        try:
            # Get additive relations for product
            rel_result = self.supabase.table('product_additives_relations').select('additive_id').eq('product_id', product_id).execute()
            if hasattr(rel_result, 'error') and rel_result.error:
                return False
            additive_ids = [rel.get('additive_id') for rel in rel_result.data]
            if not additive_ids:
                return False
            # Check if any additives are marked high risk
            hr_result = self.supabase.table('additives').select('id').in_('id', additive_ids).eq('is_high_risk', True).execute()
            if hasattr(hr_result, 'error') and hr_result.error:
                return False
            return len(hr_result.data) > 0
        except Exception:
            return False

    def fetch_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single product from Supabase by ID.
        
        Args:
            product_id: Product ID to fetch
            
        Returns:
            Product data or None if not found
        """
        try:
            print(f"🔍 Fetching product with ID: {product_id}")
            
            result = self.supabase.table('products').select('*').eq('id', product_id).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"❌ Error fetching product: {result.error}")
                self.stats['errors'].append(f"Database error: {result.error}")
                return None
            
            products = result.data
            
            if not products:
                print(f"❌ Product with ID {product_id} not found")
                self.stats['errors'].append(f"Product not found: {product_id}")
                return None
            
            product = products[0]
            product_name = product.get('name', 'Unknown Product')
            barcode = product.get('barcode', 'No barcode')
            
            print(f"✅ Found product: {product_name}")
            print(f"   📋 ID: {product_id}")
            print(f"   🏷️  Barcode: {barcode}")
            
            self.stats['product_found'] = True
            return product
            
        except Exception as e:
            print(f"❌ Error fetching product: {str(e)}")
            self.stats['errors'].append(f"Fetch error: {str(e)}")
            return None
    
    def parse_ingredients(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse ingredients for the product.
        
        Args:
            product: Product data
            
        Returns:
            Ingredients parsing results
        """
        try:
            print(f"\n🧪 Parsing ingredients...")
            
            # Check if product has ingredients
            specs = product.get('specifications', {})
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except:
                    specs = {}
            
            ingredients_text = specs.get('ingredients', '')
            if not ingredients_text:
                print("   ℹ️  No ingredients found in product (will try AI via checker)")
            else:
                print(f"   📋 Ingredients text: {ingredients_text[:100]}{'...' if len(ingredients_text) > 100 else ''}")
            
            # Parse ingredients using the checker (will use AI if needed)
            parsing_result = self.ingredients_checker.check_product_ingredients(product)
            
            extracted_ingredients = parsing_result.get('extracted_ingredients', [])
            matches = parsing_result.get('matches', [])
            nova_scores = parsing_result.get('nova_scores', [])
            
            print(f"   ✅ Extracted {len(extracted_ingredients)} ingredients")
            print(f"   🎯 Matched {len(matches)} ingredients")
            
            if matches:
                print(f"   📊 NOVA scores distribution:")
                nova_counts = {1: 0, 2: 0, 3: 0, 4: 0}
                for score in nova_scores:
                    if score in nova_counts:
                        nova_counts[score] += 1
                
                for nova_group, count in nova_counts.items():
                    if count > 0:
                        group_names = {1: 'Unprocessed', 2: 'Culinary', 3: 'Processed', 4: 'Ultra-processed'}
                        print(f"      NOVA {nova_group} ({group_names[nova_group]}): {count}")
            
            self.stats['ingredients_parsed'] = True
            
            # Prepare parsed_ingredients data
            parsed_ingredients_data = {
                'extracted_ingredients': parsing_result.get('extracted_ingredients', []),
                'matches': parsing_result.get('matches', []),
                'nova_scores': parsing_result.get('nova_scores', []),
                'ai_generated': bool(parsing_result.get('ai_generated', False)),
                'source': parsing_result.get('source', 'unknown')
            }
            
            # Update product object with parsed_ingredients (for use in calculate_health_scores)
            current_specs = product.get('specifications', {})
            if isinstance(current_specs, str):
                try:
                    current_specs = json.loads(current_specs)
                except:
                    current_specs = {}
            
            current_specs['parsed_ingredients'] = parsed_ingredients_data
            product['specifications'] = current_specs
            
            # Save parsed ingredients to database if not in dry run mode
            if not self.dry_run and parsing_result.get('matches'):
                try:
                    # Update the product in database
                    update_data = {
                        'specifications': current_specs,
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    print(f"   💾 Saving parsed ingredients to database...")
                    result = self.supabase.table('products').update(update_data).eq('id', product.get('id')).execute()
                    
                    if hasattr(result, 'error') and result.error:
                        print(f"   ❌ Failed to save parsed ingredients: {result.error}")
                        self.stats['errors'].append(f"Parsed ingredients save error: {result.error}")
                    else:
                        print(f"   ✅ Parsed ingredients saved to database")
                except Exception as e:
                    print(f"   ❌ Error saving parsed ingredients: {str(e)}")
                    self.stats['errors'].append(f"Parsed ingredients save error: {str(e)}")
            elif self.dry_run:
                print(f"   🔄 DRY RUN: Would save parsed ingredients to database")
            
            return parsing_result
            
        except Exception as e:
            print(f"❌ Error parsing ingredients: {str(e)}")
            self.stats['errors'].append(f"Ingredients parsing error: {str(e)}")
            return {}
    
    def fetch_additives(self, product: Dict[str, Any]) -> bool:
        """
        Fetch additives from Open Food Facts for the product.
        
        Args:
            product: Product data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n🔬 Fetching additives from Open Food Facts...")
            
            barcode = product.get('barcode')
            if not barcode:
                print("   ⚠️  No barcode found, cannot fetch additives")
                return False
            
            print(f"   🏷️  Using barcode: {barcode}")
            
            # Fetch additives using the existing fetcher
            additives_tags = self.additives_fetcher.fetch_additives_from_off(barcode)
            
            if additives_tags is not None:
                if additives_tags:
                    print(f"   ✅ Found {len(additives_tags)} additives: {additives_tags}")
                else:
                    print(f"   ℹ️  No additives found for this product")
                
                # Update the product object with additives_tags (for both dry run and normal mode)
                product['additives_tags'] = additives_tags
                
                # Update the database if not in dry run mode
                if not self.dry_run:
                    update_data = {'additives_tags': additives_tags}
                    result = self.supabase.table('products').update(update_data).eq('id', product.get('id')).execute()
                    
                    if hasattr(result, 'error') and result.error:
                        print(f"   ❌ Error updating additives_tags: {result.error}")
                        self.stats['errors'].append(f"Additives update error: {result.error}")
                        return False
                    else:
                        print(f"   ✅ Updated additives_tags in database")
                        self.stats['additives_fetched'] = True
                        return True
                else:
                    print(f"   🔄 DRY RUN: Would update additives_tags: {additives_tags}")
                    self.stats['additives_fetched'] = True
                    return True
            else:
                print(f"   ❌ Failed to fetch additives data")
                self.stats['errors'].append("Failed to fetch additives from Open Food Facts")
                return False
                
        except Exception as e:
            print(f"❌ Error fetching additives: {str(e)}")
            self.stats['errors'].append(f"Additives fetching error: {str(e)}")
            return False
    
    def create_additives_relations(self, product: Dict[str, Any]) -> bool:
        """
        Create relations between product and additives in the database.
        
        Args:
            product: Product data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n🔗 Creating additives relations...")
            
            product_id = product.get('id')
            additives_tags = product.get('additives_tags', [])
            
            if not additives_tags:
                print("   ℹ️  No additives tags found, skipping relations creation")
                return True
            
            print(f"   🏷️  Creating relations for {len(additives_tags)} additives")
            
            # Import the relation manager
            from processors.helpers.additives.additives_relation_manager import AdditivesRelationManager
            
            relation_manager = AdditivesRelationManager(dry_run=self.dry_run)
            
            # Create relations for the product
            stats = relation_manager.create_relations_for_product(
                product_id, 
                additives_tags, 
                product.get('name', 'Unknown Product')
            )
            
            print(f"   📊 Relations created: {stats['relations_created']}")
            print(f"   ✅ Additives found: {stats['additives_found']}")
            print(f"   ❌ Additives not found: {stats['additives_not_found']}")
            
            self.stats['additives_relations_created'] = True
            return True
            
        except Exception as e:
            print(f"❌ Error creating additives relations: {str(e)}")
            self.stats['errors'].append(f"Additives relations error: {str(e)}")
            return False
    
    def calculate_health_scores(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate all health scores for the product.
        
        Args:
            product: Product data
            
        Returns:
            Dictionary with all calculated scores
        """
        try:
            print(f"\n📊 Calculating health scores...")
            
            product_id = product.get('id')
            product_name = product.get('name', 'Unknown Product')
            
            scores = {
                'nutri_score': None,
                'additives_score': None,
                'nova_score': None,
                'final_score': None,
                'nutri_source': None,
                'nova_source': None
            }
            
            # Calculate NutriScore
            print(f"   🍎 Calculating NutriScore...")
            nutri_result = self.nutri_calc.calculate(product)
            if isinstance(nutri_result, tuple):
                scores['nutri_score'], scores['nutri_source'] = nutri_result
            else:
                scores['nutri_score'], scores['nutri_source'] = nutri_result, 'unknown'
            
            print(f"      NutriScore: {scores['nutri_score']} (source: {scores['nutri_source']})")
            
            # Calculate AdditivesScore
            print(f"   ⚠️  Calculating AdditivesScore...")
            additives_result = self.additives_calc.calculate_from_product_additives(product_id)
            if additives_result:
                scores['additives_score'] = additives_result['score']
                additives_found = additives_result['additives_found']
                risk_breakdown = additives_result['risk_breakdown']
                
                print(f"      AdditivesScore: {scores['additives_score']}")
                print(f"      Additives found: {additives_found}")
                print(f"      Risk breakdown: {risk_breakdown}")
            else:
                print(f"      AdditivesScore: Could not calculate (no relations or unknown risk levels)")
            
            # Calculate NovaScore
            print(f"   🥗 Calculating NovaScore...")
            nova_result = self.nova_calc.calculate(product)
            if isinstance(nova_result, tuple):
                scores['nova_score'], scores['nova_source'] = nova_result
            else:
                scores['nova_score'], scores['nova_source'] = nova_result, 'unknown'
            
            print(f"      NovaScore: {scores['nova_score']} (source: {scores['nova_source']})")
            
            # Calculate final health score
            print(f"   🏆 Calculating final health score...")
            
            # Check if ingredients were extracted but not all matched
            specs = product.get('specifications', {})
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except:
                    specs = {}
            
            parsed_ingredients = specs.get('parsed_ingredients', {})
            if isinstance(parsed_ingredients, dict):
                extracted_count = len(parsed_ingredients.get('extracted_ingredients', []))
                matched_count = len(parsed_ingredients.get('matches', []))
                
                if extracted_count > 0 and extracted_count > matched_count:
                    print(f"      ⚠️  Final Score: Cannot calculate - {extracted_count} ingredients extracted but only {matched_count} matched")
                    print(f"      ⚠️  Missing ingredient data would make score inaccurate")
                    scores['final_score'] = None
                    self.stats['scores_calculated'] = True
                    return scores
            
            final_score = self.calculate_final_health_score(
                scores['nutri_score'], 
                scores['additives_score'], 
                scores['nova_score']
            )
            scores['final_score'] = final_score
            
            if final_score is not None:
                print(f"      Final Score: {final_score}")
                print(f"      Formula: ({scores['nutri_score']} × 0.4) + ({scores['additives_score']} × 0.3) + ({scores['nova_score']} × 0.3) = {final_score}")
            else:
                print(f"      Final Score: Cannot calculate (missing individual scores)")
            
            self.stats['scores_calculated'] = True
            return scores
            
        except Exception as e:
            print(f"❌ Error calculating health scores: {str(e)}")
            self.stats['errors'].append(f"Health scoring error: {str(e)}")
            return {}
    
    def calculate_final_health_score(self, nutri, additives, nova):
        """Calculate final health score from individual scores."""
        if nutri is None or additives is None or nova is None:
            return None
        return int(round(nutri * 0.4 + additives * 0.3 + nova * 0.3))
    
    def update_database(self, product_id: str, scores: Dict[str, Any]) -> bool:
        """
        Update the database with calculated scores.
        
        Args:
            product_id: Product ID
            scores: Dictionary with calculated scores
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n💾 Updating database with scores...")
            
            if self.dry_run:
                print(f"   🔄 DRY RUN: Would update database with:")
                for key, value in scores.items():
                    if value is not None:
                        print(f"      {key}: {value}")
                return True
            
            update_data = {
                'updated_at': datetime.now().isoformat()
            }
            
            # Add scores to update data
            if scores.get('final_score') is not None:
                update_data['final_score'] = scores['final_score']

                has_high_risk = self._check_product_high_risk_additives(product_id)
                display_score = min(scores['final_score'], 49) if has_high_risk else scores['final_score']
                update_data['display_score'] = display_score
            if scores.get('nutri_score') is not None:
                update_data['nutri_score'] = scores['nutri_score']
                update_data['nutri_score_set_by'] = scores.get('nutri_source', 'local')
            if scores.get('additives_score') is not None:
                update_data['additives_score'] = scores['additives_score']
                update_data['additives_score_set_by'] = 'local'
            if scores.get('nova_score') is not None:
                update_data['nova_score'] = scores['nova_score']
                update_data['nova_score_set_by'] = scores.get('nova_source', 'local')
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            print(f"   📝 Updating with: {update_data}")
            
            result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"   ❌ Database update failed: {result.error}")
                self.stats['errors'].append(f"Database update error: {result.error}")
                return False
            else:
                print(f"   ✅ Database updated successfully")
                self.stats['database_updated'] = True
                return True
                
        except Exception as e:
            print(f"❌ Error updating database: {str(e)}")
            self.stats['errors'].append(f"Database update error: {str(e)}")
            return False
    
    def process_product(self, product_id: str) -> bool:
        """
        Process a single product through the complete pipeline.
        
        Args:
            product_id: Product ID to process
            
        Returns:
            True if successful, False otherwise
        """
        print("=" * 80)
        print(f"PROCESSING SINGLE PRODUCT: {product_id}")
        print("=" * 80)
        
        if self.dry_run:
            print("🔄 DRY RUN MODE - No database updates will be made")
        
        # Step 1: Fetch product
        product = self.fetch_product(product_id)
        if not product:
            return False
        
        # Step 2: Parse ingredients
        ingredients_result = self.parse_ingredients(product)
        
        # Step 3: Fetch additives
        additives_fetched = self.fetch_additives(product)
        
        # Step 4: Create additives relations (if additives were fetched)
        if additives_fetched:
            self.create_additives_relations(product)
        
        # Step 5: Calculate health scores
        scores = self.calculate_health_scores(product)
        
        # Step 6: Update database
        if scores:
            self.update_database(product_id, scores)
        
        # Print summary
        self.print_summary()
        
        return len(self.stats['errors']) == 0
    
    def print_summary(self):
        """Print processing summary."""
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        
        print(f"✅ Product found: {self.stats['product_found']}")
        print(f"✅ Ingredients parsed: {self.stats['ingredients_parsed']}")
        print(f"✅ Additives fetched: {self.stats['additives_fetched']}")
        print(f"✅ Additives relations created: {self.stats['additives_relations_created']}")
        print(f"✅ Scores calculated: {self.stats['scores_calculated']}")
        print(f"✅ Database updated: {self.stats['database_updated']}")
        
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
        description='Process a single product through the complete pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process product with ID 'abc123'
  python process_single_product.py abc123
  
  # Dry run to see what would be done
  python process_single_product.py abc123 --dry-run
        """
    )
    
    parser.add_argument(
        'product_id',
        help='Product ID to process'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without actually updating the database'
    )
    
    args = parser.parse_args()
    
    try:
        processor = SingleProductProcessor(dry_run=args.dry_run)
        success = processor.process_product(args.product_id)
        
        if success:
            print(f"\n✅ Product {args.product_id} processed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Product {args.product_id} processing failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
