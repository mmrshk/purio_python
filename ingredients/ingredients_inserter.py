#!/usr/bin/env python3
"""
Supabase ingredients inserter for adding new ingredients to the database.

This class:
1. Adds new ingredients to the Supabase ingredients table
2. Handles duplicate detection and conflict resolution
3. Tracks insertion statistics and errors
4. Provides batch insertion capabilities
"""

import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from supabase import create_client
from dotenv import load_dotenv

try:
    from .ingredient_ai_processor import IngredientAIProcessor, IngredientAIResult
except ImportError:
    from ingredient_ai_processor import IngredientAIProcessor, IngredientAIResult

try:
    from .ingredient_blacklist import is_blacklisted
except ImportError:
    from ingredient_blacklist import is_blacklisted

try:
    from .ingredient_ai_processor import IngredientAIProcessor, IngredientAIResult
except ImportError:
    from ingredient_ai_processor import IngredientAIProcessor, IngredientAIResult

load_dotenv()

VALID_RISK_LEVELS = {"free", "low", "moderate", "high"}


class IngredientsInserter:
    def __init__(
        self,
        *,
        ingredient_processor: Optional[IngredientAIProcessor] = None,
        enable_ai_processing: bool = False
    ):
        """
        Initialize the ingredients inserter.
        """
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        self.supabase = create_client(supabase_url, supabase_key)
        self._ingredient_processor: Optional[IngredientAIProcessor] = ingredient_processor
        self._ai_processing_enabled = enable_ai_processing
        # In-memory cache to avoid repeated AI enrichment calls within the same run
        self._ai_cache: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self.stats = {
            'ingredients_processed': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_updated': 0,
            'errors': 0,
            'duplicate_ingredients': 0
        }

    def _get_ingredient_processor(self) -> Optional[IngredientAIProcessor]:
        if not self._ai_processing_enabled:
            return None
        if self._ingredient_processor:
            return self._ingredient_processor
        try:
            self._ingredient_processor = IngredientAIProcessor()
            print("🧠 Ingredient AI processor initialized inside IngredientsInserter")
        except Exception as exc:
            print(f"⚠️  IngredientAIProcessor initialization failed: {exc}")
            self._ingredient_processor = None
            self._ai_processing_enabled = False
        return self._ingredient_processor

    def insert_candidate_ingredient(
        self,
        raw_name: str,
        *,
        context: Optional[str] = None,
        source_language: str = "ro",
        created_by: str = "ai_parser",
        visible: bool = False,
    ) -> Dict[str, Any]:
        """
        Preprocess a raw ingredient candidate with AI (if enabled) and insert it.
        """
        candidate = (raw_name or "").strip()
        if not candidate or len(candidate) < 2:
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'invalid_candidate',
                'message': 'Candidate ingredient is empty or too short',
                'ai_result': None
            }

        # Basic, low-risk prechecks to avoid AI calls:
        # 1) Blacklist gate on raw and normalized forms
        candidate_norm = candidate.lower().strip()
        if is_blacklisted(candidate_norm):
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'ai_rejected',
                'message': 'blacklisted term (generic/role/additive)',
                'ai_result': None
            }

        # 2) Exact DB existence check (English or Romanian name)
        try:
            existing = self._check_existing_ingredient(candidate, candidate)
            if existing:
                return {
                    'success': False,
                    'action': 'skipped',
                    'reason': 'duplicate',
                    'ingredient_id': existing.get('id'),
                    'message': f"Ingredient already exists: {existing.get('name') or existing.get('ro_name') or candidate}",
                    'ai_result': None
                }
        except Exception:
            # If DB check fails, continue with normal flow
            pass

        # 3) In-memory AI cache check to avoid repeated enrich calls within same run
        cache_key = f"enrich|{source_language.lower().strip()}|{candidate_norm}"
        cached = self._ai_cache.get(cache_key)
        if cached:
            cached_is_ingredient = bool(cached.get('is_ingredient'))
            if not cached_is_ingredient:
                return {
                    'success': False,
                    'action': 'skipped',
                    'reason': 'ai_rejected',
                    'message': cached.get('reason') or 'AI classified candidate as non-ingredient (cache)',
                    'ai_result': cached
                }
            # Proceed to insertion using cached data
            name = cached.get('name') or candidate
            ro_name = cached.get('ro_name') or candidate
            # Final blacklist guard
            if is_blacklisted((name or '').lower().strip()) or is_blacklisted((ro_name or '').lower().strip()):
                return {
                    'success': False,
                    'action': 'skipped',
                    'reason': 'ai_rejected',
                    'message': 'blacklisted term (generic/role/additive)',
                    'ai_result': cached
                }
            insertion_result = self.insert_ingredient(
                name=name,
                ro_name=ro_name,
                nova_score=cached.get('nova_score'),
                created_by=created_by,
                visible=visible,
                description=cached.get('description'),
                ro_description=cached.get('ro_description'),
                risk_level=cached.get('risk_level')
            )
            insertion_result['ai_result'] = cached
            return insertion_result

        processor = self._get_ingredient_processor()
        if not processor:
            return self.insert_ingredient(
                name=candidate,
                ro_name=candidate,
                nova_score=None,
                created_by=created_by,
                visible=visible
            )

        ai_result: IngredientAIResult = processor.process_ingredient(
            candidate,
            context=context,
            source_language=source_language
        )

        if ai_result.error:
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'ai_error',
                'message': ai_result.error,
                'ai_result': ai_result.to_dict()
            }

        if not ai_result.is_ingredient:
            # Cache negative result
            self._ai_cache[cache_key] = ai_result.to_dict()
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'ai_rejected',
                'message': ai_result.reason or 'AI classified candidate as non-ingredient',
                'ai_result': ai_result.to_dict()
            }

        if not ai_result.name:
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'missing_translation',
                'message': 'AI could not supply English name for ingredient',
                'ai_result': ai_result.to_dict()
            }

        # Final blacklist guard on both AI English name and Romanian/source name
        name_norm = ai_result.name.lower().strip()
        ro_norm = (ai_result.ro_name or candidate).lower().strip()
        if is_blacklisted(name_norm) or is_blacklisted(ro_norm):
            # Cache negative result
            self._ai_cache[cache_key] = ai_result.to_dict()
            return {
                'success': False,
                'action': 'skipped',
                'reason': 'ai_rejected',
                'message': 'blacklisted term (generic/role/additive)',
                'ai_result': ai_result.to_dict()
            }

        insertion_result = self.insert_ingredient(
            name=ai_result.name,
            ro_name=ai_result.ro_name or candidate,
            nova_score=ai_result.nova_score,
            created_by=created_by,
            visible=visible,
            description=ai_result.description,
            ro_description=ai_result.ro_description,
            risk_level=ai_result.risk_level
        )

        # Cache positive result
        cached_payload = ai_result.to_dict()
        self._ai_cache[cache_key] = cached_payload
        insertion_result['ai_result'] = cached_payload
        return insertion_result

    def insert_ingredient(
        self,
        name: str,
        ro_name: str,
        nova_score: Optional[int] = 1,
        created_by: str = "ai_parser",
        visible: bool = True,
        description: Optional[str] = None,
        ro_description: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert a single ingredient into the Supabase ingredients table.

        Args:
            name: English name of the ingredient
            ro_name: Romanian name of the ingredient
            nova_score: NOVA score (1-4, or None for AI-generated ingredients, default: 1)
            created_by: Source of the ingredient (default: "ai_parser")
            visible: Visibility flag (default: True)
            description: Short English description (optional)
            ro_description: Short Romanian description (optional)
            risk_level: Risk classification (optional, must match known values)

        Returns:
            Dictionary with insertion result
        """
        self.stats['ingredients_processed'] += 1

        try:
            # Check if ingredient already exists
            existing = self._check_existing_ingredient(name, ro_name)

            if existing:
                self.stats['duplicate_ingredients'] += 1
                return {
                    'success': False,
                    'action': 'skipped',
                    'reason': 'duplicate',
                    'ingredient_id': existing['id'],
                    'message': f"Ingredient already exists: {name}"
                }

            # Prepare ingredient data
            ingredient_data = {
                'name': name.strip(),
                'ro_name': ro_name.strip(),
                'nova_score': nova_score,
                'created_by': created_by,
                'visible': visible
            }

            if description:
                ingredient_data['description'] = description.strip()

            if ro_description:
                ingredient_data['ro_description'] = ro_description.strip()

            if risk_level and risk_level in VALID_RISK_LEVELS:
                ingredient_data['risk_level'] = risk_level

            # Insert ingredient
            result = self.supabase.table('ingredients').insert(ingredient_data).execute()

            if hasattr(result, 'error') and result.error:
                self.stats['errors'] += 1
                return {
                    'success': False,
                    'action': 'error',
                    'reason': 'insertion_failed',
                    'error': str(result.error),
                    'message': f"Failed to insert ingredient: {name}"
                }

            # Get the inserted ingredient ID
            inserted_ingredient = result.data[0] if result.data else None
            ingredient_id = inserted_ingredient.get('id') if inserted_ingredient else None

            self.stats['ingredients_inserted'] += 1

            return {
                'success': True,
                'action': 'inserted',
                'ingredient_id': ingredient_id,
                'message': f"Successfully inserted ingredient: {name}"
            }

        except Exception as e:
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'error',
                'reason': 'exception',
                'error': str(e),
                'message': f"Exception while inserting ingredient: {name}"
            }

    def insert_ingredients_batch(self, ingredients: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert multiple ingredients in a batch operation.

        Args:
            ingredients: List of ingredient dictionaries with keys:
                        - name: English name
                        - ro_name: Romanian name
                        - nova_score: NOVA score (optional, default: 1)
                        - created_by: Source (optional, default: "ai_parser")

        Returns:
            Dictionary with batch insertion results
        """
        results = {
            'total_processed': len(ingredients),
            'successful_insertions': 0,
            'skipped_duplicates': 0,
            'errors': 0,
            'details': []
        }

        for ingredient in ingredients:
            name = ingredient.get('name', '')
            ro_name = ingredient.get('ro_name', '')
            nova_score = ingredient.get('nova_score', 1)
            created_by = ingredient.get('created_by', 'ai_parser')
            visible = ingredient.get('visible', True)
            description = ingredient.get('description')
            ro_description = ingredient.get('ro_description')
            risk_level = ingredient.get('risk_level')

            if not name or not ro_name:
                results['errors'] += 1
                results['details'].append({
                    'ingredient': ingredient,
                    'success': False,
                    'reason': 'missing_name_or_ro_name'
                })
                continue

            result = self.insert_ingredient(
                name=name,
                ro_name=ro_name,
                nova_score=nova_score,
                created_by=created_by,
                visible=visible,
                description=description,
                ro_description=ro_description,
                risk_level=risk_level,
            )
            results['details'].append({
                'ingredient': ingredient,
                'result': result
            })

            if result['success']:
                results['successful_insertions'] += 1
            elif result['reason'] == 'duplicate':
                results['skipped_duplicates'] += 1
            else:
                results['errors'] += 1

        return results

    def _check_existing_ingredient(self, name: str, ro_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if an ingredient already exists in the database.

        Args:
            name: English name of the ingredient
            ro_name: Romanian name of the ingredient

        Returns:
            Existing ingredient data if found, None otherwise
        """
        try:
            # Check by English name
            result = self.supabase.table('ingredients').select('*').eq('name', name.strip()).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            # Check by Romanian name
            result = self.supabase.table('ingredients').select('*').eq('ro_name', ro_name.strip()).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            return None

        except Exception as e:
            print(f"Error checking existing ingredient: {str(e)}")
            return None

    def get_ingredient_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get an ingredient by its English or Romanian name.

        Args:
            name: Name to search for

        Returns:
            Ingredient data if found, None otherwise
        """
        try:
            # Search by English name
            result = self.supabase.table('ingredients').select('*').eq('name', name.strip()).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            # Search by Romanian name
            result = self.supabase.table('ingredients').select('*').eq('ro_name', name.strip()).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            return None

        except Exception as e:
            print(f"Error getting ingredient by name: {str(e)}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get insertion statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset insertion statistics."""
        self.stats = {
            'ingredients_processed': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_updated': 0,
            'errors': 0,
            'duplicate_ingredients': 0
        }

    def validate_ingredient_data(self, name: str, ro_name: str, nova_score: int = 1) -> Tuple[bool, str]:
        """
        Validate ingredient data before insertion.

        Args:
            name: English name
            ro_name: Romanian name
            nova_score: NOVA score

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "English name is required"

        if not ro_name or not ro_name.strip():
            return False, "Romanian name is required"

        if not isinstance(nova_score, int) or nova_score < 1 or nova_score > 4:
            return False, "NOVA score must be an integer between 1 and 4"

        if len(name.strip()) < 2:
            return False, "English name must be at least 2 characters long"

        if len(ro_name.strip()) < 2:
            return False, "Romanian name must be at least 2 characters long"

        return True, ""


def main():
    """Test the ingredients inserter."""
    try:
        inserter = IngredientsInserter()

        # Test single ingredient insertion
        print("🧪 Testing Single Ingredient Insertion")
        print("=" * 50)

        result = inserter.insert_ingredient(
            name="test_ingredient",
            ro_name="ingredient_test",
            nova_score=1,
            created_by="test_script",
            visible=False
        )

        print(f"Result: {result}")
        print(f"Stats: {inserter.get_stats()}")

        # Test batch insertion
        print("\n🧪 Testing Batch Ingredient Insertion")
        print("=" * 50)

        test_ingredients = [
            {
                'name': 'flour',
                'ro_name': 'făină',
                'nova_score': 2,
                'created_by': 'ai_parser'
            },
            {
                'name': 'sugar',
                'ro_name': 'zahăr',
                'nova_score': 2,
                'created_by': 'ai_parser'
            },
            {
                'name': 'salt',
                'ro_name': 'sare',
                'nova_score': 2,
                'created_by': 'ai_parser'
            }
        ]

        batch_result = inserter.insert_ingredients_batch(test_ingredients)
        print(f"Batch Result: {batch_result}")
        print(f"Final Stats: {inserter.get_stats()}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in environment variables.")


if __name__ == "__main__":
    main()
