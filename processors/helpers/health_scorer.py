import pandas as pd
import numpy as np
import re
from typing import Dict, Any, Optional, List
import json

class HealthScorer:
    """
    Health scoring system based on the Purio Flatter app methodology.
    
    Scoring ranges:
    - 76-100: Healthy choice (Green)
    - 51-75: Caution (Yellow) 
    - 26-50: Think twice (Orange)
    - 0-25: High risk (Red)
    """
    
    def __init__(self):
        # Define scoring weights and thresholds
        self.scoring_config = {
            'nutrients': {
                'saturated_fat': {'weight': -1, 'max_score': 15, 'unit': 'g', 'divisor': 10},
                'sugar': {'weight': -1.5, 'max_score': 20, 'unit': 'g', 'divisor': 10},
                'salt': {'weight': -2, 'max_score': 10, 'unit': 'g', 'divisor': 10},
                'sodium': {'weight': -0.5, 'max_score': 10, 'unit': 'mg', 'divisor': 100},  # Fixed: use 100mg as divisor
                'fiber': {'weight': 3, 'max_score': 15, 'unit': 'g', 'divisor': 10},
                'protein': {'weight': 2, 'max_score': 15, 'unit': 'g', 'divisor': 10},  # Increased protein weight
                'vitamins': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1},
                'minerals': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1}
            },
            'ingredients': {
                'harmful_additives': {
                    'weight': -2,
                    'keywords': [
                        # English
                        'artificial sweetener', 'aspartame', 'saccharin', 'sucralose',
                        'high fructose corn syrup', 'hfcs', 'hydrogenated oil',
                        'partially hydrogenated', 'trans fat', 'monosodium glutamate',
                        'msg', 'bha', 'bht', 'sodium nitrite', 'sodium nitrate',
                        'artificial color', 'red 40', 'yellow 5', 'blue 1',
                        'potassium bromate', 'azodicarbonamide',
                        # Romanian
                        'îndulcitor artificial', 'aspartam', 'zaharină', 'sucraloză',
                        'sirop de porumb bogat în fructoză', 'ulei hidrogenat',
                        'parțial hidrogenat', 'grăsimi trans', 'glutamat monosodic',
                        'gms', 'bha', 'bht', 'nitrit de sodiu', 'nitrați de sodiu',
                        'colorant artificial', 'roșu 40', 'galben 5', 'albastru 1',
                        'bromat de potasiu', 'azodicarbonamidă'
                    ]
                },
                'healthy_ingredients': {
                    'weight': 2,  # Increased weight for healthy ingredients
                    'keywords': [
                        # English
                        'whole grain', 'organic', 'natural', 'no artificial',
                        'real fruit', 'real vegetables', 'antioxidants',
                        'omega-3', 'probiotics', 'prebiotics', 'fiber',
                        'live cultures', 'whole milk',
                        # Romanian
                        'cereale integrale', 'organic', 'natural', 'fără aditivi artificiali',
                        'fructe reale', 'legume reale', 'antioxidanți',
                        'omega-3', 'probiotice', 'prebiotice', 'fibre',
                        'culturi vii', 'lapte integral'
                    ]
                }
            },
            'base_score': 50  # Starting score
        }
    
    def extract_nutritional_value(self, nutritional_data: Dict[str, Any], nutrient: str) -> float:
        """
        Extract nutritional value from the nutritional data dictionary.
        
        Args:
            nutritional_data: Dictionary containing nutritional information
            nutrient: Name of the nutrient to extract
            
        Returns:
            float: The nutritional value, or 0 if not found
        """
        if not nutritional_data:
            return 0.0
        
        # Common variations of nutrient names
        nutrient_variations = {
            'saturated_fat': ['saturated_fat', 'saturated fat', 'saturated fats', 'saturated_fats'],
            'sugar': ['sugar', 'sugars', 'total_sugar', 'total sugar'],
            'salt': ['salt', 'sodium_chloride'],
            'sodium': ['sodium', 'na'],
            'fiber': ['fiber', 'fibre', 'dietary_fiber', 'dietary fibre'],
            'protein': ['protein', 'proteins']
        }
        
        variations = nutrient_variations.get(nutrient, [nutrient])
        
        for var in variations:
            if var in nutritional_data:
                value = nutritional_data[var]
                if isinstance(value, (int, float)):
                    return float(value)
                elif isinstance(value, str):
                    # Extract numeric value from string
                    match = re.search(r'(\d+\.?\d*)', value)
                    if match:
                        return float(match.group(1))
        
        return 0.0
    
    def analyze_ingredients(self, ingredients: str) -> Dict[str, int]:
        """
        Analyze ingredients for harmful and healthy components.
        
        Args:
            ingredients: String containing ingredients list
            
        Returns:
            Dict with counts of harmful and healthy ingredients found
        """
        if not ingredients:
            return {'harmful': 0, 'healthy': 0}
        
        ingredients_lower = ingredients.lower()
        
        harmful_count = 0
        healthy_count = 0
        
        # Check for harmful ingredients
        for keyword in self.scoring_config['ingredients']['harmful_additives']['keywords']:
            if keyword.lower() in ingredients_lower:
                harmful_count += 1
        
        # Check for healthy ingredients
        for keyword in self.scoring_config['ingredients']['healthy_ingredients']['keywords']:
            if keyword.lower() in ingredients_lower:
                healthy_count += 1
        
        return {'harmful': harmful_count, 'healthy': healthy_count}
    
    def calculate_nutrient_score(self, nutritional_data: Dict[str, Any]) -> float:
        """
        Calculate score based on nutritional values.
        
        Args:
            nutritional_data: Dictionary containing nutritional information
            
        Returns:
            float: Nutritional score component
        """
        score = 0.0
        
        for nutrient, config in self.scoring_config['nutrients'].items():
            if nutrient in ['vitamins', 'minerals']:
                # Handle vitamins and minerals differently
                continue
            
            value = self.extract_nutritional_value(nutritional_data, nutrient)
            
            if value > 0:
                # Calculate score based on weight, value, and divisor
                divisor = config.get('divisor', 10)  # Default to 10 if not specified
                normalized_value = value / divisor
                
                if config['weight'] < 0:  # Harmful nutrients
                    # Higher values get more negative scores
                    score += max(config['weight'] * normalized_value, -config['max_score'])
                else:  # Beneficial nutrients
                    # Higher values get more positive scores
                    score += min(config['weight'] * normalized_value, config['max_score'])
        
        return score
    
    def calculate_ingredient_score(self, ingredients: str) -> float:
        """
        Calculate score based on ingredient analysis.
        
        Args:
            ingredients: String containing ingredients list
            
        Returns:
            float: Ingredient score component
        """
        analysis = self.analyze_ingredients(ingredients)
        
        harmful_score = analysis['harmful'] * self.scoring_config['ingredients']['harmful_additives']['weight']
        healthy_score = analysis['healthy'] * self.scoring_config['ingredients']['healthy_ingredients']['weight']
        
        return harmful_score + healthy_score
    
    def calculate_health_score(self, product_data: Dict[str, Any]) -> int:
        """
        Calculate overall health score for a product.
        
        Args:
            product_data: Dictionary containing product information including
                         nutritional data and ingredients
            
        Returns:
            int: Health score between 0 and 100
        """
        # Special case: water
        name = product_data.get('name', '').lower()
        ingredients = str(product_data.get('ingredients', '') or '').lower()
        if any(w in name for w in ['apa', 'water']) or any(w in ingredients for w in ['apa', 'water']):
            return 100

        # Start with base score
        score = self.scoring_config['base_score']
        
        # Get nutritional data
        nutritional_data = product_data.get('nutritional', {})
        if isinstance(nutritional_data, str):
            try:
                nutritional_data = json.loads(nutritional_data)
            except:
                nutritional_data = {}
        
        # Calculate nutritional score
        nutrient_score = self.calculate_nutrient_score(nutritional_data)
        score += nutrient_score
        
        # Calculate ingredient score
        print(f"Ingredients: {str(product_data.get('ingredients') or '')[:100]}...")

        ingredient_score = self.calculate_ingredient_score(ingredients)
        score += ingredient_score
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        return int(round(score))
    
    def get_score_category(self, score: int) -> str:
        """
        Get the category description for a given score.
        
        Args:
            score: Health score (0-100)
            
        Returns:
            str: Category description
        """
        if score >= 76:
            return "Healthy choice"
        elif score >= 51:
            return "Caution"
        elif score >= 26:
            return "Think twice"
        else:
            return "High risk"
    
    def get_score_color(self, score: int) -> str:
        """
        Get the color code for a given score.
        
        Args:
            score: Health score (0-100)
            
        Returns:
            str: Color name
        """
        if score >= 76:
            return "green"
        elif score >= 51:
            return "yellow"
        elif score >= 26:
            return "orange"
        else:
            return "red"

def calculate_health_scores_for_csv(csv_path: str, output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Calculate health scores for all products in a CSV file.
    
    Args:
        csv_path: Path to the CSV file
        output_path: Optional path to save the updated CSV
        
    Returns:
        pd.DataFrame: DataFrame with added health_score column
    """
    # Read the CSV
    df = pd.read_csv(csv_path)
    
    # Initialize the health scorer
    scorer = HealthScorer()
    
    # Calculate health scores
    health_scores = []
    score_categories = []
    score_colors = []
    
    for _, row in df.iterrows():
        # Prepare product data
        product_data = {
            'nutritional': row.get('nutritional_info', {}),
            'ingredients': row.get('ingredients', '')
        }
        
        # Calculate score
        score = scorer.calculate_health_score(product_data)
        health_scores.append(score)
        
        # Get category and color
        score_categories.append(scorer.get_score_category(score))
        score_colors.append(scorer.get_score_color(score))
    
    # Add new columns
    df['health_score'] = health_scores
    df['score_category'] = score_categories
    df['score_color'] = score_colors
    
    # Save if output path is provided
    if output_path:
        df.to_csv(output_path, index=False)
        print(f"Updated CSV saved to: {output_path}")
    
    # Print summary
    print(f"\nHealth Score Summary:")
    print(f"Total products: {len(df)}")
    print(f"Average score: {df['health_score'].mean():.1f}")
    print(f"Score distribution:")
    print(f"  Healthy choice (76-100): {len(df[df['health_score'] >= 76])}")
    print(f"  Caution (51-75): {len(df[(df['health_score'] >= 51) & (df['health_score'] < 76)])}")
    print(f"  Think twice (26-50): {len(df[(df['health_score'] >= 26) & (df['health_score'] < 51)])}")
    print(f"  High risk (0-25): {len(df[df['health_score'] < 26])}")
    
    return df

def update_supabase_health_scores():
    """
    Update health scores for existing products in Supabase.
    """
    from supabase import create_client
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
    supabase = create_client(supabase_url, supabase_key)
    
    # Initialize the health scorer
    scorer = HealthScorer()
    
    # Fetch all products from Supabase
    result = supabase.table('Products').select('*').execute()
    
    if hasattr(result, 'error') and result.error:
        print(f"Error fetching products: {result.error}")
        return
    
    products = result.data
    print(f"Found {len(products)} products to update")
    
    # Update each product with health score
    updated_count = 0
    for product in products:
        try:
            # Calculate health score
            score = scorer.calculate_health_score(product)
            
            # Update the product
            supabase.table('Products').update({
                'health_score': score
            }).eq('id', product['id']).execute()
            
            updated_count += 1
            if updated_count % 10 == 0:
                print(f"Updated {updated_count} products...")
                
        except Exception as e:
            print(f"Error updating product {product.get('name', 'Unknown')}: {str(e)}")
    
    print(f"Successfully updated health scores for {updated_count} products")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Calculate health scores for products')
    parser.add_argument('--csv', type=str, help='Path to CSV file to process')
    parser.add_argument('--output', type=str, help='Output CSV path')
    parser.add_argument('--supabase', action='store_true', help='Update health scores in Supabase')
    
    args = parser.parse_args()
    
    if args.csv:
        calculate_health_scores_for_csv(args.csv, args.output)
    elif args.supabase:
        update_supabase_health_scores()
    else:
        print("Please provide either --csv or --supabase argument") 