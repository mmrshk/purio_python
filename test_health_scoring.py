#!/usr/bin/env python3
"""
Test script to demonstrate the health scoring functionality.
"""

import sys
from pathlib import Path

# Add the processors directory to the path
sys.path.append(str(Path(__file__).parent / "processors" / "helpers"))
from health_scorer import HealthScorer

def test_health_scoring():
    """Test the health scoring with sample product data."""
    
    # Initialize the health scorer
    scorer = HealthScorer()
    
    # Sample product data for testing
    test_products = [
        {
            'name': 'Jeleuri cu aroma de capsuni Auchan, 75 g',
            'nutritional': {"fat": "0.1", "sugar": "65", "carbohydrates": "82", "calories_per_100g_or_100ml": "329"},
            'ingredients': 'Zahar, sirop de glucoza, apa, agent de umezire (sirop de sorbitol), agent gelatinizant (pectina), acidifiant (acid citric), corector de aciditate (citrat trisodic), aroma (capsuni), colorant (carmin, beta-caroten). Poate contine urme de lapte, soia, ou si fructe cu coaja lemnoasa.'
        },
        {
            'name': 'Bautura carbogazoasa limone San Benedetto Zero, 0.75 l',
            'nutritional': {"fat": "0", "sugar": "0.4", "protein": "0", "carbohydrates": "0.5", "calories_per_100g_or_100ml": "4"},
            'ingredients': 'Apa, concentrat de suc de fructe 12% (lamaie 10%, grapefruit 2%), anhidrida carbonica, indulcitori (ciclamat de sodiu, acesulfam k, sucraloza), arome, sare, conservant: sorbat de potasiu, corector de aciditate: citrat de sodiu, antioxidant: acid ascorbic, stabilizator: E1450, acidifianti: acid citric.'
        },
        {
            'name': "Apa plata Borsec, 2 l",
            'nutritional':{},
            'ingredients': None
        },
    ]
    
    print("=== Health Scoring Test ===\n")
    
    for product in test_products:
        # Calculate health score
        score = scorer.calculate_health_score(product)
        category = scorer.get_score_category(score)
        color = scorer.get_score_color(score)
        
        # Debug: Calculate individual components
        base_score = scorer.scoring_config['base_score']
        nutrient_score = scorer.calculate_nutrient_score(product['nutritional'])
        ingredient_score = scorer.calculate_ingredient_score(product['ingredients'])
        
        print(f"Product: {product['name']}")
        print(f"Health Score: {score}/100 ({category}) - {color}")
        print(f"  Base Score: {base_score}")
        print(f"  Nutrient Score: {nutrient_score:.1f}")
        print(f"  Ingredient Score: {ingredient_score:.1f}")
        print(f"  Breakdown: {base_score} + {nutrient_score:.1f} + {ingredient_score:.1f} = {score}")
        print(f"Ingredients: {str(product.get('ingredients') or '')[:100]}...")
        print(f"Nutritional Info: {product['nutritional']}")
        print("-" * 50)
    
    print("\n=== Scoring Ranges ===")
    print("76-100: Healthy choice (Green)")
    print("51-75:  Caution (Yellow)")
    print("26-50:  Think twice (Orange)")
    print("0-25:   High risk (Red)")

if __name__ == "__main__":
    test_health_scoring() 