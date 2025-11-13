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

from processors.scoring.product_scorer import ProductScorer

# Load environment variables
load_dotenv()

class SingleProductProcessor:
    def __init__(
        self,
        dry_run: bool = False,
        force_ai: bool = False,
        batch_ai_parsed_time: Optional[str] = None
    ):
        """
        Initialize the single product processor.

        Args:
            dry_run: If True, don't actually update the database
            force_ai: If True, force AI-based ingredient parsing
        """
        self.dry_run = dry_run
        self.force_ai = force_ai

        # Initialize Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")

        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Initialize unified product scorer (encapsulates all processing logic)
        self.scorer = ProductScorer(
            dry_run=dry_run,
            supabase_client=self.supabase,
            auto_insert_new_ingredients=True,
            auto_save_to_db=True
        )
        self.batch_ai_parsed_time: Optional[str] = None
        if batch_ai_parsed_time:
            self.set_batch_ai_parsed_time(batch_ai_parsed_time)

        # Statistics (mapped from scorer stats for backward compatibility)
        self.stats = {
            'product_found': False,
            'ingredients_parsed': False,
            'additives_fetched': False,
            'additives_relations_created': False,
            'scores_calculated': False,
            'database_updated': False,
            'errors': []
        }

    def set_batch_ai_parsed_time(self, ai_time: Optional[str]) -> None:
        """Set a shared ai_parsed_time to be used for batch processing."""
        self.batch_ai_parsed_time = ai_time
        self.scorer.batch_ai_parsed_time = ai_time

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

            # Check if product has ingredients (for display)
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

            if self.force_ai:
                print("   🤖 Force AI parsing is enabled for this run")

            # Use ProductScorer to parse ingredients
            parsing_result = self.scorer.parse_ingredients(product, force_ai=self.force_ai)

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

            # Show save status
            if not self.dry_run and parsing_result.get('matches'):
                print("   💾 Saving parsed ingredients to database...")
                print("   ✅ Parsed ingredients saved to database")
            elif self.dry_run:
                print("   🔄 DRY RUN: Would save parsed ingredients to database")

            self.stats['ingredients_parsed'] = True
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

            # Use ProductScorer to fetch additives
            success = self.scorer.fetch_additives(product)

            if success:
                additives_tags = product.get('additives_tags', [])
                if additives_tags:
                    print(f"   ✅ Found {len(additives_tags)} additives: {additives_tags}")
                else:
                    print("   ℹ️  No additives found for this product")

                if self.dry_run:
                    print(f"   🔄 DRY RUN: Would update additives_tags: {additives_tags}")

                self.stats['additives_fetched'] = True
                return True
            else:
                print(f"   ❌ Failed to fetch additives data")
                self.stats['errors'].extend(self.scorer.get_stats()['errors'][-1:])
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

            additives_tags = product.get('additives_tags', [])

            if not additives_tags:
                print("   ℹ️  No additives tags found, skipping relations creation")
                return True

            print(f"   🏷️  Creating relations for {len(additives_tags)} additives")

            # Use ProductScorer to create additives relations
            success = self.scorer.create_additives_relations(product)

            if success:
                # Get stats from relation manager for detailed output
                from processors.helpers.additives.additives_relation_manager import AdditivesRelationManager
                relation_manager = AdditivesRelationManager(dry_run=self.dry_run)
                product_id = product.get('id')
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

            # Use ProductScorer to calculate all scores
            scores = self.scorer.calculate_health_scores(product)

            # Print detailed results
            print(f"   🍎 Calculating NutriScore...")
            print(f"      NutriScore: {scores['nutri_score']} (source: {scores['nutri_source']})")

            print(f"   ⚠️  Calculating AdditivesScore...")
            if scores['additives_score'] is not None:
                # Get detailed additives info if available
                from processors.scoring.types.additives_score import AdditivesScoreCalculator
                additives_calc = AdditivesScoreCalculator()
                additives_result = additives_calc.calculate_from_product_additives(product_id)
                if additives_result:
                    additives_found = additives_result['additives_found']
                    risk_breakdown = additives_result['risk_breakdown']
                    print(f"      AdditivesScore: {scores['additives_score']}")
                    print(f"      Additives found: {additives_found}")
                    print(f"      Risk breakdown: {risk_breakdown}")
                else:
                    print("      AdditivesScore: Could not calculate (no relations or unknown risk levels)")
            else:
                print("      AdditivesScore: Not available")

            print(f"   🥗 Calculating NovaScore...")
            print(f"      NovaScore: {scores['nova_score']} (source: {scores['nova_source']})")

            # Calculate final health score
            print(f"   🏆 Calculating final health score...")

            # Check if ingredients were extracted but not all matched (for display)
            specs = product.get('specifications', {})
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except:
                    specs = {}

            parsed_ingredients = specs.get('parsed_ingredients', {})
            if isinstance(parsed_ingredients, dict):
                extracted_count = len(parsed_ingredients.get('extracted_ingredients', []))
                matches = parsed_ingredients.get('matches', []) or []

                visible_matches = []
                hidden_matches = []
                for match in matches:
                    data = match.get('data') or {}
                    if data.get('visible', True):
                        visible_matches.append(match)
                    else:
                        hidden_matches.append(match)

                matched_count = len(visible_matches)
                hidden_count = len(hidden_matches)

                if hidden_count > 0:
                    hidden_labels = []
                    for hidden in hidden_matches:
                        data = hidden.get('data') or {}
                        label = hidden.get('matched_name') or data.get('name') or data.get('name_ro') or 'unknown'
                        hidden_labels.append(label)
                    hidden_names = ", ".join(sorted(set(hidden_labels))) or "unknown"
                    print(f"      ⚠️  Ignoring {hidden_count} hidden ingredient(s) (visible = False): {hidden_names}")

                if extracted_count > 0:
                    match_ratio = matched_count / extracted_count if extracted_count else 0
                    if matched_count != extracted_count:
                        print(f"      ⚠️  Final Score: Cannot calculate - matched {matched_count}/{extracted_count} visible ingredients ({match_ratio:.0%})")
                        print("      ⚠️  All ingredients must be matched to ensure accurate scoring")
                        scores['final_score'] = None
                        scores['display_score'] = None
                    else:
                        print(f"      ✅ All extracted ingredients matched ({matched_count}/{extracted_count})")

                if scores['final_score'] is not None:
                    has_high_risk = scores.get('has_high_risk_additives', False)
                    print(f"      Final Score: {scores['final_score']}")
                    print(f"      Formula: ({scores['nutri_score']} × 0.4) + ({scores['additives_score']} × 0.3) + ({scores['nova_score']} × 0.3) = {scores['final_score']}")
                    if has_high_risk:
                        print("      ⚠️ High-risk additives detected; capping scores to 49")
                    if scores.get('display_score') is not None:
                        if has_high_risk:
                            print(f"      Display Score: {scores['display_score']} (capped at 49 due to high-risk additives)")
                        else:
                            print(f"      Display Score: {scores['display_score']}")
            else:
                print(f"      Final Score: Cannot calculate (missing individual scores)")

            self.stats['scores_calculated'] = True
            return scores

        except Exception as e:
            print(f"❌ Error calculating health scores: {str(e)}")
            self.stats['errors'].append(f"Health scoring error: {str(e)}")
            return {
                'nutri_score': None,
                'additives_score': None,
                'nova_score': None,
                'final_score': None,
                'display_score': None,
                'nutri_source': None,
                'nova_source': None
            }

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
                    if value is not None and key not in ['nutri_source', 'nova_source']:
                        print(f"      {key}: {value}")
                return True

            # Use ProductScorer to update database
            success = self.scorer.update_database(product_id, scores)

            if success:
                # Build update_data for display
                update_data = {
                    'updated_at': datetime.now().isoformat()
                }
                update_data['ai_parsed'] = self.scorer.last_parse_ai_generated
                if self.scorer.last_parse_ai_generated:
                    ai_time = (
                        self.scorer.last_ai_parsed_time_used
                        or self.batch_ai_parsed_time
                        or self.scorer.batch_ai_parsed_time
                        or datetime.now().isoformat()
                    )
                    update_data['ai_parsed_time'] = ai_time
                else:
                    update_data['ai_parsed_time'] = None
                if scores.get('final_score') is not None:
                    update_data['final_score'] = scores['final_score']
                    if scores.get('display_score') is not None:
                        update_data['display_score'] = scores['display_score']
                if scores.get('nutri_score') is not None:
                    update_data['nutri_score'] = scores['nutri_score']
                    update_data['nutri_score_set_by'] = scores.get('nutri_source', 'local')
                if scores.get('additives_score') is not None:
                    update_data['additives_score'] = scores['additives_score']
                    update_data['additives_score_set_by'] = 'local'
                if scores.get('nova_score') is not None:
                    update_data['nova_score'] = scores['nova_score']
                    update_data['nova_score_set_by'] = scores.get('nova_source', 'local')
                # Explicitly clear scores if they are None (e.g., extracted > matched)
                if scores.get('final_score') is None:
                    update_data['final_score'] = None
                    update_data['display_score'] = None
                elif scores.get('display_score') is not None:
                    update_data['display_score'] = scores['display_score']

                # Keep None values for fields we want to clear in the database
                update_data = {k: v for k, v in update_data.items() if v is not None or k in ['final_score', 'display_score', 'ai_parsed_time']}
                print(f"   📝 Updating with: {update_data}")
                print("   ✅ Database updated successfully")
                self.stats['database_updated'] = True
            else:
                print(f"   ❌ Database update failed")
                self.stats['errors'].extend(self.scorer.get_stats()['errors'][-1:])

            return success

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

    parser.add_argument(
        '--force-ai',
        action='store_true',
        help='Force AI ingredient parsing even when specifications exist'
    )

    args = parser.parse_args()

    try:
        processor = SingleProductProcessor(dry_run=args.dry_run, force_ai=args.force_ai)
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
