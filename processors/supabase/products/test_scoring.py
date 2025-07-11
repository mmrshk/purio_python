#!/usr/bin/env python3
"""
Test script to verify Nova and Nutri-Score calculations work correctly.
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from processors.scoring.types.nova_score import NovaScoreCalculator
from processors.scoring.types.nutri_score import NutriScoreCalculator

def test_scoring_calculators():
    """Test the scoring calculators with sample product data."""
    
    print("Testing Nova and Nutri-Score Calculators")
    print("=" * 50)
    
    # Initialize calculators
    nova_calc = NovaScoreCalculator()
    nutri_calc = NutriScoreCalculator()
    
    # Sample product data for testing
    test_products = [
        {
            'name': 'Fresh Apples',
            'barcode': '1234567890123',
            'nutritional': {
                'fiber': 4.0,
                'protein': 0.5,
                'sugar': 19.0,
                'saturated_fat': 0.1,
                'sodium': 1.0
            },
            'ingredients': 'apples',
            'nova_group': 1
        },
        {
            'name': 'Whole Grain Bread',
            'barcode': '9876543210987',
            'nutritional': {
                'fiber': 8.0,
                'protein': 12.0,
                'sugar': 3.0,
                'saturated_fat': 1.0,
                'sodium': 400.0
            },
            'ingredients': 'whole grain flour, water, salt, yeast',
            'nova_group': 3
        },
        {
            'name': 'Processed Cheese',
            'barcode': '5556667778889',
            'nutritional': {
                'fiber': 0.0,
                'protein': 25.0,
                'sugar': 1.0,
                'saturated_fat': 18.0,
                'sodium': 800.0
            },
            'ingredients': 'milk, salt, enzymes, artificial color',
            'nova_group': 4
        },
        {
            'name': 'Chocolate Bar',
            'barcode': '1112223334445',
            'nutritional': {
                'fiber': 3.0,
                'protein': 5.0,
                'sugar': 45.0,
                'saturated_fat': 25.0,
                'sodium': 50.0
            },
            'ingredients': 'sugar, cocoa butter, milk, artificial sweetener, preservatives',
            'nova_group': 4
        }
    ]
    
    for i, product in enumerate(test_products, 1):
        print(f"\nProduct {i}: {product['name']}")
        print("-" * 30)
        
        # Calculate Nova score
        nova_score, nova_source = nova_calc.calculate(product)
        print(f"Nova Score: {nova_score}/100 (source: {nova_source})")
        
        # Calculate Nutri-Score
        nutri_score, nutri_source = nutri_calc.calculate(product)
        print(f"Nutri-Score: {nutri_score}/100 (source: {nutri_source})")
        
        # Print nutritional info
        print(f"Nutritional data: {product['nutritional']}")
        print(f"Ingredients: {product['ingredients']}")
        print(f"Nova group: {product.get('nova_group', 'N/A')}")
    
    print("\n" + "=" * 50)
    print("Test completed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    test_scoring_calculators() 