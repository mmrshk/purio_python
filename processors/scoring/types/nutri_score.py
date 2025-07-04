import re
import json

class NutriScoreCalculator:
    # Use similar config as HealthScorer
    scoring_config = {
        'saturated_fat': {'weight': -1, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'sugar': {'weight': -1.5, 'max_score': 20, 'unit': 'g', 'divisor': 10},
        'salt': {'weight': -2, 'max_score': 10, 'unit': 'g', 'divisor': 10},
        'sodium': {'weight': -0.5, 'max_score': 10, 'unit': 'mg', 'divisor': 100},
        'fiber': {'weight': 3, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'protein': {'weight': 2, 'max_score': 15, 'unit': 'g', 'divisor': 10},
        'vitamins': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1},
        'minerals': {'weight': 1, 'max_score': 5, 'unit': None, 'divisor': 1}
    }

    def extract_nutritional_value(self, nutritional_data, nutrient):
        if not nutritional_data:
            return 0.0
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
                    match = re.search(r'(\d+\.?\d*)', value)
                    if match:
                        return float(match.group(1))
        return 0.0

    def calculate_nutrient_score(self, nutritional_data):
        score = 0.0
        for nutrient, config in self.scoring_config.items():
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
        nutritional_data = product_data.get('nutritional', {})
        if isinstance(nutritional_data, str):
            try:
                nutritional_data = json.loads(nutritional_data)
            except:
                nutritional_data = {}
        # Use the same normalization as in HealthScorer stub: -50 to +50 mapped to 0-100
        nutrient_score = self.calculate_nutrient_score(nutritional_data)
        normalized = max(0, min(100, 50 + nutrient_score))
        return normalized 