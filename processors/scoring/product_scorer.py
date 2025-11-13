#!/usr/bin/env python3
"""
Unified Product Scorer for processing products through the complete pipeline.

This class provides reusable logic for:
- Ingredients parsing (with AI fallback)
- Additives fetching and relations
- Health score calculation (Nutri, Additives, NOVA, Final, Display)
- Database updates

Can be used by both single product processing and batch processing.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
import sys
sys.path.insert(0, project_root)

from processors.scoring.types.nutri_score import NutriScoreCalculator
from processors.scoring.types.additives_score import AdditivesScoreCalculator
from processors.scoring.types.nova_score import NovaScoreCalculator
from processors.scoring.fetch_additives_from_off import OpenFoodFactsAdditivesFetcher
from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker

load_dotenv()


class ProductScorer:
    """
    Unified scorer for processing products through the complete pipeline.

    This class encapsulates all logic for ingredient parsing, additives fetching,
    and health score calculation, making it reusable for both single product
    and batch processing scenarios.
    """

    def __init__(
        self,
        dry_run: bool = False,
        supabase_client=None,
        auto_insert_new_ingredients: bool = True,
        auto_save_to_db: bool = True
    ):
        """
        Initialize the product scorer.

        Args:
            dry_run: If True, don't actually update the database
            supabase_client: Optional Supabase client (will create if not provided)
            auto_insert_new_ingredients: Whether to auto-insert unmatched AI ingredients
            auto_save_to_db: Whether to automatically save parsed ingredients and additives to DB
        """
        self.dry_run = dry_run
        self.auto_save_to_db = auto_save_to_db

        # Initialize Supabase client if needed
        if supabase_client is None and auto_save_to_db:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not supabase_url or not supabase_key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
            self.supabase = create_client(supabase_url, supabase_key)
        else:
            self.supabase = supabase_client

        # Initialize calculators and checkers
        self.nutri_calc = NutriScoreCalculator()
        self.additives_calc = AdditivesScoreCalculator()
        self.nova_calc = NovaScoreCalculator()
        self.ingredients_checker = SupabaseIngredientsChecker(
            auto_insert_new_ingredients=auto_insert_new_ingredients
        )
        self.additives_fetcher = OpenFoodFactsAdditivesFetcher(dry_run=dry_run)
        self.last_parse_ai_generated: bool = False
        self.batch_ai_parsed_time: Optional[str] = None
        self.last_ai_parsed_time_used: Optional[str] = None

        # Statistics tracking
        self.stats = {
            'products_processed': 0,
            'ingredients_parsed': 0,
            'additives_fetched': 0,
            'additives_relations_created': 0,
            'scores_calculated': 0,
            'database_updates': 0,
            'errors': []
        }

    def _check_product_high_risk_additives(self, product_id: str) -> bool:
        """
        Check if a product has high-risk additives using relations in the database.

        Args:
            product_id: Product ID to check

        Returns:
            True if product has high-risk additives, False otherwise
        """
        if not self.supabase:
            return False

        try:
            result = (
                self.supabase.table('product_additives')
                .select('additives!inner(risk_level)')
                .eq('product_id', product_id)
                .execute()
            )
            if hasattr(result, 'error') and result.error:
                return False
            for relation in result.data or []:
                additive = relation.get('additives') or {}
                risk_level = additive.get('risk_level')
                if risk_level and risk_level.lower() == 'high risk':
                    return True
            return False
        except Exception:
            return False

    def parse_ingredients(
        self,
        product: Dict[str, Any],
        save_to_db: Optional[bool] = None,
        force_ai: bool = False
    ) -> Dict[str, Any]:
        """
        Parse ingredients for the product with AI fallback.

        Args:
            product: Product data (must have 'specifications' field)
            save_to_db: Override auto_save_to_db setting (None = use default)

        Returns:
            Dictionary with parsing results:
            - extracted_ingredients: List of extracted ingredient names
            - matches: List of matched ingredients with data
            - nova_scores: List of NOVA scores for matched ingredients
            - ai_generated: Whether AI was used
            - source: Source of ingredients ('specifications', 'ai_parser', 'none')
        """
        save_to_db = save_to_db if save_to_db is not None else self.auto_save_to_db

        self.last_parse_ai_generated = False
        try:
            # Parse ingredients using the checker (will use AI if needed)
            parsing_result = self.ingredients_checker.check_product_ingredients(product, force_ai=force_ai)
            self.last_parse_ai_generated = bool(parsing_result.get('ai_generated', False))

            extracted_ingredients = parsing_result.get('extracted_ingredients', [])
            matches = parsing_result.get('matches', [])
            nova_scores = parsing_result.get('nova_scores', [])

            # Prepare parsed_ingredients data
            parsed_ingredients_data = {
                'extracted_ingredients': parsing_result.get('extracted_ingredients', []),
                'matches': parsing_result.get('matches', []),
                'nova_scores': parsing_result.get('nova_scores', []),
                'ai_generated': bool(parsing_result.get('ai_generated', False)),
                'source': parsing_result.get('source', 'unknown'),
                'force_ai': force_ai
            }

            # Update product object with parsed_ingredients (for use in calculate_health_scores)
            specs = product.get('specifications', {})
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except:
                    specs = {}

            specs['parsed_ingredients'] = parsed_ingredients_data
            product['specifications'] = specs

            # Save parsed ingredients to database if enabled
            if save_to_db and not self.dry_run and self.supabase and parsing_result.get('matches'):
                try:
                    product_id = product.get('id')
                    if product_id:
                        update_data = {
                            'specifications': specs,
                            'updated_at': datetime.now().isoformat()
                        }
                        result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()

                        if hasattr(result, 'error') and result.error:
                            self.stats['errors'].append(f"Parsed ingredients save error: {result.error}")
                        else:
                            self.stats['database_updates'] += 1
                except Exception as e:
                    self.stats['errors'].append(f"Parsed ingredients save error: {str(e)}")

            self.stats['ingredients_parsed'] += 1
            return parsing_result

        except Exception as e:
            self.stats['errors'].append(f"Ingredients parsing error: {str(e)}")
            return {
                'extracted_ingredients': extracted_ingredients,
                'matches': matches,
                'nova_scores': nova_scores,
                'ai_generated': False,
                'source': 'error'
            }

    def fetch_additives(
        self,
        product: Dict[str, Any],
        save_to_db: Optional[bool] = None
    ) -> bool:
        """
        Fetch additives from Open Food Facts for the product.

        Args:
            product: Product data (must have 'barcode' field)
            save_to_db: Override auto_save_to_db setting (None = use default)

        Returns:
            True if successful (including when no additives found), False on error
        """
        save_to_db = save_to_db if save_to_db is not None else self.auto_save_to_db

        try:
            barcode = product.get('barcode')
            if not barcode:
                return False

            # Fetch additives using the existing fetcher
            additives_tags = self.additives_fetcher.fetch_additives_from_off(barcode)

            if additives_tags is not None:
                # Update the product object with additives_tags
                product['additives_tags'] = additives_tags

                # Update the database if enabled
                if save_to_db and not self.dry_run and self.supabase:
                    product_id = product.get('id')
                    if product_id:
                        update_data = {'additives_tags': additives_tags}
                        result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()

                        if hasattr(result, 'error') and result.error:
                            self.stats['errors'].append(f"Additives update error: {result.error}")
                            return False
                        else:
                            self.stats['database_updates'] += 1

                self.stats['additives_fetched'] += 1
                return True
            else:
                self.stats['errors'].append("Failed to fetch additives from Open Food Facts")
                return False

        except Exception as e:
            self.stats['errors'].append(f"Additives fetching error: {str(e)}")
            return False

    def create_additives_relations(
        self,
        product: Dict[str, Any]
    ) -> bool:
        """
        Create relations between product and additives in the database.

        Args:
            product: Product data (must have 'id' and 'additives_tags' fields)

        Returns:
            True if successful (including when no additives to link), False on error
        """
        try:
            product_id = product.get('id')
            additives_tags = product.get('additives_tags', [])

            if not additives_tags:
                return True

            # Import the relation manager
            from processors.helpers.additives.additives_relation_manager import AdditivesRelationManager

            relation_manager = AdditivesRelationManager(dry_run=self.dry_run)

            # Create relations for the product
            stats = relation_manager.create_relations_for_product(
                product_id,
                additives_tags,
                product.get('name', 'Unknown Product')
            )

            self.stats['additives_relations_created'] += 1
            return True

        except Exception as e:
            self.stats['errors'].append(f"Additives relations error: {str(e)}")
            return False

    def calculate_health_scores(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate all health scores for the product.

        Args:
            product: Product data (must have 'specifications', 'id', 'barcode', 'name')

        Returns:
            Dictionary with calculated scores:
            - nutri_score: NutriScore value
            - nutri_source: Source of NutriScore
            - additives_score: AdditivesScore value
            - nova_score: NOVAScore value
            - nova_source: Source of NOVAScore
            - final_score: Final health score (None if cannot calculate)
            - display_score: Display score (None if final_score is None)
        """
        try:
            product_id = product.get('id')
            product_name = product.get('name', 'Unknown Product')

            scores = {
                'nutri_score': None,
                'additives_score': None,
                'nova_score': None,
                'final_score': None,
                'display_score': None,
                'nutri_source': None,
                'nova_source': None
            }

            # Calculate NutriScore
            nutri_result = self.nutri_calc.calculate(product)
            if isinstance(nutri_result, tuple):
                scores['nutri_score'], scores['nutri_source'] = nutri_result
            else:
                scores['nutri_score'], scores['nutri_source'] = nutri_result, 'unknown'

            # Calculate AdditivesScore
            additives_result = self.additives_calc.calculate_from_product_additives(product_id) if product_id else None
            has_high_risk_additives = False
            if additives_result:
                scores['additives_score'] = additives_result['score']
                high_count = additives_result.get('risk_breakdown', {}).get('high', 0)
                has_high_risk_additives = bool(high_count) or bool(additives_result.get('high_risk_additives'))
            else:
                has_high_risk_additives = self._check_product_high_risk_additives(product_id) if product_id else False

            # Calculate NovaScore
            nova_result = self.nova_calc.calculate(product)
            if isinstance(nova_result, tuple):
                scores['nova_score'], scores['nova_source'] = nova_result
            else:
                scores['nova_score'], scores['nova_source'] = nova_result, 'unknown'

            # Calculate final health score (with ingredient matching check)
            specs = product.get('specifications', {})
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except:
                    specs = {}

            parsed_ingredients = specs.get('parsed_ingredients', {})
            extracted_count = 0
            matched_count = 0
            hidden_count = 0
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

            # Require all extracted ingredients to be matched (visible only)
            if extracted_count > 0:
                all_matched = matched_count == extracted_count
                scores['match_counts'] = {
                    'matched': matched_count,
                    'hidden': hidden_count,
                    'extracted': extracted_count
                }
                scores['hidden_matches'] = hidden_count
                scores['match_ratio'] = matched_count / extracted_count if extracted_count else 0
                if not all_matched:
                    scores['final_score'] = None
                    scores['display_score'] = None
                    scores['has_high_risk_additives'] = has_high_risk_additives
                    self.stats['scores_calculated'] += 1
                    return scores

            # Calculate final score if all checks pass
            final_score = self._calculate_final_health_score(
                scores['nutri_score'],
                scores['additives_score'],
                scores['nova_score']
            )
            scores['final_score'] = final_score

            # Calculate display_score (capped at 49 if high-risk additives present)
            if final_score is not None:
                if has_high_risk_additives:
                    capped_score = min(final_score, 49)
                    scores['final_score'] = capped_score
                    scores['display_score'] = capped_score
                else:
                    scores['display_score'] = final_score
            scores['has_high_risk_additives'] = has_high_risk_additives

            self.stats['scores_calculated'] += 1
            return scores

        except Exception as e:
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

    def _calculate_final_health_score(self, nutri, additives, nova):
        """
        Calculate final health score from individual scores.

        Args:
            nutri: NutriScore value
            additives: AdditivesScore value
            nova: NOVAScore value

        Returns:
            Final health score or None if any score is missing
        """
        if nutri is None or additives is None or nova is None:
            return None
        return int(round(nutri * 0.4 + additives * 0.3 + nova * 0.3))

    def update_database(
        self,
        product_id: str,
        scores: Dict[str, Any],
        save_to_db: Optional[bool] = None
    ) -> bool:
        """
        Update the database with calculated scores.

        Args:
            product_id: Product ID
            scores: Dictionary with calculated scores
            save_to_db: Override auto_save_to_db setting (None = use default)

        Returns:
            True if successful, False otherwise
        """
        save_to_db = save_to_db if save_to_db is not None else self.auto_save_to_db

        if not save_to_db or self.dry_run or not self.supabase:
            return True

        try:
            update_data = {
                'updated_at': datetime.now().isoformat()
            }
            if self.last_parse_ai_generated:
                update_data['ai_parsed'] = True
                ai_time = self.batch_ai_parsed_time or datetime.now().isoformat()
                update_data['ai_parsed_time'] = ai_time
                self.last_ai_parsed_time_used = ai_time
            else:
                update_data['ai_parsed'] = False
                update_data['ai_parsed_time'] = None
                self.last_ai_parsed_time_used = None

            # Add scores to update data
            if scores.get('final_score') is not None:
                update_data['final_score'] = scores['final_score']

                # Calculate display_score if not already calculated
                if scores.get('display_score') is None and product_id:
                    has_high_risk = self._check_product_high_risk_additives(product_id)
                    display_score = min(scores['final_score'], 49) if has_high_risk else scores['final_score']
                    update_data['display_score'] = display_score
                elif scores.get('display_score') is not None:
                    update_data['display_score'] = scores['display_score']
            else:
                # Explicitly clear scores when final_score is missing (e.g., extracted > matched)
                update_data['final_score'] = None
                update_data['display_score'] = None

            if scores.get('nutri_score') is not None:
                update_data['nutri_score'] = scores['nutri_score']
                update_data['nutri_score_set_by'] = scores.get('nutri_source', 'local')
            if scores.get('additives_score') is not None:
                update_data['additives_score'] = scores['additives_score']
                update_data['additives_score_set_by'] = 'local'
            if scores.get('nova_score') is not None:
                update_data['nova_score'] = scores['nova_score']
                update_data['nova_score_set_by'] = scores.get('nova_source', 'local')

            # Remove None values except for fields we intentionally clear
            allow_none_keys = {'final_score', 'display_score', 'ai_parsed_time'}
            update_data = {
                k: v for k, v in update_data.items()
                if v is not None or k in allow_none_keys
            }

            result = self.supabase.table('products').update(update_data).eq('id', product_id).execute()

            if hasattr(result, 'error') and result.error:
                self.stats['errors'].append(f"Database update error: {result.error}")
                return False
            else:
                self.stats['database_updates'] += 1
                return True

        except Exception as e:
            self.stats['errors'].append(f"Database update error: {str(e)}")
            return False

    def process_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a product through the complete pipeline.

        This method performs all steps:
        1. Parse ingredients (with AI fallback)
        2. Fetch additives
        3. Create additives relations
        4. Calculate health scores
        5. Update database

        Args:
            product: Product data from Supabase

        Returns:
            Dictionary with processing results:
            - success: True if processing completed without errors
            - ingredients_result: Ingredients parsing results
            - additives_fetched: Whether additives were fetched
            - scores: Calculated health scores
            - errors: List of errors encountered
        """
        self.stats['products_processed'] += 1

        result = {
            'success': True,
            'ingredients_result': None,
            'additives_fetched': False,
            'scores': None,
            'errors': []
        }

        product_id = product.get('id')

        # Step 1: Parse ingredients
        ingredients_result = self.parse_ingredients(product)
        result['ingredients_result'] = ingredients_result

        # Step 2: Fetch additives
        additives_fetched = self.fetch_additives(product)
        result['additives_fetched'] = additives_fetched

        # Step 3: Create additives relations (if additives were fetched)
        if additives_fetched:
            self.create_additives_relations(product)

        # Step 4: Calculate health scores
        scores = self.calculate_health_scores(product)
        result['scores'] = scores

        # Step 5: Update database
        if product_id:
            self.update_database(product_id, scores)

        # Collect errors
        if self.stats['errors']:
            result['errors'] = self.stats['errors'][-5:]  # Last 5 errors
            result['success'] = len([e for e in self.stats['errors'] if 'error' in e.lower()]) == 0

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            'products_processed': 0,
            'ingredients_parsed': 0,
            'additives_fetched': 0,
            'additives_relations_created': 0,
            'scores_calculated': 0,
            'database_updates': 0,
            'errors': []
        }


def main():
    """Test the ProductScorer."""
    import argparse

    parser = argparse.ArgumentParser(description='Test ProductScorer with a single product')
    parser.add_argument('product_id', help='Product ID to process')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    args = parser.parse_args()

    try:
        scorer = ProductScorer(dry_run=args.dry_run)

        # Fetch product
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        supabase = create_client(supabase_url, supabase_key)

        result = supabase.table('products').select('*').eq('id', args.product_id).execute()
        if not result.data:
            print(f"❌ Product {args.product_id} not found")
            return

        product = result.data[0]

        # Process product
        result = scorer.process_product(product)

        print(f"\n✅ Processing complete!")
        print(f"📊 Stats: {scorer.get_stats()}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
