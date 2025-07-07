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
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value='C'):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 'C')
            self.assertEqual(source, 'api')
    
    def test_calculate_fallback_to_local(self):
        """Test calculation falls back to local method when API fails."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product',
            'nutritional': {
                'sugar': '10',
                'fiber': '5',
                'protein': '8'
            }
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            # Should return a numeric value between 0-100
            self.assertIsInstance(result, (int, float))
            self.assertGreaterEqual(result, 0)
            self.assertLessEqual(result, 100)
            self.assertEqual(source, 'local')
    
    def test_extract_nutritional_value_direct(self):
        """Test extracting nutritional value directly."""
        nutritional_data = {
            'sugar': 15.5,
            'protein': 8.0
        }
        
        sugar_value = self.calculator.extract_nutritional_value(nutritional_data, 'sugar')
        protein_value = self.calculator.extract_nutritional_value(nutritional_data, 'protein')
        
        self.assertEqual(sugar_value, 15.5)
        self.assertEqual(protein_value, 8.0)
    
    def test_extract_nutritional_value_variations(self):
        """Test extracting nutritional value with different key variations."""
        nutritional_data = {
            'saturated_fat': 5.0,
            'saturated fat': 6.0,
            'fiber': 3.0,
            'fibre': 4.0
        }
        
        sat_fat_value = self.calculator.extract_nutritional_value(nutritional_data, 'saturated_fat')
        fiber_value = self.calculator.extract_nutritional_value(nutritional_data, 'fiber')
        
        # Should return the first match found
        self.assertEqual(sat_fat_value, 5.0)
        self.assertEqual(fiber_value, 3.0)
    
    def test_extract_nutritional_value_string(self):
        """Test extracting nutritional value from string format."""
        nutritional_data = {
            'sugar': '12.5g',
            'protein': '8.0 grams'
        }
        
        sugar_value = self.calculator.extract_nutritional_value(nutritional_data, 'sugar')
        protein_value = self.calculator.extract_nutritional_value(nutritional_data, 'protein')
        
        self.assertEqual(sugar_value, 12.5)
        self.assertEqual(protein_value, 8.0)
    
    def test_extract_nutritional_value_not_found(self):
        """Test extracting nutritional value when not found."""
        nutritional_data = {
            'sugar': 10.0
        }
        
        result = self.calculator.extract_nutritional_value(nutritional_data, 'protein')
        self.assertEqual(result, 0.0)
    
    def test_extract_nutritional_value_empty_data(self):
        """Test extracting nutritional value with empty data."""
        result = self.calculator.extract_nutritional_value({}, 'sugar')
        self.assertEqual(result, 0.0)
        
        result = self.calculator.extract_nutritional_value(None, 'sugar')
        self.assertEqual(result, 0.0)
    
    def test_calculate_nutrient_score_positive(self):
        """Test nutrient score calculation with positive nutrients."""
        nutritional_data = {
            'fiber': 8.0,
            'protein': 12.0
        }
        
        score = self.calculator.calculate_nutrient_score(nutritional_data)
        # Fiber: 8/10 * 3 = 2.4, Protein: 12/10 * 2 = 2.4, Total: 4.8
        self.assertGreater(score, 0)
    
    def test_calculate_nutrient_score_negative(self):
        """Test nutrient score calculation with negative nutrients."""
        nutritional_data = {
            'sugar': 25.0,
            'saturated_fat': 15.0
        }
        
        score = self.calculator.calculate_nutrient_score(nutritional_data)
        # Should be negative due to high sugar and saturated fat
        self.assertLess(score, 0)
    
    def test_calculate_nutrient_score_mixed(self):
        """Test nutrient score calculation with mixed positive and negative nutrients."""
        nutritional_data = {
            'sugar': 10.0,      # Negative: 10/10 * -1.5 = -1.5
            'fiber': 5.0,       # Positive: 5/10 * 3 = 1.5
            'protein': 8.0      # Positive: 8/10 * 2 = 1.6
        }
        
        score = self.calculator.calculate_nutrient_score(nutritional_data)
        # Expected: -1.5 + 1.5 + 1.6 = 1.6
        self.assertGreater(score, 0)
    
    def test_calculate_with_string_nutritional_data(self):
        """Test calculation with string nutritional data."""
        product_data = {
            'barcode': '1234567890123',
            'nutritional': '{"sugar": "15", "fiber": "8"}'
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertIsInstance(result, (int, float))
            self.assertGreaterEqual(result, 0)
            self.assertLessEqual(result, 100)
            self.assertEqual(source, 'local')
    
    def test_calculate_with_invalid_json_nutritional_data(self):
        """Test calculation with invalid JSON nutritional data."""
        product_data = {
            'barcode': '1234567890123',
            'nutritional': 'invalid json'
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            # Should handle invalid JSON gracefully
            self.assertIsInstance(result, (int, float))
            self.assertEqual(source, 'local')
    
    def test_calculate_no_barcode_or_name(self):
        """Test calculation when no barcode or name is provided."""
        product_data = {
            'nutritional': {
                'sugar': '10',
                'fiber': '5'
            }
        }
        
        with patch.object(self.calculator, 'fetch_nutriscore_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertIsInstance(result, (int, float))
            self.assertGreaterEqual(result, 0)
            self.assertLessEqual(result, 100)
            self.assertEqual(source, 'local')


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests() 