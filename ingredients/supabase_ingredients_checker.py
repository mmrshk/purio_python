#!/usr/bin/env python3
"""
Supabase-based ingredients checker for processing product ingredients.

This class:
1. Fetches ingredients from the Supabase ingredients table
2. Uses fuzzy search to match ingredients from products with the database
3. Returns NOVA score distributions for ingredient analysis
"""

import os
import sys
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from fuzzywuzzy import process
from supabase import create_client
from dotenv import load_dotenv

try:
    from .ai_ingredients_parser import AIIngredientsParser
except ImportError:
    from ai_ingredients_parser import AIIngredientsParser

try:
    from .ingredients_inserter import IngredientsInserter
except ImportError:
    from ingredients_inserter import IngredientsInserter

try:
    from .ingredient_blacklist import is_blacklisted
except ImportError:
    from ingredient_blacklist import is_blacklisted

load_dotenv()

class SupabaseIngredientsChecker:
    def __init__(
        self,
        use_ai_fallback: bool = True,
        ai_model: str = "gpt-3.5-turbo",
        supabase_client=None,
        ai_parser=None,
        match_threshold: int = 90,
        auto_insert_new_ingredients: bool = False,
        ingredients_inserter: Any = None,
    ):
        """
        Initialize the Supabase ingredients checker with optional AI fallback.

        Args:
            use_ai_fallback: Whether to use AI when no ingredients found
            ai_model: AI model to use for fallback parsing
        """
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        self.supabase = supabase_client or create_client(supabase_url, supabase_key)
        self.ingredients_data = self._load_ingredients_from_supabase()
        self.use_ai_fallback = use_ai_fallback
        self.ai_parser = ai_parser
        self.match_threshold = match_threshold
        self.auto_insert_new_ingredients = auto_insert_new_ingredients
        self.ingredients_inserter = ingredients_inserter

        if use_ai_fallback and self.ai_parser is None:
            try:
                self.ai_parser = AIIngredientsParser(model=ai_model)
                print("🤖 AI ingredients parser initialized")
            except Exception as e:
                print(f"⚠️  AI parser initialization failed: {str(e)}")
                print("   Continuing without AI fallback...")
                self.use_ai_fallback = False

        if self.auto_insert_new_ingredients and self.ingredients_inserter is None:
            try:
                self.ingredients_inserter = IngredientsInserter(enable_ai_processing=True)
                print("🔗 Ingredients inserter ready for auto-insert of unmatched AI ingredients")
            except Exception as e:
                print(f"⚠️  Ingredients inserter initialization failed: {str(e)}")
                self.auto_insert_new_ingredients = False

        # Statistics
        self.stats = {
            'products_processed': 0,
            'products_with_ingredients': 0,
            'products_with_ai_ingredients': 0,
            'total_ingredients_found': 0,
            'ingredients_matched': 0,
            'ingredients_not_matched': 0,
            'nova_scores': {1: 0, 2: 0, 3: 0, 4: 0},
            'ai_stats': {}
        }

    def _load_ingredients_from_supabase(self) -> Dict[str, Dict[str, Any]]:
        """
        Load ingredients from Supabase ingredients table.

        Returns:
            Dictionary with ingredient names as keys and data as values
        """
        ingredients = {}

        try:
            # Fetch all ingredients from Supabase
            result = self.supabase.table('ingredients').select('*').execute()

            if hasattr(result, 'error') and result.error:
                raise Exception(f"Error fetching ingredients: {result.error}")

            ingredients_list = result.data

            for ingredient in ingredients_list:
                ingredient_id = ingredient.get('id')
                name = ingredient.get('name', '').lower().strip()
                name_ro = ingredient.get('ro_name', '').lower().strip()
                nova_score = ingredient.get('nova_score', 1)

                # Store both English and Romanian versions
                visible = ingredient.get('visible', True)

                if name:
                    ingredients[name] = {
                        'id': ingredient_id,
                        'name': ingredient.get('name'),
                        'name_ro': ingredient.get('ro_name'),
                        'nova_score': nova_score,
                        'visible': visible
                    }

                if name_ro:
                    ingredients[name_ro] = {
                        'id': ingredient_id,
                        'name': ingredient.get('name'),
                        'name_ro': ingredient.get('ro_name'),
                        'nova_score': nova_score,
                        'visible': visible
                    }

            print(f"Loaded {len(ingredients)//2} ingredients from Supabase (English + Romanian)")
            return ingredients

        except Exception as e:
            print(f"Error loading ingredients from Supabase: {str(e)}")
            raise

    def extract_ingredients_from_text(self, text: str) -> List[str]:
        """
        Extract ingredients from text using various patterns.

        Args:
            text: Text containing ingredients

        Returns:
            List of extracted ingredients
        """
        if not text:
            return []

        # Convert to lowercase for better matching
        text = text.lower()

        # Common patterns for ingredient lists
        patterns = [
            r'ingrediente:\s*(.*?)(?=\n|\.|$)',  # Romanian: "Ingrediente: ..."
            r'ingredients:\s*(.*?)(?=\n|\.|$)',  # English: "Ingredients: ..."
            r'conține:\s*(.*?)(?=\n|\.|$)',      # Romanian: "Conține: ..."
            r'contains:\s*(.*?)(?=\n|\.|$)',     # English: "Contains: ..."
        ]

        ingredients = []

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Split by common separators
                parts = re.split(r'[,;\.]', match)
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 2:  # Filter out very short parts
                        ingredients.append(part)

        # If no specific pattern found, try to extract from the whole text
        if not ingredients:
            # Look for common ingredient indicators
            if any(keyword in text for keyword in ['ingrediente', 'ingredients', 'conține', 'contains']):
                # Split by common separators and clean up
                parts = re.split(r'[,;\.]', text)
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 2:
                        ingredients.append(part)

        # If still no ingredients, try to extract from the whole text
        if not ingredients:
            # Split by common separators and clean up
            parts = re.split(r'[,;\.]', text)
            for part in parts:
                part = part.strip()
                # Remove parentheses and their contents, but keep what's inside
                part = re.sub(r'\(([^)]*)\)', r'\1', part).strip()
                # Remove percentages and other non-ingredient text
                part = re.sub(r'\d+%', '', part).strip()
                part = re.sub(r'\*\*.*?\*\*', '', part).strip()  # Remove **text** patterns
                # Filter out very short parts and common non-ingredient words
                if (part and len(part) > 2 and
                    part not in ['și', 'and', 'sau', 'or', 'cu', 'with', 'din', 'from']):
                    ingredients.append(part)

        return list(set(ingredients))  # Remove duplicates

    def _load_specs(self, product: Dict[str, Any]) -> Dict[str, Any]:
        specs = product.get('specifications', {})
        if isinstance(specs, str):
            try:
                specs = json.loads(specs)
            except:
                specs = {}
        return specs if isinstance(specs, dict) else {}

    def _reuse_parsed_ai_results(self, specs: Dict[str, Any], product_name: str) -> Optional[Dict[str, Any]]:
        try:
            parsed_prev = specs.get('parsed_ingredients', {})
            if isinstance(parsed_prev, dict) and parsed_prev.get('ai_generated') and parsed_prev.get('extracted_ingredients'):
                extracted_ingredients = parsed_prev.get('extracted_ingredients', [])
                matches = parsed_prev.get('matches', [])
                nova_scores = parsed_prev.get('nova_scores', [])
                # Update stats based on stored data
                self.stats['products_with_ai_ingredients'] += 1
                self.stats['total_ingredients_found'] += len(extracted_ingredients)
                self.stats['ingredients_matched'] += len(matches)
                not_matched = max(0, len(extracted_ingredients) - len(matches))
                self.stats['ingredients_not_matched'] += not_matched
                for score in nova_scores:
                    if score in self.stats['nova_scores']:
                        self.stats['nova_scores'][score] += 1
                if self.ai_parser:
                    self.stats['ai_stats'] = self.ai_parser.get_stats()
                return {
                    'product_name': product_name,
                    'ingredients_text': specs.get('ingredients', ''),
                    'extracted_ingredients': extracted_ingredients,
                    'matches': matches,
                    'nova_scores': nova_scores,
                    'source': 'ai_parser',
                    'ai_generated': True
                }
        except Exception:
            return None

    def _compute_matches(self, ingredients_list: List[str]) -> Tuple[List[Dict[str, Any]], List[int], int, int]:
        local_matches: List[Dict[str, Any]] = []
        local_nova_scores: List[int] = []
        local_matched = 0
        local_not_matched = 0
        for ing in ingredients_list:
            m = self.fuzzy_match_ingredient(ing, threshold=self.match_threshold)
            if m:
                local_matches.append(m)
                local_nova_scores.append(m['data']['nova_score'])
                local_matched += 1
            else:
                local_not_matched += 1
        return local_matches, local_nova_scores, local_matched, local_not_matched

    def _log_ai_ingredients(self, ingredients: List[str]):
        try:
            if ingredients:
                print(f"      AI ingredients: {', '.join(ingredients)}")
        except Exception:
            pass

    def _try_ai(self, product_name: str, description: str, ingredients_text: str = None) -> Tuple[List[str], Optional[str]]:
        """
        Try AI parsing. If ingredients_text is provided, use it instead of product name.

        Args:
            product_name: Product name
            description: Product description
            ingredients_text: Optional ingredients text to parse (preferred over product name)

        Returns:
            Tuple of (list of extracted ingredients, error message if any)
        """
        if not (self.use_ai_fallback and self.ai_parser):
            return [], None

        # If ingredients text is provided, use it as context instead of product name
        if ingredients_text:
            # Use AI to parse from ingredients text (better than product name)
            print(f"🤖 Using AI to parse ingredients from ingredients text (not product name)")
            context = f"Ingredients list: {ingredients_text}"
            if product_name:
                context += f"\nProduct: {product_name}"
            ai_result = self._try_ai_from_text(context)
        else:
            # Fall back to product name if no ingredients text
            ai_result = self.ai_parser.parse_ingredients_from_name(product_name, description)

        error = ai_result.get('error')
        if ai_result.get('extracted_ingredients'):
            ai_ings = ai_result['extracted_ingredients']
            self.stats['products_with_ai_ingredients'] += 1
            self._log_ai_ingredients(ai_ings)
            return ai_ings, error
        return [], error

    def _try_ai_from_text(self, context: str) -> Dict[str, Any]:
        """
        Use AI to parse ingredients from a given text context.

        Args:
            context: Text to parse (could be ingredients list, product name, etc.)

        Returns:
            Dictionary with parsing results
        """
        if not (self.use_ai_fallback and self.ai_parser):
            return {'extracted_ingredients': []}

        try:
            # Create a prompt that focuses on parsing the provided text
            prompt = self.ai_parser._create_ingredient_prompt(context)

            # Make AI request
            response = self.ai_parser._make_ai_request(prompt)

            if response:
                # Parse AI response
                ingredients = self.ai_parser._parse_ai_response(response)

                return {
                    'extracted_ingredients': ingredients,
                    'ai_generated': True,
                    'source': 'ai_parser'
                }
            else:
                return {
                    'extracted_ingredients': [],
                    'ai_generated': False,
                    'source': 'ai_parser_failed'
                }
        except Exception as e:
            print(f"   ❌ AI parsing from text error: {str(e)}")
            return {
                'extracted_ingredients': [],
                'ai_generated': False,
                'source': 'ai_parser_error',
                'error': str(e)
            }

    def _auto_insert_unmatched(self, extracted_ingredients: List[str], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not (self.auto_insert_new_ingredients and self.ingredients_inserter and extracted_ingredients):
            return {'rejected': [], 'resolved_duplicates': []}
        try:
            matched_names = set(m['matched_name'].lower().strip() for m in matches)
            matched_originals = set(m.get('original', '').lower().strip() for m in matches if m.get('original'))

            # Blacklist for non-ingredient terms that might slip through
            non_ingredient_blacklist = {'air', 'sun', 'time', 'heat', 'light', 'temperature', 'drying', 'curing', 'aging'}

            rejected: List[str] = []
            resolved_duplicates: List[Dict[str, Any]] = []
            for ing in extracted_ingredients:
                print(f"   🔍 Evaluating unmatched ingredient: {ing}")
                # Clean the ingredient: remove trailing punctuation, parentheses, etc.
                cleaned_ing = self._clean_ingredient_for_insertion(ing)
                if not cleaned_ing or len(cleaned_ing) < 2:
                    print(f"   ⏭️  Skipping invalid ingredient (too short/empty): {ing}")
                    continue

                ing_norm = cleaned_ing.lower().strip()

                # Skip auto-insert if this ingredient was matched (by original text) or equals any matched name
                if ing_norm in matched_originals or ing_norm in matched_names:
                    print(f"   ⏭️  Already matched ingredient, skipping insert: {cleaned_ing}")
                    continue

                # Check blacklist
                if is_blacklisted(ing_norm):
                    print(f"   ⏭️  Skipping blacklisted ingredient: {cleaned_ing}")
                    rejected.append(ing_norm)
                    continue

                # Skip if it's a blacklisted non-ingredient term
                if ing_norm in non_ingredient_blacklist:
                    print(f"   ⏭️  Skipping non-ingredient term: {cleaned_ing}")
                    rejected.append(ing_norm)
                    continue

                res = self.ingredients_inserter.insert_candidate_ingredient(
                    cleaned_ing,
                    source_language="ro",
                    created_by="ai_parser",
                    visible=False
                )
                ai_payload = res.get('ai_result')
                if res.get('success') and res.get('action') == 'inserted':
                    if ai_payload:
                        print(f"   💾 Inserted new ingredient to DB: {ai_payload.get('name')} (RO: {ai_payload.get('ro_name')})")
                    else:
                        print(f"   💾 Inserted new ingredient to DB: {cleaned_ing}")
                elif res.get('reason') == 'duplicate':
                    name_display = (ai_payload and ai_payload.get('name')) or cleaned_ing
                    print(f"   ⏭️  Skipped existing ingredient in DB: {name_display}")
                    # Try to resolve duplicate as a successful match so it won't block scoring
                    dup_id = res.get('ingredient_id')
                    try:
                        if dup_id and self.supabase:
                            fetched = self.supabase.table('ingredients').select('*').eq('id', dup_id).execute()
                            row = fetched.data[0] if (hasattr(fetched, 'data') and fetched.data) else None
                            if row:
                                data = {
                                    'id': row.get('id'),
                                    'name': row.get('name'),
                                    'name_ro': row.get('ro_name'),
                                    'nova_score': row.get('nova_score', 1),
                                    'visible': row.get('visible', True),
                                }
                                resolved_duplicates.append({
                                    'matched_name': (row.get('ro_name') or row.get('name') or cleaned_ing),
                                    'data': data,
                                    'score': 100,
                                    'original': ing,
                                    'method': 'ai_duplicate_resolved'
                                })
                    except Exception as _e:
                        # Best-effort; ignore resolution failure
                        pass
                else:
                    reason = res.get('reason') or (ai_payload and ai_payload.get('reason')) or res.get('message')
                    if reason:
                        print(f"   ⏭️  Skipped ingredient '{cleaned_ing}': {reason}")
                    else:
                        print(f"   ⏭️  Skipped ingredient '{cleaned_ing}'")
                    # If AI explicitly rejected as non-ingredient, mark it for removal from extracted list
                    if res.get('reason') == 'ai_rejected' or (ai_payload and ai_payload.get('is_ingredient') is False):
                        rejected.append(ing_norm)
            return {'rejected': rejected, 'resolved_duplicates': resolved_duplicates}
        except Exception as e:
            print(f"⚠️  Auto-insert unmatched ingredients failed: {str(e)}")
            return {'rejected': [], 'resolved_duplicates': []}

    def _clean_ingredient_for_insertion(self, ingredient: str) -> str:
        """
        Clean ingredient name before insertion: remove trailing punctuation, parentheses, etc.

        Args:
            ingredient: Raw ingredient string

        Returns:
            Cleaned ingredient name
        """
        if not ingredient:
            return ""

        cleaned = ingredient.strip()

        # Remove trailing punctuation: ), ], }, etc.
        cleaned = re.sub(r'[)\]},;]+$', '', cleaned)

        # Remove leading punctuation: (, [, {, etc.
        cleaned = re.sub(r'^[(\[{]+', '', cleaned)

        # Remove trailing periods, commas, colons
        cleaned = re.sub(r'[.,:;]+$', '', cleaned)

        # Remove extra whitespace
        cleaned = cleaned.strip()

        return cleaned

    def fuzzy_match_ingredient(self, ingredient: str, threshold: int = 90) -> Optional[Dict[str, Any]]:
        """
        Find the best fuzzy match for an ingredient.

        Args:
            ingredient: Ingredient to match
            threshold: Minimum similarity score (0-100)

        Returns:
            Dictionary with match information or None if no good match found
        """
        if not ingredient or not self.ingredients_data:
            return None

        ingredient_lower = ingredient.lower().strip()

        try:
            # Get potential matches ordered by score
            matches = process.extractBests(
                ingredient_lower,
                self.ingredients_data.keys(),
                limit=5  # Get top 5 matches for better filtering
            )

            if matches:
                min_threshold = threshold if threshold is not None else self.match_threshold
                for candidate in matches:
                    matched_name = candidate[0]
                    score = candidate[1]

                    if score < min_threshold:
                        continue

                    ingredient_data = self.ingredients_data.get(matched_name)
                    if not ingredient_data:
                        continue

                    if not ingredient_data.get('visible', True):
                        print(f"   ⏭️  Skipping hidden ingredient match: {matched_name}")
                        continue

                    if self._is_valid_match(ingredient_lower, matched_name, score):
                        return {
                            'matched_name': matched_name,
                            'data': ingredient_data,
                            'score': score,
                            'original': ingredient,
                            'method': 'fuzzy_match'
                        }

            return None

        except Exception as e:
            print(f"Error in fuzzy matching for '{ingredient}': {str(e)}")
            return None

    def _is_valid_match(self, ingredient: str, match: str, score: int) -> bool:
        """
        Check if a fuzzy match is valid by applying common sense rules.

        Args:
            ingredient: Original ingredient text
            match: Matched ingredient name
            score: Similarity score

        Returns:
            True if the match is valid, False otherwise
        """
        # Very high threshold for short ingredients
        if len(ingredient) < 5 and score < 95:
            return False

        # CRITICAL: Prevent false "sorb" matches
        # "sorbat" (potassium sorbate) and "sorbitol" should NOT match "serviceberry"
        if 'sorbat' in ingredient or 'sorbitol' in ingredient:
            if 'serviceberry' in match.lower() or 'sorb' in match.lower():
                return False

        # CRITICAL: Ensure lecithin matches correctly
        # "lecitina de soia" should match "soy lecithin", not "soybean"
        if 'lecitina' in ingredient.lower():
            if 'lecithin' not in match.lower() and score < 95:
                return False
            # If ingredient mentions a specific source (soia, floarea-soarelui), match should too
            if 'soia' in ingredient.lower() and 'soy' not in match.lower() and score < 95:
                return False
            if 'floarea-soarelui' in ingredient.lower() and 'sunflower' not in match.lower() and score < 95:
                return False

        # Check for obvious category mismatches
        ingredient_words = set(ingredient.split())
        match_words = set(match.lower().split())

        # If ingredient contains specific food words, match should too
        food_words = ['lapte', 'milk', 'zahar', 'sugar', 'unt', 'butter', 'ou', 'egg']
        for word in food_words:
            if word in ingredient_words and word not in match_words and score < 95:
                return False

        # CRITICAL: Prevent "coffee beans" or "cocoa beans" from matching generic "bean" (legume)
        # "arabica coffee beans" should NOT match "bean" (fasole)
        coffee_related = ['coffee', 'cafea', 'cafe', 'arabica', 'robusta']
        bean_related = ['bean', 'beans', 'fasole']
        ingredient_lower = ingredient.lower()
        match_lower = match.lower()

        # If ingredient mentions coffee/cocoa and match is just "bean" without coffee context, reject
        has_coffee_context = any(word in ingredient_lower for word in coffee_related + ['cocoa', 'cacao'])
        is_generic_bean = any(word in match_lower for word in bean_related) and not any(word in match_lower for word in coffee_related + ['cocoa', 'cacao'])

        if has_coffee_context and is_generic_bean and score < 98:
            return False

        # Reverse check: if match is coffee-related but ingredient is just "bean", also reject
        match_has_coffee = any(word in match_lower for word in coffee_related + ['cocoa', 'cacao'])
        ingredient_is_generic_bean = any(word in ingredient_lower for word in bean_related) and not any(word in ingredient_lower for word in coffee_related + ['cocoa', 'cacao'])

        if match_has_coffee and ingredient_is_generic_bean and score < 98:
                return False

        return True

    def check_product_ingredients(self, product: Dict[str, Any], force_ai: bool = False) -> Dict[str, Any]:
        """
        Check ingredients for a single product with AI fallback.

        Args:
            product: Product data from Supabase
            force_ai: If True, always attempt AI parsing and prefer AI results

        Returns:
            Dictionary with matching results
        """
        product_name = product.get('name', 'Unknown Product')
        specs = self._load_specs(product)

        self.stats['products_processed'] += 1

        # AI PARSED
        # If product was already parsed by AI previously, reuse stored results to avoid re-processing
        reused = None
        try:
            parsed_prev = specs.get('parsed_ingredients', {})
            if isinstance(parsed_prev, dict) and parsed_prev.get('ai_generated'):
                prev_extracted = parsed_prev.get('extracted_ingredients', []) or []
                prev_matches = parsed_prev.get('matches', []) or []
                # Consider only visible matches when comparing counts
                visible_prev_matches = []
                for m in prev_matches:
                    data = (m.get('data') or {})
                    if data.get('visible', True):
                        visible_prev_matches.append(m)
                if prev_extracted and len(visible_prev_matches) == len(prev_extracted):
                    # Fully matched previously with AI-generated results → reuse, skip AI calls
                    reused = self._reuse_parsed_ai_results(specs, product_name)
        except Exception:
            reused = None
        if reused is not None:
            return reused

        ingredients_text = specs.get('ingredients', '')
        extracted_ingredients = []
        source = 'none'
        force_ai_enabled = bool(force_ai and self.use_ai_fallback and self.ai_parser)
        if force_ai and not force_ai_enabled:
            print("🤖 Force AI parsing requested but AI fallback is disabled or AI parser unavailable; proceeding without force.")

        # Try to extract ingredients from specifications first
        if ingredients_text:
            print(f"📋 Found ingredients text: {ingredients_text[:100]}{'...' if len(ingredients_text) > 100 else ''}")
            extracted_ingredients = self.extract_ingredients_from_text(ingredients_text)
            source = 'specifications'
            self.stats['products_with_ingredients'] += 1

        # Force AI parsing if requested (overrides specification extraction)
        if force_ai_enabled:
            print("🤖 Force AI parsing enabled – using AI results.")
            description = specs.get('description', '') or product.get('description', '')
            ai_ings, ai_error = self._try_ai(product_name, description, ingredients_text=ingredients_text if ingredients_text else None)
            if ai_ings:
                extracted_ingredients = ai_ings
                source = 'ai_parser'
                print(f"   ✅ AI (forced) extracted {len(extracted_ingredients)} ingredients")
            else:
                error_msg = f"   ❌ Forced AI parsing failed; falling back to extracted text"
                if ai_error:
                    error_msg += f"\n   ⚠️  AI Error: {ai_error}"
                else:
                    error_msg += "\n   ⚠️  AI returned no ingredients (empty response or parsing failed)"
                print(error_msg)
                force_ai_enabled = False  # Allow normal fallback logic below

        # If no ingredients found and AI fallback is enabled, try AI
        if not extracted_ingredients and self.use_ai_fallback and self.ai_parser:
            print(f"🤖 No ingredients found, trying AI parsing for: {product_name}")
            description = specs.get('description', '') or product.get('description', '')
            ai_ings, ai_error = self._try_ai(product_name, description, ingredients_text=None)
            source = 'ai_parser'
            if ai_ings:
                extracted_ingredients = ai_ings
                print(f"   ✅ AI extracted {len(extracted_ingredients)} ingredients")
            else:
                error_msg = "   ❌ AI could not extract ingredients"
                if ai_error:
                    error_msg += f"\n   ⚠️  AI Error: {ai_error}"
                else:
                    error_msg += " (empty response or parsing failed)"
                print(error_msg)

        # First pass matching (local counters, no stats yet)
        matches, nova_scores, matched_count, not_matched_count = self._compute_matches(extracted_ingredients)

        # If we extracted ingredients but matched none, try AI as a secondary fallback
        # IMPORTANT: If ingredients_text exists, use it instead of product name (much better results)
        if extracted_ingredients and not force_ai_enabled and matched_count == 0 and self.use_ai_fallback and self.ai_parser:
            print("🤖 No fuzzy matches found, trying AI parsing to improve ingredient list")
            description = specs.get('description', '') or product.get('description', '')
            # Use ingredients_text if available (better than product name), otherwise fall back to product name
            ai_ings, ai_error = self._try_ai(product_name, description, ingredients_text=ingredients_text if ingredients_text else None)
            source = 'ai_parser'
            if ai_ings:
                extracted_ingredients = ai_ings
                print(f"   ✅ AI provided {len(extracted_ingredients)} ingredients; re-running matching")
                # Recompute matches with AI ingredients
                matches, nova_scores, matched_count, not_matched_count = self._compute_matches(extracted_ingredients)
            else:
                error_msg = "   ❌ AI could not improve ingredient extraction"
                if ai_error:
                    error_msg += f"\n   ⚠️  AI Error: {ai_error}"
                else:
                    error_msg += " (empty response or parsing failed)"
                print(error_msg)

        # Optionally insert unmatched ingredients into DB (regardless of source)
        # If ingredients were extracted but not matched, they should be added to DB
        if extracted_ingredients and (matched_count < len(extracted_ingredients)):
            matched_names_preview = {m['matched_name'].lower().strip() for m in matches}
            matched_originals_preview = {m.get('original', '').lower().strip() for m in matches if m.get('original')}
            unmatched_preview = [
                ing for ing in extracted_ingredients
                if ing.lower().strip() not in matched_names_preview
                and ing.lower().strip() not in matched_originals_preview
            ]
            print(f"   📦 Unmatched ingredients candidates: {len(unmatched_preview)}")
            for ing in unmatched_preview:
                print(f"      • {ing}")
            cleanup = self._auto_insert_unmatched(extracted_ingredients, matches)
            rejected_norms = cleanup.get('rejected', [])
            resolved_duplicates = cleanup.get('resolved_duplicates', [])
            if rejected_norms:
                # Remove AI-rejected/blacklisted items from extracted list
                before_len = len(extracted_ingredients)
                extracted_ingredients = [
                    ing for ing in extracted_ingredients
                    if ing and ing.lower().strip() not in set(rejected_norms)
                ]
                if len(extracted_ingredients) != before_len:
                    print(f"   🧹 Removed {before_len - len(extracted_ingredients)} AI-rejected/blacklisted items from extracted list")
            # Recompute matches and nova scores with cleaned list
            if rejected_norms or resolved_duplicates:
                matches, nova_scores, matched_count, not_matched_count = self._compute_matches(extracted_ingredients)
            # After recompute, merge resolved duplicates (manual matches) so they count
            if resolved_duplicates:
                print(f"   🔗 Resolved {len(resolved_duplicates)} duplicates as matches")
                # Add any resolved duplicate match that isn't already present
                existing_keys = {(m.get('matched_name') or '').lower().strip() for m in matches}
                for dm in resolved_duplicates:
                    key = (dm.get('matched_name') or '').lower().strip()
                    if key and key not in existing_keys:
                        matches.append(dm)
                        existing_keys.add(key)
                        matched_count += 1
                        # Track NOVA if available
                        ds = (dm.get('data') or {}).get('nova_score')
                        if isinstance(ds, int):
                            nova_scores.append(ds)

        # Now safely update stats once based on final lists
        self.stats['total_ingredients_found'] += len(extracted_ingredients)
        self.stats['ingredients_matched'] += matched_count
        self.stats['ingredients_not_matched'] += not_matched_count
        for score in nova_scores:
            if score in self.stats['nova_scores']:
                self.stats['nova_scores'][score] += 1

        # Update AI stats if available
        if self.ai_parser:
            self.stats['ai_stats'] = self.ai_parser.get_stats()

        return {
            'product_name': product_name,
            'ingredients_text': ingredients_text,
            'extracted_ingredients': extracted_ingredients,
            'matches': matches,
            'nova_scores': nova_scores,
            'source': source,
            'ai_generated': source == 'ai_parser'
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset all statistics."""
        self.stats = {
            'products_processed': 0,
            'products_with_ingredients': 0,
            'products_with_ai_ingredients': 0,
            'total_ingredients_found': 0,
            'ingredients_matched': 0,
            'ingredients_not_matched': 0,
            'nova_scores': {1: 0, 2: 0, 3: 0, 4: 0},
            'ai_stats': {}
        }

        if self.ai_parser:
            self.ai_parser.reset_stats()

def main():
    """Test the enhanced Supabase ingredients checker with AI fallback."""
    try:
        # Test without AI first to check basic functionality
        print("🧪 Testing Enhanced Supabase Ingredients Checker")
        print("=" * 60)

        # Test 1: Without AI fallback
        print("\n1️⃣ Testing without AI fallback:")
        checker_no_ai = SupabaseIngredientsChecker(use_ai_fallback=False)

        test_products = [
            {
                'name': 'Lapte UHT 3.5% grăsime',
                'specifications': {'ingredients': 'lapte, vitamina d3'}  # Has ingredients
            },
            {
                'name': 'Pâine albă Auchan',
                'specifications': {'ingredients': ''}  # No ingredients
            }
        ]

        for product in test_products:
            print(f"\n📦 Product: {product['name']}")
            result = checker_no_ai.check_product_ingredients(product)

            print(f"   Source: {result['source']}")
            print(f"   Ingredients: {result['extracted_ingredients']}")
            print(f"   Matches: {len(result['matches'])}")
            print(f"   NOVA scores: {result['nova_scores']}")
            print(f"   AI Generated: {result['ai_generated']}")

        print(f"\n📊 Statistics (no AI): {checker_no_ai.get_stats()}")

        # Test 2: With AI fallback (if API key is available)
        print("\n2️⃣ Testing with AI fallback:")
        try:
            checker_with_ai = SupabaseIngredientsChecker(use_ai_fallback=True)

            for product in test_products:
                print(f"\n📦 Product: {product['name']}")
                result = checker_with_ai.check_product_ingredients(product)

                print(f"   Source: {result['source']}")
                print(f"   Ingredients: {result['extracted_ingredients']}")
                print(f"   Matches: {len(result['matches'])}")
                print(f"   NOVA scores: {result['nova_scores']}")
                print(f"   AI Generated: {result['ai_generated']}")

            print(f"\n📊 Statistics (with AI): {checker_with_ai.get_stats()}")

        except Exception as ai_error:
            print(f"⚠️  AI test skipped: {str(ai_error)}")
            print("   (This is expected if OPENAI_API_KEY is not set)")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in environment variables.")
        sys.exit(1)

if __name__ == "__main__":
    main()
