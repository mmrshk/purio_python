import requests
import os
import sys

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

class NovaScoreCalculator:
    NOVA_MAP = {
        1: 100,  # Unprocessed or minimally processed foods
        2: 80,   # Processed culinary ingredients
        3: 50,   # Processed foods
        4: 20    # Ultra-processed foods
    }
    
    def __init__(self):
        """Initialize the NOVA score calculator with ingredients checker."""
        from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker
        self.ingredients_checker = SupabaseIngredientsChecker()
    
    def get_nova_distribution_from_ingredients(self, product_data):
        """
        Get NOVA score distribution from product ingredients.
        
        Args: 
            product_data: Product data containing specifications with ingredients
        Returns: 
            Dictionary with NOVA score distribution {1: count, 2: count, 3: count, 4: count} 
            or None if unable to get distribution.
            Will use parsed_ingredients.nova_scores if available, otherwise parses from ingredients text.
        """

        specs = product_data.get('specifications', {})
        if not isinstance(specs, dict):
            return None
        
        # First, check if parsed_ingredients already exists with nova_scores
        parsed_ingredients = specs.get('parsed_ingredients', {})
        if isinstance(parsed_ingredients, dict) and parsed_ingredients.get('nova_scores'):
            nova_scores = parsed_ingredients.get('nova_scores', [])
            if nova_scores and len(nova_scores) > 0:
                # Convert list to distribution dictionary
                distribution = {1: 0, 2: 0, 3: 0, 4: 0}
                for score in nova_scores:
                    if score in distribution:
                        distribution[score] += 1
                return distribution
        
        # Fallback: parse ingredients from scratch
        ingredients_text = specs.get('ingredients', '')
        if not ingredients_text:
            return None
        
        # Use the ingredients checker to get NOVA scores
        result = self.ingredients_checker.check_product_ingredients({
            'name': product_data.get('name', 'Unknown'),
            'specifications': specs
        })
        
        # Convert list of scores to distribution dictionary
        nova_scores_list = result.get('nova_scores', [])
        if not nova_scores_list:
            return None
        
        distribution = {1: 0, 2: 0, 3: 0, 4: 0}
        for score in nova_scores_list:
            if score in distribution:
                distribution[score] += 1
        return distribution
    
    def calculate_nova_from_distribution(self, nova_distribution):
        """
        Calculate NOVA score from distribution using the rules:
        - If any ingredient is NOVA 4 → NOVA 4 (ultra-processed)
        - Else if only culinary ingredients (NOVA 2) → NOVA 2
        - Else if mix of natural and culinary → NOVA 3
        - Only whole ingredients → NOVA 1
        
        Args:
            nova_distribution: List of NOVA scores or dict with counts {1: count, 2: count, 3: count, 4: count}
            
        Returns:
            NOVA group (1-4) or None if unable to calculate
        """
        if not nova_distribution:
            return None
        
        # Convert list of scores to distribution dictionary if needed
        if isinstance(nova_distribution, list):
            distribution = {1: 0, 2: 0, 3: 0, 4: 0}
            for score in nova_distribution:
                if score in distribution:
                    distribution[score] += 1
            nova_distribution = distribution
        
        # If any ingredient is NOVA 4 → NOVA 4 (ultra-processed)
        if nova_distribution.get(4, 0) > 0:
            return 4
        
        # If any ingredient is NOVA 3 → NOVA 3 (processed)
        if nova_distribution.get(3, 0) > 0:
            return 3
        
        # If mix of natural (NOVA 1) and culinary (NOVA 2) → NOVA 3
        if (nova_distribution.get(1, 0) > 0 and 
            nova_distribution.get(2, 0) > 0):
            return 3

        # If only culinary ingredients (NOVA 2) → NOVA 2
        if (nova_distribution.get(2, 0) > 0 and 
            nova_distribution.get(1, 0) == 0):
            return 2
        
        # If only whole ingredients (NOVA 1) → NOVA 1
        if (nova_distribution.get(1, 0) > 0 and 
            nova_distribution.get(2, 0) == 0):
            return 1
        
        return None
    
    def fetch_nova_from_off(self, ean=None, product_name=None):
        """Fetch NOVA score from Open Food Facts API."""
        # Configure headers to be more respectful to the API
        headers = {
            'User-Agent': 'FoodFacts-HealthScoring/1.0 (https://github.com/mmrshk/food_facts)',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # Try by barcode first
        if ean:
            url = f"https://world.openfoodfacts.org/api/v0/product/{ean}.json"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    product = data.get('product', {})
                    nova_group = product.get('nova-group')
                    if nova_group:
                        return int(nova_group)
            except requests.exceptions.Timeout:
                print(f"Timeout fetching NOVA by EAN: {ean}")
            except requests.exceptions.RequestException as e:
                print(f"Network error fetching NOVA by EAN: {e}")
            except Exception as e:
                print(f"Error fetching NOVA by EAN: {e}")
        
        # Fallback: search by product name
        if product_name:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": product_name,
                "search_simple": 1,
                "action": "process",
                "json": 1
            }
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get('products', [])
                    if products:
                        nova_group = products[0].get('nova-group')
                        if nova_group:
                            return int(nova_group)
            except requests.exceptions.Timeout:
                print(f"Timeout fetching NOVA by name: {product_name}")
            except requests.exceptions.RequestException as e:
                print(f"Network error fetching NOVA by name: {e}")
            except Exception as e:
                print(f"Error fetching NOVA by name: {e}")
        return None
    
    def calculate_local_nova(self, product_data):
        """Calculate NOVA score locally based on ingredient analysis."""
        # Get NOVA distribution from ingredients
        nova_distribution = self.get_nova_distribution_from_ingredients(product_data)
        
        # Calculate NOVA group from distribution
        return self.calculate_nova_from_distribution(nova_distribution)
    
    def calculate(self, product_data):
        """Calculate NOVA score, trying API first, then falling back to ingredient analysis."""
        ean = product_data.get('barcode')
        name = product_data.get('name')
        
        # Try to get NOVA from Open Food Facts API
        nova_group = self.fetch_nova_from_off(ean=ean, product_name=name)
        nova_score_set_by = None
        
        if nova_group is not None:
            nova_score_set_by = 'api'
            score = self.NOVA_MAP.get(nova_group)
            return score, nova_score_set_by
        
        # Special handling for water and similar products with no ingredients
        specs = product_data.get('specifications', {})
        if isinstance(specs, str):
            try:
                import json
                specs = json.loads(specs)
            except:
                specs = {}
        
        ingredients = specs.get('ingredients', '') if specs else ''
        
        # Check if this looks like water or a similar natural product with no ingredients
        if not ingredients or ingredients.strip() == '':
            product_name_lower = name.lower() if name else ""
            if any(keyword in product_name_lower for keyword in ['water', 'apa', 'mineral', 'spring']):
                nova_score_set_by = 'special_case'
                return 100, nova_score_set_by  # NOVA 1 = 100 points for unprocessed natural products
            
            # Special handling for alcoholic beverages
            alcohol_keywords = ['beer', 'bere', 'wine', 'vin', 'spirit', 'vodka', 'whiskey', 'rum', 'gin', 'liqueur', 'cocktail']
            if any(keyword in product_name_lower for keyword in alcohol_keywords):
                nova_score_set_by = 'special_case'
                return 50, nova_score_set_by  # NOVA 3 = 50 points for processed alcoholic beverages
        
        # Fallback to ingredient analysis
        nova_group = self.calculate_local_nova(product_data)
        
        if nova_group is not None:
            nova_score_set_by = 'local'
            score = self.NOVA_MAP.get(nova_group)
            return score, nova_score_set_by
        
        return None, None 