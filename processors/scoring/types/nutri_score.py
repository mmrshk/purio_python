import re
import json
import requests

class NutriScoreCalculator:
    SCORING_CONFIG = {
        'saturated_fat': {'weight': -1, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'sugar': {'weight': -1.5, 'max_score': 20, 'unit': 'g', 'divisor': 10},
        'salt': {'weight': -2, 'max_score': 10, 'unit': 'g', 'divisor': 10},
        'sodium': {'weight': -0.5, 'max_score': 10, 'unit': 'mg', 'divisor': 100},
        'fiber': {'weight': 3, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'protein': {'weight': 2, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'vitamins': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1},
        'minerals': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1}
    }

    NUTRIENT_VARIATIONS = {
        'saturated_fat': ['saturated_fat', 'saturated fat', 'saturated fats', 'saturated_fats'],
        'sugar': ['sugar', 'sugars', 'total_sugar', 'total sugar'],
        'salt': ['salt', 'sodium_chloride'],
        'sodium': ['sodium', 'na'],
        'fiber': ['fiber', 'fibre', 'dietary_fiber', 'dietary fibre'],
        'protein': ['protein', 'proteins']
    }

    NUTRISCORE_MAP = {
        'a': 100,
        'b': 80,
        'c': 60,
        'd': 40,
        'e': 20
    }

    def fetch_nutriscore_from_off(self, ean=None, product_name=None):
        if ean:
            url = f"https://world.openfoodfacts.org/api/v0/product/{ean}.json"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    product = data.get('product', {})
                    nutriscore = product.get('nutriscore_grade')

                    return self.NUTRISCORE_MAP.get(nutriscore)
            except Exception as e:
                print(f"Error fetching NutriScore by EAN: {e}")

        if product_name:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": product_name,
                "search_simple": 1,
                "action": "process",
                "json": 1
            }
            try:
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get('products', [])
                    if products:
                        nutriscore = products[0].get('nutriscore_grade')

                        return self.NUTRISCORE_MAP.get(nutriscore)
            except Exception as e:
                print(f"Error fetching NutriScore by name: {e}")
        return None

    def extract_nutritional_value(self, nutritional_data, nutrient):
        if not nutritional_data:
            return 0.0

        variations = self.NUTRIENT_VARIATIONS.get(nutrient, [nutrient])
        for var in variations:
            if var in nutritional_data:
                value = nutritional_data[var]
                if isinstance(value, (int, float)):
                    return float(value)
                elif isinstance(value, str):
                    match = re.search(r'(\d+\.?\d*)', value)
                    if match:
                        return float(match.group(1))
        return 0.0

    def calculate_nutrient_score(self, nutritional_data):
        score = 0.0
        for nutrient, config in self.SCORING_CONFIG.items():
            if nutrient in ['vitamins', 'minerals']:
                continue
            value = self.extract_nutritional_value(nutritional_data, nutrient)
            if value > 0:
                divisor = config.get('divisor', 10)
                normalized_value = value / divisor
                if config['weight'] < 0:
                    score += max(config['weight'] * normalized_value, -config['max_score'])
                else:
                    score += min(config['weight'] * normalized_value, config['max_score'])
        return score

    def calculate(self, product_data):
        ean = product_data.get('barcode')
        name = product_data.get('name')

        nutriscore = self.fetch_nutriscore_from_off(ean=ean, product_name=name)
        nutriscore_score_set_by = None

        if nutriscore is not None:
            nutriscore_score_set_by = 'api'

            return nutriscore, nutriscore_score_set_by

        nutritional_data = product_data.get('nutritional', {})

        if isinstance(nutritional_data, str):
            try:
                nutritional_data = json.loads(nutritional_data)
            except:
                nutritional_data = {}

        nutrient_score = self.calculate_nutrient_score(nutritional_data)
        nutriscore_score_set_by = 'local'
        normalized = max(0, min(100, 50 + nutrient_score))

        return normalized, nutriscore_score_set_by