#!/usr/bin/env python3
"""
AI-based ingredients parser for extracting ingredients from product names.

This class:
1. Uses OpenAI GPT-3.5-turbo to infer ingredients from product names
2. Acts as a fallback when no ingredients text is available
3. Returns structured results compatible with existing ingredient checking system
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

try:
    from .ingredients_inserter import IngredientsInserter
    from .ingredient_blacklist import is_blacklisted
except ImportError:
    from ingredients_inserter import IngredientsInserter
    from ingredient_blacklist import is_blacklisted

load_dotenv()

class AIIngredientsParser:
    def __init__(self, model: str = "gpt-3.5-turbo", max_tokens: int = 500,
                 auto_insert_ingredients: bool = False):
        """
        Initialize the AI ingredients parser.

        Args:
            model: OpenAI model to use (default: gpt-3.5-turbo)
            max_tokens: Maximum tokens for AI response
            auto_insert_ingredients: Whether to automatically insert new ingredients to Supabase
        """
        self.model = model
        self.max_tokens = max_tokens
        self.auto_insert_ingredients = auto_insert_ingredients

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        self.client = OpenAI(api_key=api_key)

        # Initialize ingredients inserter if auto-insert is enabled
        self.ingredients_inserter = None
        if auto_insert_ingredients:
            try:
                self.ingredients_inserter = IngredientsInserter()
                print("🔗 Ingredients inserter initialized - new ingredients will be added to database")
            except Exception as e:
                print(f"⚠️  Failed to initialize ingredients inserter: {str(e)}")
                print("   Continuing without auto-insertion...")
                self.auto_insert_ingredients = False

        # Statistics
        self.stats = {
            'ai_requests_made': 0,
            'ai_requests_successful': 0,
            'ai_requests_failed': 0,
            'ingredients_extracted': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }

        # Precompiled helpers for cleaning
        self.label_prefix_patterns = [
            r'^(?:stabilizatori?|stabilizers?)[:\-]?\s*',
            r'^(?:stabilizator|stabilizer)[:\-]?\s*',
            r'^(?:antioxidanti?|antioxidants?)[:\-]?\s*',
            r'^(?:acidifianti|acidity\s+regulators?|acidity\s+regulator)[:\-]?\s*',
            r'^(?:agent(?:i)?\s+de\s+[a-zăâîșț\- ]+?)[:\-]?\s*',
            r'^(?:indulcitori?|indulcitori\s+artificiali|sweeteners?)[:\-]?\s*',
            r'^(?:coloranti?|colorings?)[:\-]?\s*',
            r'^(?:flavorings?|flavoring|arome?|aroma)[:\-]?\s*',
            r'^(?:smoke\s+flavoring)[:\-]?\s*',
            r'^(?:stabilizers?)[:\-]?\s*',
        ]

    def parse_ingredients_from_name(self, product_name: str, product_description: str = None) -> Dict[str, Any]:
        """
        Parse ingredients from product name using AI.

        Args:
            product_name: Name of the product
            product_description: Optional product description for additional context

        Returns:
            Dictionary with parsing results
        """
        try:
            print(f"🤖 Using AI to parse ingredients from: {product_name}")

            # Prepare context for AI
            context = product_name
            if product_description:
                context += f"\nDescription: {product_description}"

            # Create AI prompt
            prompt = self._create_ingredient_prompt(context)

            # Make AI request
            response = self._make_ai_request(prompt)

            if response:
                # Parse AI response
                ingredients = self._parse_ai_response(response)

                self.stats['ai_requests_successful'] += 1
                self.stats['ingredients_extracted'] += len(ingredients)

                print(f"   ✅ AI extracted {len(ingredients)} ingredients")

                # Auto-insert ingredients to database if enabled
                insertion_results = []
                if self.auto_insert_ingredients and self.ingredients_inserter and ingredients:
                    insertion_results = self._insert_ingredients_to_database(ingredients)

                return {
                    'ingredients_text': f"AI-generated from product name: {product_name}",
                    'extracted_ingredients': ingredients,
                    'ai_generated': True,
                    'source': 'ai_parser',
                    'insertion_results': insertion_results
                }
            else:
                self.stats['ai_requests_failed'] += 1
                print("   ❌ AI request failed")
                return {
                    'ingredients_text': None,
                    'extracted_ingredients': [],
                    'ai_generated': False,
                    'source': 'ai_parser_failed'
                }

        except Exception as e:
            print(f"   ❌ AI parsing error: {str(e)}")
            self.stats['ai_requests_failed'] += 1
            return {
                'ingredients_text': None,
                'extracted_ingredients': [],
                'ai_generated': False,
                'source': 'ai_parser_error',
                'error': str(e)
            }

    def _create_ingredient_prompt(self, context: str) -> str:
        """
        Create a prompt for AI to extract ingredients.

        Args:
            context: Product name/description or ingredients list text

        Returns:
            Formatted prompt for AI
        """
        # Detect if context is an ingredients list or product name
        is_ingredients_list = context.strip().lower().startswith('ingredients list:')

        if is_ingredients_list:
            # Context is an ingredients list - parse it directly
            return f"""You are a food ingredient expert. Parse the following ingredients list and extract individual ingredient names.

{context}

⭐ CRITICAL RULE: An ingredient is a single, specific substance that can legally appear exactly as written on an ingredient list. Products and categories are NOT ingredients.

✔️ INGREDIENTS: "dried tomatoes", "black pepper", "sunflower seed oil", "grape juice", "hydrolyzed vegetable protein", "soy fiber", "hazelnut pieces", "whey powder"
❌ PRODUCTS (NOT ingredients): "bread", "pepperoni", "tofu", "apricot jam", "pickled cucumbers", "yogurt", "pale lager", "chocolate sauce", "pasta de tomate", "branza mozzarella", "sunca", "salam", "paine", "iaurt", "biscuiti", "ciocolată", "dulceata de caise"
❌ CATEGORIES (NOT ingredients): "herbs", "berries", "vegetables", "meat", "oils", "mushrooms", "wild berry", "fruit puree", "verdețuri", "fructe de padure", "uleiuri", "ciuperci"

Please extract ONLY the edible ingredients and additives from the list above.
- Normalize ingredient names (e.g., "frunze de ceai verde" → "green tea leaves" or "ceai verde")
- Extract percentages and quantities separately, do not include them in ingredient names
- If an ingredient is listed with a percentage (e.g., "frunze de ceai verde 55%"), extract just "ceai verde" or "green tea"
- Split compound ingredients appropriately (e.g., "frunze de lotus" → "lotus leaves" or "lotus")
- Exclude non-ingredient terms like: air, sun, time, heat, light, temperature, drying, curing, aging
- NEVER include quantities or measurements as ingredients (e.g., "5mg", "100g", "2%", "10ml" are NOT ingredients)
- Remove functional labels such as "stabilizator:", "antioxidant:", "agent de afanare:", "sweeteners", "flavorings", "colorings", "mix", "blend", "atmosfera protectoare"
- Ignore marketing descriptors or sensory adjectives (e.g., "picante", "gust natural", "gust echilibrat", "intensitate", "blend special", "smarties", "corsicane", "aer si soare", "o delicatese speciala")
- Exclude packaging, container, or certification terms (e.g., "caserola", "sticla", "certificat ecologic", "norme reglementate", "inspectii regulate")
- Exclude time or maturation phrases (e.g., "timp 11 luni", "maturat 12 luni", "aged 18 months")
- Exclude farming slogans, regions, or origin statements (e.g., "cultivate in mod natural", "regiunea dorsolombosacrala", "puiul fermierului agricola", "vietnam")
- For anatomical meat parts or cuts (e.g., "aripioare", "ciocanele", "spinari", "burta de vita", "pipote"), emit only the base animal ingredient ("pui", "vita", "rata") once and skip the cut name
- When a label is followed by an actual ingredient (e.g., "stabilizator: trifosfati", "agent de afanare (bicarbonat de amoniu)"), output only the ingredient after the label
- If parentheses contain the real ingredient, include the ingredient inside the parentheses
- When you see spreads or creams like "crema de alune" or "hazelnut cream", output only the base ingredient ("alune", "hazelnut")
- DO NOT output finished products: bread, yogurt, cheese varieties (mozzarella, cheddar, edam, ricotta, etc.), ham, salami, pepperoni, chocolate products, wine, spirits, jam, pickled items, dough, broth, soup, etc. (English and Romanian: "paine", "iaurt", "branza", "sunca", "salam", "ciocolată", "vin", "dulceata", "masa", "bulion", "supa")
- DO NOT output generic categories: herbs, berries, vegetables, meat, oils, mushrooms, sprouts, wild berry, fruit puree, etc. (English and Romanian: "verdețuri", "fructe de padure", "uleiuri", "ciuperci")
- DO NOT output generic/non-specific terms: tea extract, paprika oil, syrup, whole flakes, cereal flakes, etc. (English and Romanian: "extract de ceai", "ulei de paprika", "sirop", "fulgi integrali")
- DO NOT output role-only salts/acid salts or colorants when not tied to a specific food identity (e.g., "sodium polyphosphates", "diphosphates", "potassium citrates", "sodium acetate", "potassium chloride", "calcium carbonate", "calcium lactate", "sodium lactate", "sodium erythorbate", "ammonium bicarbonate", "anthocyanin", "curcumin", "beta-carotene", "processed Eucheuma seaweed")
- DO NOT output additives as ingredients (roles such as emulsifier, stabilizer, colorant, sweetener, preservative, flavoring, raising agent), including E-number additives (E100–E999). Skip items like "emulsifiers", "smoke flavor", "carmine/Beetroot Red/Brilliant Blue FCF", "polyglycerol esters of fatty acids", "proteins from", "protein from".
- Return each ingredient in lowercase, without duplicates

Return ONLY a JSON array of normalized ingredient names, like this:
["ingredient1", "ingredient2", "ingredient3"]

Do not include explanations, just the JSON array. If you cannot determine ingredients, return an empty array: []"""
        else:
            # Context is product name/description - infer ingredients
            return f"""You are a food ingredient expert. Based on the product name and description, extract the most likely ingredients.

Product: {context}

⭐ CRITICAL RULE: An ingredient is a single, specific substance that can legally appear exactly as written on an ingredient list. Products and categories are NOT ingredients.

✔️ INGREDIENTS: "dried tomatoes", "black pepper", "sunflower seed oil", "grape juice", "hydrolyzed vegetable protein", "soy fiber", "hazelnut pieces", "whey powder"
❌ PRODUCTS (NOT ingredients): "bread", "pepperoni", "tofu", "apricot jam", "pickled cucumbers", "yogurt", "pale lager", "chocolate sauce", "pasta de tomate", "branza mozzarella", "sunca", "salam", "paine", "iaurt", "biscuiti", "ciocolată", "dulceata de caise"
❌ CATEGORIES (NOT ingredients): "herbs", "berries", "vegetables", "meat", "oils", "mushrooms", "wild berry", "fruit puree", "verdețuri", "fructe de padure", "uleiuri", "ciuperci"

Please extract ingredients that are most likely to be in this product. Consider:
1. Common ingredients for this type of product
2. Ingredients typically mentioned in product names
3. Standard ingredients for this food category

Important rules:
- Only include edible ingredients or approved food additives (e.g., E-codes), not processes or environmental factors
- Exclude non-ingredients such as: air, sun, time, heat, light, temperature, drying, curing, aging, process descriptions
- Do not infer brand slogans or preparation methods as ingredients
- NEVER include quantities or measurements as ingredients (e.g., "5mg", "100g", "2%", "10ml" are NOT ingredients)
- Remove functional labels such as "stabilizator:", "antioxidant:", "agent de afanare:", "sweeteners", "flavorings", "colorings", "mix", "blend", "atmosfera protectoare"
- Ignore marketing descriptors or sensory adjectives (e.g., "picante", "gust natural", "gust echilibrat", "intensitate", "blend special", "smarties", "corsicane", "aer si soare", "o delicatese speciala")
- Exclude packaging, container, or certification terms (e.g., "caserola", "sticla", "certificat ecologic", "norme reglementate", "inspectii regulate")
- Exclude time or maturation phrases (e.g., "timp 11 luni", "maturat 12 luni", "aged 18 months")
- Exclude farming slogans, regions, or origin statements (e.g., "cultivate in mod natural", "regiunea dorsolombosacrala", "puiul fermierului agricola", "vietnam")
- For anatomical meat parts or cuts (e.g., "aripioare", "ciocanele", "spinari", "burta de vita", "pipote"), emit only the base animal ingredient ("pui", "vita", "rata") once and skip the cut name
- When a label is followed by an actual ingredient (e.g., "stabilizator: trifosfati", "agent de afanare (bicarbonat de amoniu)"), output only the ingredient after the label
- If parentheses contain the real ingredient, include the ingredient inside the parentheses
- When you see spreads or creams like "crema de alune" or "hazelnut cream", output only the base ingredient ("alune", "hazelnut")
- DO NOT output finished products: bread, yogurt, cheese varieties (mozzarella, cheddar, edam, ricotta, etc.), ham, salami, pepperoni, chocolate products, wine, spirits, jam, pickled items, dough, broth, soup, etc. (English and Romanian: "paine", "iaurt", "branza", "sunca", "salam", "ciocolată", "vin", "dulceata", "masa", "bulion", "supa")
- DO NOT output generic categories: herbs, berries, vegetables, meat, oils, mushrooms, sprouts, wild berry, fruit puree, etc. (English and Romanian: "verdețuri", "fructe de padure", "uleiuri", "ciuperci")
- DO NOT output generic/non-specific terms: tea extract, paprika oil, syrup, whole flakes, cereal flakes, etc. (English and Romanian: "extract de ceai", "ulei de paprika", "sirop", "fulgi integrali")
- DO NOT output role-only salts/acid salts or colorants not tied to a specific food identity (e.g., "sodium polyphosphates", "diphosphates", "potassium citrates", "sodium acetate", "potassium chloride", "calcium carbonate", "calcium lactate", "sodium lactate", "sodium erythorbate", "ammonium bicarbonate", "anthocyanin", "curcumin", "beta-carotene", "processed Eucheuma seaweed")
- DO NOT output additives as ingredients (roles such as emulsifier, stabilizer, colorant, sweetener, preservative, flavoring, raising agent), including E-number additives (E100–E999). Skip items like "emulsifiers", "smoke flavor", "carmine/Beetroot Red/Brilliant Blue FCF", "polyglycerol esters of fatty acids", "proteins from", "protein from".
- Return each ingredient in lowercase, without duplicates

Return ONLY a JSON array of ingredient names, like this:
["ingredient1", "ingredient2", "ingredient3"]

Do not include explanations, just the JSON array. If you cannot determine ingredients, return an empty array: []"""

    def _make_ai_request(self, prompt: str) -> Optional[str]:
        """
        Make request to OpenAI API.

        Args:
            prompt: Formatted prompt for AI

        Returns:
            AI response or None if failed
        """
        try:
            self.stats['ai_requests_made'] += 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a food ingredient expert. Always respond with valid JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3  # Lower temperature for more consistent results
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"   ❌ OpenAI API error: {str(e)}")
            return None

    def _strip_leading_labels(self, ingredient: str) -> str:
        """Remove functional labels (e.g., 'stabilizator:', 'agent de ...') from the ingredient string."""
        if not ingredient:
            return ""

        result = ingredient.strip()
        for pattern in self.label_prefix_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        return result.strip(" ,;-:.")

    def _expand_raw_ingredient(self, ingredient: str) -> List[str]:
        """
        Expand a raw ingredient string into candidate segments by handling parentheses and separators.
        """
        if not ingredient or not isinstance(ingredient, str):
            return []

        raw = ingredient.strip()
        if not raw:
            return []

        candidates: List[str] = []

        # Capture parenthetical content (e.g., "agent ... (bicarbonat de amoniu)")
        parenthetical_matches = re.findall(r'\(([^)]+)\)', raw)
        for match in parenthetical_matches:
            inner = match.strip()
            if inner:
                inner = self._strip_leading_labels(inner)
                if inner:
                    candidates.append(inner)
        # Remove parenthetical sections from the original string
        without_parentheses = re.sub(r'\([^)]*\)', '', raw).strip(" ,;")

        # Replace slashes with commas to normalize separators
        normalized = without_parentheses.replace('/', ',')

        # Split by commas or semicolons
        parts = re.split(r'[;,]', normalized)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            part = self._strip_leading_labels(part)
            if part:
                candidates.append(part)

        # Fall back to the raw string if nothing else was produced
        if not candidates and without_parentheses:
            candidates.append(self._strip_leading_labels(without_parentheses))

        # Deduplicate while preserving order
        unique_candidates: List[str] = []
        seen = set()
        for cand in candidates:
            key = cand.lower().strip()
            if key and key not in seen:
                unique_candidates.append(cand)
                seen.add(key)

        print(f"   🔍 Expanded '{ingredient}' into candidates: {unique_candidates}")
        return unique_candidates

    @staticmethod
    def _normalize_output(ingredient: str) -> str:
        """Normalize final ingredient name formatting."""
        if not ingredient:
            return ""
        normalized = ingredient.strip().lower()
        normalized = re.sub(r'\s+', ' ', normalized)
        print(f"   🔄 Normalized ingredient: '{ingredient}' -> '{normalized}'")
        return normalized

    def _parse_ai_response(self, response: str) -> List[str]:
        """
        Parse AI response to extract ingredients list.

        Args:
            response: Raw AI response

        Returns:
            List of extracted ingredients
        """
        try:
            # Clean the response
            response = response.strip()

            # Remove any markdown formatting
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]

            # Parse JSON
            ingredients = json.loads(response)

            if not isinstance(ingredients, list):
                return []

            # Clean and validate ingredients
            cleaned_ingredients: List[str] = []
            seen_normalized = set()
            for ingredient in ingredients:
                if isinstance(ingredient, str):
                    ingredient = ingredient.strip()
                    if ingredient and len(ingredient) > 1:
                        candidates = self._expand_raw_ingredient(ingredient)
                        for candidate in candidates:
                            # Clean the ingredient name (extract from patterns like "fier: 2" -> "fier")
                            cleaned = self._clean_ingredient_name(candidate)
                            if cleaned and len(cleaned) > 1:
                                normalized = self._normalize_output(cleaned)
                                if not normalized:
                                    continue
                                if normalized in seen_normalized:
                                    print(f"   🔁 Duplicate normalized ingredient skipped: {normalized}")
                                    continue
                                # Validate ingredient (check blacklist, quantity-only, etc.)
                                if self._is_valid_ingredient(normalized):
                                    cleaned_ingredients.append(normalized)
                                    seen_normalized.add(normalized)
                                else:
                                    print(f"   ⏭️  Skipping invalid ingredient: {normalized}")

            return cleaned_ingredients

        except json.JSONDecodeError:
            print(f"   ⚠️  Failed to parse AI response as JSON: {response[:100]}...")
            # Fallback: try to extract ingredients using regex
            return self._extract_ingredients_fallback(response)
        except Exception as e:
            print(f"   ⚠️  Error parsing AI response: {str(e)}")
            return []

    def _extract_ingredients_fallback(self, response: str) -> List[str]:
        """
        Fallback method to extract ingredients from malformed AI response.

        Args:
            response: Raw AI response

        Returns:
            List of extracted ingredients
        """
        # Look for quoted strings or comma-separated values
        ingredients = []

        # Try to find quoted strings
        quoted_matches = re.findall(r'"([^"]+)"', response)
        if quoted_matches:
            ingredients.extend(quoted_matches)

        # Try to find comma-separated values
        if not ingredients:
            parts = response.split(',')
            for part in parts:
                part = part.strip().strip('[]"\'')
                if part and len(part) > 1:
                    ingredients.append(part)

        # Clean and filter ingredients
        cleaned_ingredients: List[str] = []
        seen_normalized = set()
        for ing in ingredients[:10]:
            for candidate in self._expand_raw_ingredient(ing):
                cleaned = self._clean_ingredient_name(candidate)
                normalized = self._normalize_output(cleaned)
                if normalized and len(normalized) > 1:
                    if normalized in seen_normalized:
                        continue
                    if self._is_valid_ingredient(normalized):
                        cleaned_ingredients.append(normalized)
                        seen_normalized.add(normalized)
                    else:
                        print(f"   ⏭️  Skipping invalid ingredient: {normalized}")
        return cleaned_ingredients

    def _clean_ingredient_name(self, ingredient: str) -> str:
        """
        Clean ingredient name by extracting the actual ingredient from patterns like:
        - "fier: 2" -> "fier"
        - "zinc: 2" -> "zinc"
        - "alte valori nutritionale: fosfor: 315mg/100g" -> "fosfor"
        - "fosfor: 315mg/100g" -> "fosfor"
        - "flori de tei" -> "tei"
        - "flori de hibiscus" -> "hibiscus"
        - "faina de grau" -> "grau"
        - "grasime vegetala de palmier" -> "palmier"

        Args:
            ingredient: Raw ingredient string

        Returns:
            Cleaned ingredient name
        """
        if not ingredient:
            return ""

        ingredient = ingredient.strip()
        ingredient = self._strip_leading_labels(ingredient)
        ingredient = re.sub(r'\s+', ' ', ingredient)
        ingredient = ingredient.strip(" ,;.-")

        # "crema de X" -> "X"
        match = re.match(r'^crema\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            extracted = re.sub(r'[\s\d\.]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg|/100g|/100ml).*$', '', extracted, flags=re.IGNORECASE)
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "(hazelnut|alune) cream" -> "hazelnut"/"alune"
        match = re.match(r'^([a-zăâîșț\s]+)\s+cream$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and any(keyword in extracted.lower() for keyword in ['hazelnut', 'alune', 'almond', 'peanut', 'pistachio']):
                if not self._is_quantity_only(extracted):
                    return extracted.strip()

        # Pattern 0: Extract from compound descriptions
        # "flori de X" -> "X"
        match = re.match(r'^flori\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Remove quantities if any
            extracted = re.sub(r'[\s\d\.]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg|/100g|/100ml).*$', '', extracted, flags=re.IGNORECASE)
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "frunze de X" or "frunze si flori de X" -> "X"
        match = re.match(r'^frunze(?:\s+si\s+flori)?\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            extracted = re.sub(r'[\s\d\.]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg|/100g|/100ml).*$', '', extracted, flags=re.IGNORECASE)
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "faina de X" or "faina integrala de X" -> "X"
        match = re.match(r'^faina(?:\s+integrala)?\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "grasime vegetala de X" -> "X"
        match = re.match(r'^grasime\s+vegetala\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "nectar de X" -> "X"
        match = re.match(r'^nectar\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "suc de X" -> "X"
        match = re.match(r'^suc\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "pasta de X" -> "X"
        match = re.match(r'^pasta\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "pulpa de X" -> "X"
        match = re.match(r'^pulpa\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "carnea de X" -> "X"
        match = re.match(r'^carnea\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "ficat de X" -> "X"
        match = re.match(r'^ficat\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "radacina de X" -> "X"
        match = re.match(r'^radacina\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Remove parenthetical info like "(liquiritiae radix)"
            extracted = re.sub(r'\s*\([^)]+\)\s*', '', extracted)
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "boabe X" -> "X" (for coffee beans)
        match = re.match(r'^boabe\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # "crupe de X" or "fulgi de X" -> "X"
        match = re.match(r'^(?:crupe|fulgi)\s+de\s+(.+)$', ingredient, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and not self._is_quantity_only(extracted):
                return extracted.strip()

        # Pattern 1: "ingredient: quantity" or "ingredient: 2"
        # Extract the part before the colon if it's followed by numbers/units
        match = re.match(r'^([^:]+?)\s*:\s*[\d\.]+', ingredient)
        if match:
            potential_name = match.group(1).strip()
            # If the extracted name is not a quantity itself, return it
            if potential_name and not self._is_quantity_only(potential_name):
                return potential_name

        # Pattern 2: Complex strings like "alte valori nutritionale: fosfor: 315mg/100g"
        # Extract the ingredient name (usually the last meaningful word before quantities)
        # Look for pattern: "text: ingredient: quantity" or "text: ingredient quantity"
        parts = re.split(r'[:]', ingredient)
        if len(parts) > 1:
            # Skip common Romanian labels at the start
            skip_labels = ['alte valori nutritionale', 'valori nutritionale', 'nutritional values',
                          'alte valori', 'valori', 'nutritional']

            # Get the last part before quantities (usually the actual ingredient)
            for part in reversed(parts):
                part = part.strip()
                part_lower = part.lower()

                # Skip if it's a known label
                if part_lower in skip_labels:
                    continue

                # Remove quantities and units from the end
                part_cleaned = re.sub(r'[\s\d\.]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg|/100g|/100ml).*$', '', part, flags=re.IGNORECASE)
                part_cleaned = part_cleaned.strip()

                # If it's a valid ingredient name (not empty, not quantity-only)
                if part_cleaned and len(part_cleaned) > 1 and not self._is_quantity_only(part_cleaned):
                    # Skip if it's a label
                    if part_cleaned.lower() not in skip_labels:
                        return part_cleaned

        # Pattern 3: Remove quantities and units from the end
        # e.g., "fosfor 315mg/100g" -> "fosfor"
        cleaned = re.sub(r'[\s\d\.]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg|/100g|/100ml).*$', '', ingredient, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Pattern 4: Remove trailing numbers after colon (e.g., "fier: 2" -> "fier")
        cleaned = re.sub(r'\s*:\s*[\d\.\s]+$', '', cleaned)

        return cleaned.strip()

    def _is_quantity_only(self, ingredient: str) -> bool:
        """
        Check if an ingredient is just a quantity/measurement (e.g., "5mg", "100g", "2%").

        Args:
            ingredient: Ingredient name to check

        Returns:
            True if the ingredient is just a quantity/measurement, False otherwise
        """
        if not ingredient:
            return True

        # Remove whitespace and convert to lowercase
        ingredient = ingredient.strip().lower()

        # Pattern 1: Just a number with unit abbreviation at the end (e.g., "5mg", "9mg", "100g")
        # This is the most common pattern
        if re.match(r'^\d+\.?\d*\s*(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg)\s*$', ingredient):
            return True

        # Pattern 2: Starts with numbers and ends with units (e.g., "315mg/100g")
        if re.match(r'^[\d\.\s]+(mg|g|kg|ml|l|cl|dl|%|percent|ppm|ppb|iu|units?|mcg|µg)', ingredient):
            # If there's no meaningful text before the number, it's quantity-only
            if not re.match(r'^[a-z]+', ingredient):
                return True

        # Pattern 3: Just a number (likely a percentage or quantity)
        if re.match(r'^\d+\.?\d*\s*%?\s*$', ingredient):
            return True

        # Pattern 4: Just numbers with slashes or ratios (e.g., "315/100", "2/1")
        if re.match(r'^[\d\.\s/]+$', ingredient):
            return True

        return False

    def _is_valid_ingredient(self, ingredient: str) -> bool:
        """
        Check if an ingredient is valid (not blacklisted, not quantity-only, etc.).

        Args:
            ingredient: Ingredient name to validate

        Returns:
            True if the ingredient is valid, False otherwise
        """
        if not ingredient or len(ingredient) < 2:
            return False

        ingredient_lower = ingredient.lower().strip()

        # Check if it's quantity-only
        if self._is_quantity_only(ingredient_lower):
            return False

        # Check blacklist (uses the external blacklist module)
        if is_blacklisted(ingredient_lower):
            return False

        # Reject if it's too short after cleaning (likely a fragment)
        if len(ingredient_lower) < 2:
            return False

        return True

    def _insert_ingredients_to_database(self, ingredients: List[str]) -> List[Dict[str, Any]]:
        """
        Insert AI-generated ingredients to the database.

        Args:
            ingredients: List of ingredient names to insert

        Returns:
            List of insertion results
        """
        if not self.ingredients_inserter:
            return []

        insertion_results = []

        for ingredient in ingredients:
            try:
                # For AI-generated ingredients, we'll use the same name for both English and Romanian
                # In a real scenario, you might want to translate or use a different approach
                result = self.ingredients_inserter.insert_ingredient(
                    name=ingredient,
                    ro_name=ingredient,  # Using same name for both languages
                    nova_score=None,  # AI-generated ingredients don't have a NOVA score yet
                    created_by="ai_parser",
                    visible=False
                )

                insertion_results.append({
                    'ingredient': ingredient,
                    'result': result
                })

                # Update stats based on result
                if result['success']:
                    if result['action'] == 'inserted':
                        self.stats['ingredients_inserted'] += 1
                        print(f"   💾 Inserted new ingredient: {ingredient}")
                    elif result['action'] == 'skipped':
                        self.stats['ingredients_skipped'] += 1
                        print(f"   ⏭️  Skipped existing ingredient: {ingredient}")
                else:
                    self.stats['ingredients_errors'] += 1
                    print(f"   ❌ Failed to insert ingredient {ingredient}: {result.get('message', 'Unknown error')}")

            except Exception as e:
                self.stats['ingredients_errors'] += 1
                print(f"   ❌ Exception inserting ingredient {ingredient}: {str(e)}")
                insertion_results.append({
                    'ingredient': ingredient,
                    'result': {
                        'success': False,
                        'action': 'error',
                        'reason': 'exception',
                        'error': str(e)
                    }
                })

        return insertion_results

    def get_stats(self) -> Dict[str, Any]:
        """
        Get parser statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_stats(self):
        """Reset parser statistics."""
        self.stats = {
            'ai_requests_made': 0,
            'ai_requests_successful': 0,
            'ai_requests_failed': 0,
            'ingredients_extracted': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }

        # Also reset inserter stats if available
        if self.ingredients_inserter:
            self.ingredients_inserter.reset_stats()


def main():
    """Test the AI ingredients parser with auto-insertion."""
    try:
        # Test with auto-insertion enabled
        parser = AIIngredientsParser(auto_insert_ingredients=True)

        # Test with sample products
        test_products = [
            "Pâine albă Auchan",
            "Lapte UHT 3.5% grăsime",
            "Branză de vaci 200g",
            "Coca-Cola 2L",
            "Chipsuri cu sare"
        ]

        print("🧪 Testing AI Ingredients Parser with Auto-Insertion")
        print("=" * 60)

        for product in test_products:
            print(f"\n📦 Product: {product}")
            result = parser.parse_ingredients_from_name(product)

            if result['extracted_ingredients']:
                print(f"   ✅ Ingredients: {', '.join(result['extracted_ingredients'])}")

                # Show insertion results if available
                if 'insertion_results' in result and result['insertion_results']:
                    print("   📊 Insertion Results:")
                    for insertion in result['insertion_results']:
                        ingredient = insertion['ingredient']
                        res = insertion['result']
                        if res['success']:
                            if res['action'] == 'inserted':
                                print(f"      💾 {ingredient}: Inserted (ID: {res.get('ingredient_id', 'N/A')})")
                            elif res['action'] == 'skipped':
                                print(f"      ⏭️  {ingredient}: Skipped (already exists)")
                        else:
                            print(f"      ❌ {ingredient}: Failed - {res.get('message', 'Unknown error')}")
            else:
                print("   ❌ No ingredients extracted")

        print(f"\n📊 Parser Statistics: {parser.get_stats()}")

        # Show inserter statistics if available
        if parser.ingredients_inserter:
            print(f"📊 Inserter Statistics: {parser.ingredients_inserter.get_stats()}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure to set OPENAI_API_KEY and Supabase credentials environment variables.")


if __name__ == "__main__":
    main()
