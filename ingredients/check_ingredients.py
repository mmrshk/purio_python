#!/usr/bin/env python3
"""
Ingredients checker utility class for processing product ingredients.

This class:
1. Loads the ingredients CSV file with Romanian translations
2. Uses fuzzy search to match ingredients from products with the CSV
3. Returns NOVA score distributions for ingredient analysis
"""

import os
import sys
import csv
import re
from typing import List, Dict, Any, Optional, Tuple
from fuzzywuzzy import process

class IngredientsChecker:
    def __init__(self, csv_path: str = "ingredients_clean.csv"):
        """
        Initialize the ingredients checker.
        
        Args:
            csv_path: Path to the ingredients CSV file
        """
        self.csv_path = csv_path
        
        # Load ingredients from CSV
        self.ingredients_data = self._load_ingredients_csv()
        
        # Statistics
        self.stats = {
            'products_processed': 0,
            'products_with_ingredients': 0,
            'total_ingredients_found': 0,
            'ingredients_matched': 0,
            'ingredients_not_matched': 0,
            'nova_scores': {1: 0, 2: 0, 3: 0, 4: 0}
        }
    
    def _load_ingredients_csv(self) -> Dict[str, Dict[str, Any]]:
        """
        Load ingredients from CSV file.
        
        Returns:
            Dictionary with ingredient names as keys and data as values
        """
        ingredients = {}
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    ingredient_name = row['name'].lower().strip()
                    ingredient_ro = row['name_ro'].lower().strip()
                    nova_score = int(row['nova_score'])
                    
                    # Store both English and Romanian versions
                    ingredients[ingredient_name] = {
                        'name': row['name'],
                        'name_ro': row['name_ro'],
                        'nova_score': nova_score
                    }
                    ingredients[ingredient_ro] = {
                        'name': row['name'],
                        'name_ro': row['name_ro'],
                        'nova_score': nova_score
                    }
            
            print(f"Loaded {len(ingredients)//2} ingredients from CSV (English + Romanian)")
            return ingredients
            
        except FileNotFoundError:
            print(f"Error: Ingredients CSV file not found at {self.csv_path}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading ingredients CSV: {str(e)}")
            sys.exit(1)
    
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
                    part not in ['apa', 'water', 'suc', 'juice', 'concentrat', 'concentrate', 'agent', 'acidifiant', 'arome', 'indulcitori', 'corector', 'conservanti', 'stabilizatori', 'coloranti', 'emulgatori', 'dioxid', 'carbon', 'acid', 'esteri', 'glicerici', 'rasinilor', 'lemn', 'contine', 'sursa', 'fenilalamina']):
                    ingredients.append(part)
        
        return list(set(ingredients))  # Remove duplicates
    
    def fuzzy_match_ingredient(self, ingredient: str, threshold: int = 90) -> Optional[Dict[str, Any]]:
        """
        Use fuzzy matching to find the best match for an ingredient.
        
        Args:
            ingredient: Ingredient to match
            threshold: Minimum similarity score (0-100)
            
        Returns:
            Matched ingredient data or None
        """
        if not ingredient or len(ingredient) < 2:
            return None
        
        ingredient_lower = ingredient.lower().strip()
        
        # Clean up the ingredient text
        ingredient_lower = re.sub(r'[^\w\s]', ' ', ingredient_lower)  # Remove special chars
        ingredient_lower = re.sub(r'\s+', ' ', ingredient_lower).strip()  # Normalize spaces
        
        # Skip very short or non-ingredient words
        if len(ingredient_lower) < 3:
            return None
            
        # Skip common non-ingredient words
        skip_words = {
            'apa', 'water', 'suc', 'juice', 'concentrat', 'concentrate', 'agent', 'acidifiant', 
            'arome', 'indulcitori', 'corector', 'conservanti', 'stabilizatori', 'coloranti', 
            'emulgatori', 'dioxid', 'carbon', 'acid', 'esteri', 'glicerici', 'rasinilor', 
            'lemn', 'contine', 'sursa', 'fenilalamina', 'potasiu', 'sodiu', 'calciu', 
            'magneziu', 'fosfat', 'carbonat', 'bicarbonat', 'nitrit', 'nitrat', 'benzoat',
            'sorbat', 'propionat', 'galat', 'glutamat', 'inosinat', 'guanylat', 'ribonucleotide',
            'alginat', 'carragenan', 'agar', 'guma', 'arabica', 'xantan', 'guar', 'locust',
            'tara', 'gellan', 'celuloză', 'metilceluloză', 'hidroxipropil', 'carboximetilceluloză',
            'microcristalină', 'praf', 'fibră', 'gel', 'ester', 'eter', 'acetat', 'propionat',
            'butirat', 'valerat', 'caproat', 'caprilat', 'caprat', 'laurat', 'miristat',
            'palmitat', 'stearat', 'oleat', 'linoleat', 'linolenat', 'arachidonat',
            'docosahexaenoat', 'eicosapentaenoat', 'docosapentaenoat', 'eicosatetraenoat',
            'docosatetraenoat', 'eicosatrienoat', 'docosatrienoat', 'eicosadienoat',
            'docosadienoat', 'eicosamonoeenoat', 'docosamonoeenoat', 'eicosanoat',
            'docosanoat', 'tetracosanoat', 'hexacosanoat', 'octacosanoat', 'triacontanoat',
            'dotriacontanoat', 'tetratriacontanoat', 'hexatriacontanoat', 'octatriacontanoat',
            'tetracontanoat', 'dotetracontanoat', 'tetratetracontanoat', 'hexatetracontanoat',
            'octatetracontanoat', 'pentacontanoat', 'dopentacontanoat', 'tetrapentacontanoat',
            'hexapentacontanoat', 'octapentacontanoat', 'hexacontanoat', 'dohexacontanoat',
            'tetrahexacontanoat', 'hexahexacontanoat', 'octahexacontanoat', 'heptacontanoat',
            'doheptacontanoat', 'tetraheptacontanoat', 'hexaheptacontanoat', 'octaheptacontanoat',
            'octacontanoat', 'dooctacontanoat', 'tetraoctacontanoat', 'hexaoctacontanoat',
            'octaoctacontanoat', 'nonacontanoat', 'dononacontanoat', 'tetranonacontanoat',
            'hexanonacontanoat', 'octanonacontanoat', 'hectanoat', 'dohectanoat',
            'tetrahectanoat', 'hexahectanoat', 'octahectanoat'
        }
        
        if ingredient_lower in skip_words:
            return None
        
        # Try exact word matching first
        for key in self.ingredients_data.keys():
            if ingredient_lower == key.lower():
                return {
                    'matched_name': key,
                    'data': self.ingredients_data[key],
                    'score': 100,
                    'original': ingredient,
                    'method': 'exact_match'
                }
        
        # Then try fuzzy matching with higher threshold and word-based matching
        matches = process.extractBests(
            ingredient_lower,
            self.ingredients_data.keys(),
            score_cutoff=threshold,
            limit=5  # Get top 5 matches for better filtering
        )
        
        if matches:
            # Filter out obviously wrong matches
            valid_matches = []
            for match, score in matches:
                # Check if the match makes sense
                if self._is_valid_match(ingredient_lower, match, score):
                    valid_matches.append((match, score))
            
            if valid_matches:
                # Prioritize shorter, more specific matches over longer compound names
                # This prevents "zahăr" from matching "sugar apple" when "sugar" exists
                best_match = valid_matches[0]
                for match, score in valid_matches:
                    # If we have a shorter match with similar score, prefer it
                    if (len(match.split()) < len(best_match[0].split()) and 
                        score >= best_match[1] - 2):  # Allow 2 point difference
                        best_match = (match, score)
                
                # CRITICAL: For lecithin, prioritize the specific lecithin match
                # "lecitina de soia" should match "soy lecithin", not "soybean"
                if 'lecitina' in ingredient_lower:
                    for match, score in valid_matches:
                        if 'lecithin' in match.lower() and score >= best_match[1] - 5:  # Allow 5 point difference for lecithin
                            best_match = (match, score)
                            break
                
                # CRITICAL: For sugar, prioritize exact word matches
                # "zahăr" should match "sugar", not "sugar apple"
                if ingredient_lower == 'zahăr' or ingredient_lower == 'zahar':
                    for match, score in valid_matches:
                        if match.lower() == 'sugar' and score >= best_match[1] - 5:  # Allow 5 point difference for sugar
                            best_match = (match, score)
                            break
                
                return {
                    'matched_name': best_match[0],
                    'data': self.ingredients_data[best_match[0]],
                    'score': best_match[1],
                    'original': ingredient,
                    'method': 'fuzzy_match'
                }
        
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
        food_indicators = {
            'grepfruit', 'grapefruit', 'portocală', 'orange', 'lămâie', 'lemon',
            'morcov', 'carrot', 'cartof', 'potato', 'roșie', 'tomato', 'ceapă', 'onion',
            'usturoi', 'garlic', 'piper', 'pepper', 'ardei', 'chili', 'boia', 'paprika'
        }
        
        for indicator in food_indicators:
            if indicator in ingredient_words:
                # If ingredient mentions a specific food, match should be related
                if indicator not in match_words and score < 95:
                    return False
        
        # Check for additive vs food mismatches
        additive_indicators = {
            'acid', 'acidic', 'citric', 'malic', 'tartaric', 'fumaric', 'adipic',
            'succinic', 'gluconic', 'lactic', 'acetic', 'fosforic', 'sulfuric',
            'clorhidric', 'hidroxid', 'carbonat', 'bicarbonat', 'fosfat', 'glutamat',
            'inosinat', 'guanylat', 'ribonucleotide', 'alginat', 'carragenan',
            'agar', 'guma', 'xantan', 'guar', 'locust', 'tara', 'gellan',
            'celuloză', 'metilceluloză', 'carboximetilceluloză', 'benzoat',
            'sorbat', 'propionat', 'nitrit', 'nitrat', 'aspartam', 'sacharină',
            'acesulfam', 'sucraloză', 'neotam', 'advantam', 'ciclamat'
        }
        
        food_indicators = {
            'măr', 'apple', 'banană', 'banana', 'portocală', 'orange', 'strugure',
            'grape', 'căpșună', 'strawberry', 'afină', 'blueberry', 'zmeură',
            'raspberry', 'mură', 'blackberry', 'vișină', 'cherry', 'piersică',
            'peach', 'pară', 'pear', 'prună', 'plum', 'caisă', 'apricot',
            'nectarină', 'nectarine', 'mango', 'ananas', 'pineapple', 'kiwi',
            'papaya', 'guava', 'fructul', 'fruit', 'roșie', 'tomato', 'castravete',
            'cucumber', 'morcov', 'carrot', 'ceapă', 'onion', 'usturoi', 'garlic',
            'cartof', 'potato', 'cartof dulce', 'sweet potato', 'ardei', 'pepper',
            'broccoli', 'conopidă', 'cauliflower', 'varză', 'cabbage', 'spanac',
            'spinach', 'salata', 'lettuce', 'rucola', 'arugula', 'creson',
            'watercress', 'sparanghel', 'asparagus', 'anghinare', 'artichoke',
            'țelină', 'celery', 'fenicul', 'fennel', 'praz', 'leek', 'șalotă',
            'shallot', 'arpagic', 'chive', 'orez', 'rice', 'grâu', 'wheat',
            'ovăz', 'oats', 'orz', 'barley', 'quinoa', 'mei', 'millet',
            'hrișcă', 'buckwheat', 'secară', 'rye', 'sorg', 'sorghum',
            'amaranth', 'teff', 'alac', 'spelt', 'kamut', 'farro', 'freekeh',
            'bulgur', 'couscous', 'polenta', 'grits', 'porumb', 'corn',
            'popcorn', 'porumb dulce', 'sweet corn', 'migdală', 'almond',
            'nucă', 'walnut', 'caju', 'cashew', 'arahidă', 'peanut',
            'pistachiu', 'pistachio', 'pecan', 'macadamia', 'alună', 'hazelnut',
            'castană', 'chestnut', 'semințe', 'seed', 'fasole', 'bean',
            'linte', 'lentil', 'năut', 'chickpea', 'soia', 'soybean',
            'mazăre', 'pea', 'lapte', 'milk', 'smântână', 'cream', 'ou',
            'egg', 'pui', 'chicken', 'vită', 'beef', 'porc', 'pork',
            'miel', 'lamb', 'curcan', 'turkey', 'pește', 'fish', 'somon',
            'salmon', 'ton', 'tuna', 'cod', 'creveți', 'shrimp', 'rac',
            'crab', 'homar', 'lobster', 'midii', 'mussel', 'scoci', 'clam',
            'stridie', 'oyster', 'viezure', 'scallop', 'calamar', 'squid',
            'caracatiță', 'octopus', 'sepie', 'cuttlefish', 'melc', 'snail'
        }
        
        ingredient_is_additive = any(indicator in ingredient_words for indicator in additive_indicators)
        match_is_additive = any(indicator in match_words for indicator in additive_indicators)
        ingredient_is_food = any(indicator in ingredient_words for indicator in food_indicators)
        match_is_food = any(indicator in match_words for indicator in food_indicators)
        
        # Don't match additives with foods unless very high similarity
        if ingredient_is_additive and match_is_food and score < 95:
            return False
        if ingredient_is_food and match_is_additive and score < 95:
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
    """Main function to run the ingredients checker."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check ingredients from CSV file')
    parser.add_argument('--csv-path', default='ingredients_clean.csv', 
                       help='Path to ingredients CSV file')
    
    args = parser.parse_args()
    
    try:
        checker = IngredientsChecker(args.csv_path)
        print("Ingredients checker initialized successfully!")
        print(f"Loaded {len(checker.ingredients_data)//2} ingredients from CSV")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
