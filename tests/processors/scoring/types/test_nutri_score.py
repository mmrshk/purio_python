#!/usr/bin/env python3
"""
Test script for NutriScoreCalculator functionality.
"""

import sys
import unittest

from unittest.mock import patch, Mock
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))
from processors.scoring.types.nutri_score import NutriScoreCalculator


class TestNutriScoreCalculator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.calculator = NutriScoreCalculator()
        
    def test_fetch_nutriscore_by_ean_success(self):
        """Test successful NutriScore fetch by EAN."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'product': {
                'nutriscore_grade': 'a'
            }
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nutriscore_from_off(ean='1234567890123')
            self.assertEqual(result, 100)
    
    def test_fetch_nutriscore_by_ean_no_grade(self):
        """Test NutriScore fetch by EAN when no grade is available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'product': {}
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nutriscore_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_fetch_nutriscore_by_name_success(self):
        """Test successful NutriScore fetch by product name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'products': [
                {'nutriscore_grade': 'b'}
            ]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nutriscore_from_off(product_name='Test Product')
            self.assertEqual(result, 80)
    
    def test_fetch_nutriscore_by_name_no_products(self):
        """Test NutriScore fetch by name when no products found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'products': []
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nutriscore_from_off(product_name='Unknown Product')
            self.assertIsNone(result)
    
    def test_fetch_nutriscore_api_error(self):
        """Test NutriScore fetch when API returns error."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nutriscore_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_fetch_nutriscore_request_exception(self):
        """Test NutriScore fetch when request raises exception."""
        with patch('requests.get', side_effect=Exception("Network error")):
            result = self.calculator.fetch_nutriscore_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_calculate_with_api_nutriscore(self):
        """Test calculation when API returns NutriScore."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product',
            'nutritional': {}
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=100):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 100)
            self.assertEqual(source, 'api')
    
    def test_calculate_negative_points(self):
        """Test negative points calculation."""
        nutritional_data = {
            'calories_per_100g_or_100ml': 200,  # kcal
            'sugar': 25,   # g
            'fat': 10,     # g (30% = 3g saturated fat)
        }
        
        n_points = self.calculator.calculate_negative_points(nutritional_data)
        # Energy: 200 kcal = 836.8 kJ → 2 points
        # Sugars: 25g → 5 points
        # Saturated fat: 3g (30% of 10g fat) → 2 points
        # Sodium: 0 (not available) → 0 points
        # Total: 2 + 5 + 2 + 0 = 9 points
        self.assertEqual(n_points, 9)
    
    def test_calculate_positive_points(self):
        """Test positive points calculation."""
        nutritional_data = {
            'protein': 8  # g
        }
        specifications_data = {
            'fiber': 4.5  # g
        }
        
        p_points = self.calculator.calculate_positive_points(nutritional_data, specifications_data)
        # Fiber: 4.5g → 4 points
        # Protein: 8g → 4 points
        # Total: 4 + 4 = 8 points
        self.assertEqual(p_points, 8)
    
    def test_calculate_final_nutriscore(self):
        """Test final Nutri-Score grade calculation."""
        # Test case 1: N < 11
        grade = self.calculator.calculate_final_nutriscore(5, 8)  # N=5, P=8
        self.assertEqual(grade, 'a')  # 5 - 8 = -3 → A
        
        # Test case 2: N ≥ 11, fruit/veg < threshold
        grade = self.calculator.calculate_final_nutriscore(15, 8)  # N=15, P=8
        self.assertEqual(grade, 'c')  # 15 - 5 = 10 → C (using fiber only)
        
        # Test case 3: Very high N
        grade = self.calculator.calculate_final_nutriscore(25, 2)  # N=25, P=2
        self.assertEqual(grade, 'e')  # 25 - 2 = 23 → E
    
    def test_extract_nutritional_value(self):
        """Test extracting nutritional values from different formats."""
        nutritional_data = {
            'sugar': 10.5,
            'protein': '8.0g',
            'fat': '3.5 grams'
        }
        
        sugar_value = self.calculator.extract_nutritional_value(nutritional_data, 'sugar')
        protein_value = self.calculator.extract_nutritional_value(nutritional_data, 'protein')
        fat_value = self.calculator.extract_nutritional_value(nutritional_data, 'fat')
        
        self.assertEqual(sugar_value, 10.5)
        self.assertEqual(protein_value, 8.0)
        self.assertEqual(fat_value, 3.5)
    
    def test_extract_specification_value(self):
        """Test extracting specification values."""
        specifications_data = {
            'fiber': 2.5,
            'vitamins': '10mg'
        }
        
        fiber_value = self.calculator.extract_specification_value(specifications_data, 'fiber')
        self.assertEqual(fiber_value, 2.5)
    
    def test_calculate_local_nutriscore(self):
        """Test local Nutri-Score calculation."""
        product_data = {
            'nutritional': {
                'calories_per_100g_or_100ml': 150,  # kcal
                'sugar': 8,    # g
                'fat': 3.33,   # g (30% = 1g saturated fat)
                'protein': 8   # g
            },
            'specifications': {
                'fiber': 4.5    # g
            }
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            score, source = self.calculator.calculate(product_data)
            self.assertEqual(source, 'local')
            self.assertIsInstance(score, (int, float))
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
    
    def test_calculate_with_missing_data(self):
        """Test calculation with missing nutritional data."""
        product_data = {
            'nutritional': {},
            'specifications': {}
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            score, source = self.calculator.calculate(product_data)
            self.assertEqual(source, 'local')
            self.assertIsInstance(score, (int, float))
    
    def test_calculate_with_string_data(self):
        """Test calculation with string nutritional data."""
        product_data = {
            'nutritional': '{"energy": "200", "sugars": "25"}',
            'specifications': '{"fiber": "1.5"}'
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            score, source = self.calculator.calculate(product_data)
            self.assertEqual(source, 'local')
            self.assertIsInstance(score, (int, float))


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests() 