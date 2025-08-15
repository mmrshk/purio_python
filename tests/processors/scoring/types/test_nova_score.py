#!/usr/bin/env python3
"""
Test script for NovaScoreCalculator functionality.
"""

import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).resolve().parents[4]))


class TestNovaScoreCalculator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the IngredientsChecker import to avoid file dependencies
        with patch('ingredients.check_ingredients.IngredientsChecker'):
            from processors.scoring.types.nova_score import NovaScoreCalculator
            self.calculator = NovaScoreCalculator()
    
    def test_nova_map_values(self):
        """Test NOVA group to score mapping."""
        self.assertEqual(self.calculator.NOVA_MAP[1], 100)  # Unprocessed
        self.assertEqual(self.calculator.NOVA_MAP[2], 80)   # Processed ingredients
        self.assertEqual(self.calculator.NOVA_MAP[3], 50)   # Processed foods
        self.assertEqual(self.calculator.NOVA_MAP[4], 20)   # Ultra-processed
    
    def test_fetch_nova_by_ean_success(self):
        """Test successful NOVA fetch by EAN."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'product': {
                'nova-group': 2
            }
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nova_from_off(ean='1234567890123')
            self.assertEqual(result, 2)
    
    def test_fetch_nova_by_ean_no_group(self):
        """Test NOVA fetch by EAN when no group is available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'product': {}
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nova_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_fetch_nova_by_name_success(self):
        """Test successful NOVA fetch by product name."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'products': [
                {'nova-group': 3}
            ]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nova_from_off(product_name='Test Product')
            self.assertEqual(result, 3)
    
    def test_fetch_nova_by_name_no_products(self):
        """Test NOVA fetch by name when no products found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'products': []
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nova_from_off(product_name='Unknown Product')
            self.assertIsNone(result)
    
    def test_fetch_nova_api_error(self):
        """Test NOVA fetch when API returns error."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('requests.get', return_value=mock_response):
            result = self.calculator.fetch_nova_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_fetch_nova_request_exception(self):
        """Test NOVA fetch when request raises exception."""
        with patch('requests.get', side_effect=Exception("Network error")):
            result = self.calculator.fetch_nova_from_off(ean='1234567890123')
            self.assertIsNone(result)
    
    def test_get_nova_distribution_from_ingredients_success(self):
        """Test getting NOVA distribution from ingredients successfully."""
        product_data = {
            'name': 'Test Product',
            'specifications': {
                'ingredients': 'Lapte de vaca, zahar, acid citric'
            }
        }
        
        # Mock the ingredients checker result
        mock_result = {
            'nova_scores': [1, 2, 4]  # Natural, culinary, ultra-processed
        }
        
        with patch.object(self.calculator.ingredients_checker, 'check_product_ingredients', return_value=mock_result):
            result = self.calculator.get_nova_distribution_from_ingredients(product_data)
            self.assertEqual(result, [1, 2, 4])
    
    def test_get_nova_distribution_no_specifications(self):
        """Test getting NOVA distribution when no specifications."""
        product_data = {
            'name': 'Test Product'
        }
        
        result = self.calculator.get_nova_distribution_from_ingredients(product_data)
        self.assertIsNone(result)
    
    def test_get_nova_distribution_no_ingredients(self):
        """Test getting NOVA distribution when no ingredients."""
        product_data = {
            'name': 'Test Product',
            'specifications': {}
        }
        
        result = self.calculator.get_nova_distribution_from_ingredients(product_data)
        self.assertIsNone(result)
    
    def test_calculate_nova_from_distribution_nova_4(self):
        """Test NOVA calculation when NOVA 4 ingredients are present."""
        nova_scores = [1, 2, 4, 1, 2]  # Contains NOVA 4
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertEqual(nova_group, 4)  # Should return NOVA 4 (ultra-processed)
    
    def test_calculate_nova_from_distribution_nova_3(self):
        """Test NOVA calculation when NOVA 3 ingredients are present."""
        nova_scores = [1, 2, 3, 1]  # Contains NOVA 3
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertEqual(nova_group, 3)  # Should return NOVA 3 (processed)
    
    def test_calculate_nova_from_distribution_nova_2_only(self):
        """Test NOVA calculation when only NOVA 2 ingredients are present."""
        nova_scores = [2, 2, 2]  # Only NOVA 2 (culinary ingredients)
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertEqual(nova_group, 2)  # Should return NOVA 2 (culinary)
    
    def test_calculate_nova_from_distribution_nova_1_and_2(self):
        """Test NOVA calculation when mix of NOVA 1 and 2 ingredients."""
        nova_scores = [1, 2, 1, 2]  # Mix of natural and culinary
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertEqual(nova_group, 3)  # Should return NOVA 3 (processed)
    
    def test_calculate_nova_from_distribution_nova_1_only(self):
        """Test NOVA calculation when only NOVA 1 ingredients are present."""
        nova_scores = [1, 1, 1]  # Only NOVA 1 (natural ingredients)
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertEqual(nova_group, 1)  # Should return NOVA 1 (natural)
    
    def test_calculate_nova_from_distribution_empty(self):
        """Test NOVA calculation with empty distribution."""
        nova_scores = []
        nova_group = self.calculator.calculate_nova_from_distribution(nova_scores)
        self.assertIsNone(nova_group)
    
    def test_calculate_nova_from_distribution_none(self):
        """Test NOVA calculation with None distribution."""
        nova_group = self.calculator.calculate_nova_from_distribution(None)
        self.assertIsNone(nova_group)
    
    def test_calculate_local_nova_with_ingredients(self):
        """Test local NOVA calculation using ingredients."""
        product_data = {
            'name': 'Test Product',
            'specifications': {
                'ingredients': 'Lapte de vaca, acid citric, arome'
            }
        }
        
        # Mock the ingredients checker result
        mock_result = {
            'nova_scores': [1, 4, 4]  # Natural, ultra-processed, ultra-processed
        }
        
        with patch.object(self.calculator.ingredients_checker, 'check_product_ingredients', return_value=mock_result):
            result = self.calculator.calculate_local_nova(product_data)
            self.assertEqual(result, 4)  # Should return NOVA 4 (ultra-processed)
    
    def test_calculate_local_nova_no_ingredients(self):
        """Test local NOVA calculation when no ingredients."""
        product_data = {
            'name': 'Test Product',
            'specifications': {}
        }
        
        result = self.calculator.calculate_local_nova(product_data)
        self.assertIsNone(result)
    
    def test_calculate_with_api_success(self):
        """Test calculation when API returns NOVA group."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product'
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=2):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 80)  # NOVA group 2 maps to 80
            self.assertEqual(source, 'api')
    
    def test_calculate_fallback_to_ingredients(self):
        """Test calculation falls back to ingredients when API fails."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product',
            'specifications': {
                'ingredients': 'Lapte de vaca, acid citric'
            }
        }
        
        # Mock API failure and ingredients success
        mock_result = {
            'nova_scores': [1, 4]  # Natural, ultra-processed
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            with patch.object(self.calculator.ingredients_checker, 'check_product_ingredients', return_value=mock_result):
                result, source = self.calculator.calculate(product_data)
                self.assertEqual(result, 20)  # NOVA group 4 maps to 20
                self.assertEqual(source, 'local')
    
    def test_calculate_no_ingredients_available(self):
        """Test calculation when no ingredients are available."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product',
            'specifications': {}
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertIsNone(result)
            self.assertIsNone(source)
    
    def test_calculate_edge_cases(self):
        """Test calculation with edge cases."""
        # Test with None values
        product_data = {
            'barcode': None,
            'name': None,
            'specifications': None
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertIsNone(result)
            self.assertIsNone(source)
        
        # Test with empty specifications
        product_data = {
            'barcode': '',
            'name': '',
            'specifications': {}
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertIsNone(result)
            self.assertIsNone(source)


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests() 