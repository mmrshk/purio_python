import json

class AdditivesScoreCalculator:
    # Harmful additives keywords (from HealthScorer)
    harmful_keywords = [
        'artificial sweetener', 'aspartame', 'saccharin', 'sucralose',
        'high fructose corn syrup', 'hfcs', 'hydrogenated oil',
        'partially hydrogenated', 'trans fat', 'monosodium glutamate',
        'msg', 'bha', 'bht', 'sodium nitrite', 'sodium nitrate',
        'artificial color', 'red 40', 'yellow 5', 'blue 1',
        'potassium bromate', 'azodicarbonamide',
        'îndulcitor artificial', 'aspartam', 'zaharină', 'sucraloză',
        'sirop de porumb bogat în fructoză', 'ulei hidrogenat',
        'parțial hidrogenat', 'grăsimi trans', 'glutamat monosodic',
        'gms', 'bha', 'bht', 'nitrit de sodiu', 'nitrați de sodiu',
        'colorant artificial', 'roșu 40', 'galben 5', 'albastru 1',
        'bromat de potasiu', 'azodicarbonamidă'
    ]

    def analyze_ingredients(self, ingredients):
        if not ingredients:
            return 0
        ingredients_lower = ingredients.lower()
        harmful_count = 0
        for keyword in self.harmful_keywords:
            if keyword.lower() in ingredients_lower:
                harmful_count += 1
        return harmful_count

    def calculate(self, product_data):
        # Prefer OpenFoodFacts additives_tags if present
        additives = product_data.get('additives_tags')
        if additives is not None:
            if isinstance(additives, str):
                try:
                    additives = json.loads(additives)
                except:
                    additives = [additives]
            num_additives = len(additives)
            # Score: 100 if no additives, 0 if 10 or more, linear in between
            score = max(0, 100 - num_additives * 10)
            return score
        # Fallback: keyword search in ingredients
        ingredients = str(product_data.get('ingredients', '') or '')
        harmful_count = self.analyze_ingredients(ingredients)
        score = max(0, 100 - harmful_count * 20)  # Each harmful keyword penalizes 20 points
        return score 