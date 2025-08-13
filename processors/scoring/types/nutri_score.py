import re
import json
import requests

class NutriScoreCalculator:
    # Official Nutri-Score negative points (N) thresholds
    NEGATIVE_POINTS_THRESHOLDS = {
        'energy': [
            (0, 335, 0), (336, 670, 1), (671, 1005, 2), (1006, 1340, 3),
            (1341, 1675, 4), (1676, 2010, 5), (2011, 2345, 6), (2346, 2680, 7),
            (2681, 3015, 8), (3016, 3350, 9), (3351, float('inf'), 10)
        ],
        'sugars': [
            (0, 4.5, 0), (4.6, 9, 1), (9.1, 13.5, 2), (13.6, 18, 3),
            (18.1, 22.5, 4), (22.6, 27, 5), (27.1, 31, 6), (31.1, 36, 7),
            (36.1, 40, 8), (40.1, 45, 9), (45.1, float('inf'), 10)
        ],
        'saturated_fat': [
            (0, 1, 0), (1.1, 2, 1), (2.1, 3, 2), (3.1, 4, 3),
            (4.1, 5, 4), (5.1, 6, 5), (6.1, 7, 6), (7.1, 8, 7),
            (8.1, 9, 8), (9.1, 10, 9), (10.1, float('inf'), 10)
        ],
        'sodium': [
            (0, 90, 0), (91, 180, 1), (181, 270, 2), (271, 360, 3),
            (361, 450, 4), (451, 540, 5), (541, 630, 6), (631, 720, 7),
            (721, 810, 8), (811, 900, 9), (901, float('inf'), 10)
        ]
    }

    # Official Nutri-Score positive points (P) thresholds
    POSITIVE_POINTS_THRESHOLDS = {
        'fiber': [
            (0, 0.9, 0), (0.9, 1.9, 1), (1.9, 2.8, 2), (2.8, 3.7, 3),
            (3.7, 4.7, 4), (4.7, float('inf'), 5)
        ],
        'protein': [
            (0, 1.6, 0), (1.6, 3.2, 1), (3.2, 4.8, 2), (4.8, 6.4, 3),
            (6.4, 8, 4), (8, float('inf'), 5)
        ]
    }

    # Fruit/vegetables/nuts threshold for special calculation
    FRUIT_VEG_THRESHOLD = 80  # 80%

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

    def get_points_for_value(self, value, thresholds):
        """Get points for a given value based on thresholds."""
        for min_val, max_val, points in thresholds:
            if min_val <= value <= max_val:
                return points
        return 0

    def extract_nutritional_value(self, nutritional_data, nutrient):
        """Extract nutritional value from the nutritional data dictionary."""
        if not nutritional_data:
            return 0.0

        if nutrient in nutritional_data:
            value = nutritional_data[nutrient]
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Extract numeric value from string
                match = re.search(r'(\d+\.?\d*)', value)
                if match:
                    return float(match.group(1))
        return 0.0

    def extract_specification_value(self, specifications_data, spec):
        """Extract value from specifications data."""
        if not specifications_data:
            return 0.0

        if spec in specifications_data:
            value = specifications_data[spec]
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                match = re.search(r'(\d+\.?\d*)', value)
                if match:
                    return float(match.group(1))
        return 0.0

    def calculate_negative_points(self, nutritional_data):
        """Calculate negative points (N) based on official Nutri-Score thresholds."""
        n_points = 0
        
        # Energy (convert kcal to kJ if needed)
        energy_kcal = self.extract_nutritional_value(nutritional_data, 'calories_per_100g_or_100ml')
        if energy_kcal > 0:
            # If energy is in kcal, convert to kJ (1 kcal = 4.184 kJ)
            energy_kj = energy_kcal * 4.184
            n_points += self.get_points_for_value(energy_kj, self.NEGATIVE_POINTS_THRESHOLDS['energy'])
        
        # Sugars
        sugars = self.extract_nutritional_value(nutritional_data, 'sugar')
        n_points += self.get_points_for_value(sugars, self.NEGATIVE_POINTS_THRESHOLDS['sugars'])
        
        # Saturated fat (from fat field - we'll need to extract saturated fat from total fat)
        # For now, using total fat as approximation
        fat = self.extract_nutritional_value(nutritional_data, 'fat')
        # Assuming 30% of total fat is saturated fat (rough approximation)
        saturated_fat = fat * 0.3 if fat > 0 else 0
        n_points += self.get_points_for_value(saturated_fat, self.NEGATIVE_POINTS_THRESHOLDS['saturated_fat'])
        
        # Sodium - not available in current data structure
        # Nutri-Score calculation will be less accurate without sodium data
        # This is a limitation of the current data structure
        sodium = 0
        n_points += self.get_points_for_value(sodium, self.NEGATIVE_POINTS_THRESHOLDS['sodium'])
        
        return n_points

    def calculate_positive_points(self, nutritional_data, specifications_data):
        """Calculate positive points (P) based on official Nutri-Score thresholds."""
        p_points = 0
        
        # Fiber (from specifications)
        fiber = self.extract_specification_value(specifications_data, 'fiber')
        p_points += self.get_points_for_value(fiber, self.POSITIVE_POINTS_THRESHOLDS['fiber'])
        
        # Protein (from nutritional)
        protein = self.extract_nutritional_value(nutritional_data, 'protein')
        p_points += self.get_points_for_value(protein, self.POSITIVE_POINTS_THRESHOLDS['protein'])
        
        return p_points

    def calculate_final_nutriscore(self, n_points, p_points, fruit_veg_percentage=0):
        """Calculate final Nutri-Score using official formula."""
        if n_points < 11:
            final_score = n_points - p_points
        else:
            # If N ≥ 11 and fruit/veg < threshold, use N - (Fiber + Fruit)
            if fruit_veg_percentage < self.FRUIT_VEG_THRESHOLD:
                # For now, we'll use just fiber since fruit/veg data is not available
                fiber_points = min(p_points, 5)  # Fiber can contribute max 5 points
                final_score = n_points - fiber_points
            else:
                final_score = n_points - p_points
        
        # Map to Nutri-Score grade
        if final_score <= -1:
            return 'a'
        elif final_score <= 2:
            return 'b'
        elif final_score <= 10:
            return 'c'
        elif final_score <= 18:
            return 'd'
        else:
            return 'e'

    def calculate(self, product_data):
        ean = product_data.get('barcode')
        name = product_data.get('name')

        # Try to get Nutri-Score from Open Food Facts API
        nutriscore = self.fetch_nutriscore_from_off(ean=ean, product_name=name)
        nutriscore_score_set_by = None

        if nutriscore is not None:
            nutriscore_score_set_by = 'api'
            return nutriscore, nutriscore_score_set_by

        # Calculate locally using official Nutri-Score formula
        nutritional_data = product_data.get('nutritional', {})
        specifications_data = product_data.get('specifications', {})

        if isinstance(nutritional_data, str):
            try:
                nutritional_data = json.loads(nutritional_data)
            except:
                nutritional_data = {}

        if isinstance(specifications_data, str):
            try:
                specifications_data = json.loads(specifications_data)
            except:
                specifications_data = {}

        # Calculate negative points (N)
        n_points = self.calculate_negative_points(nutritional_data)
        
        # Calculate positive points (P)
        p_points = self.calculate_positive_points(nutritional_data, specifications_data)
        
        # Calculate final Nutri-Score grade
        final_grade = self.calculate_final_nutriscore(n_points, p_points)
        
        # Map to numeric score (20-100 range)
        numeric_score = self.NUTRISCORE_MAP.get(final_grade, 50)
        nutriscore_score_set_by = 'local'

        return numeric_score, nutriscore_score_set_by