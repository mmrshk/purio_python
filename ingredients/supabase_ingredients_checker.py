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
from typing import List, Dict, Any, Optional, Tuple
from fuzzywuzzy import process
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

class SupabaseIngredientsChecker:
    def __init__(self):
        """
        Initialize the Supabase ingredients checker.
        """
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials are not set in environment variables.")
        
        self.supabase = create_client(supabase_url, supabase_key)
        
        # Load ingredients from Supabase
        self.ingredients_data = self._load_ingredients_from_supabase()
        
        # Statistics
        self.stats = {
            'products_processed': 0,
            'products_with_ingredients': 0,
            'total_ingredients_found': 0,
            'ingredients_matched': 0,
            'ingredients_not_matched': 0,
            'nova_scores': {1: 0, 2: 0, 3: 0, 4: 0}
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
                name_ro = ingredient.get('name_ro', '').lower().strip()
                nova_score = ingredient.get('nova_score', 1)
                
                # Store both English and Romanian versions
                if name:
                    ingredients[name] = {
                        'id': ingredient_id,
                        'name': ingredient.get('name'),
                        'name_ro': ingredient.get('name_ro'),
                        'nova_score': nova_score
                    }
                
                if name_ro:
                    ingredients[name_ro] = {
                        'id': ingredient_id,
                        'name': ingredient.get('name'),
                        'name_ro': ingredient.get('name_ro'),
                        'nova_score': nova_score
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
            # Get the best matches
            matches = process.extractBests(
                ingredient_lower,
                self.ingredients_data.keys(),
                limit=5  # Get top 5 matches for better filtering
            )
            
            if matches:
                best_match = matches[0]
                score = best_match[1]
                
                if score >= threshold:
                    # Additional validation
                    if self._is_valid_match(ingredient_lower, best_match[0], score):
                        return {
                            'matched_name': best_match[0],
                            'data': self.ingredients_data[best_match[0]],
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
        
        return True
    
    def check_product_ingredients(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check ingredients for a single product.
        
        Args:
            product: Product data from Supabase
            
        Returns:
            Dictionary with matching results
        """
        product_name = product.get('name', 'Unknown Product')
        specs = product.get('specifications', {})
        
        if not isinstance(specs, dict):
            return {
                'product_name': product_name,
                'ingredients_text': None,
                'extracted_ingredients': [],
                'matches': [],
                'nova_scores': []
            }
        
        ingredients_text = specs.get('ingredients', '')
        if not ingredients_text:
            return {
                'product_name': product_name,
                'ingredients_text': None,
                'extracted_ingredients': [],
                'matches': [],
                'nova_scores': []
            }
        
        # Extract ingredients from text
        extracted_ingredients = self.extract_ingredients_from_text(ingredients_text)
        
        # Match each ingredient
        matches = []
        nova_scores = []
        
        for ingredient in extracted_ingredients:
            match = self.fuzzy_match_ingredient(ingredient)
            if match:
                matches.append(match)
                nova_scores.append(match['data']['nova_score'])
                self.stats['ingredients_matched'] += 1
                self.stats['nova_scores'][match['data']['nova_score']] += 1
            else:
                self.stats['ingredients_not_matched'] += 1
        
        self.stats['total_ingredients_found'] += len(extracted_ingredients)
        
        return {
            'product_name': product_name,
            'ingredients_text': ingredients_text,
            'extracted_ingredients': extracted_ingredients,
            'matches': matches,
            'nova_scores': nova_scores
        }

def main():
    """Main function to test the Supabase ingredients checker."""
    try:
        checker = SupabaseIngredientsChecker()
        print("Supabase ingredients checker initialized successfully!")
        print(f"Loaded {len(checker.ingredients_data)//2} ingredients from Supabase")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
