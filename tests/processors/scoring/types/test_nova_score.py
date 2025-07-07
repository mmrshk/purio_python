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
from processors.scoring.types.nova_score import NovaScoreCalculator


class TestNovaScoreCalculator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
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
    
    def test_calculate_local_nova_group_1(self):
        """Test local NOVA calculation for group 1."""
        product_data = {'nova_group': 1}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 100)
    
    def test_calculate_local_nova_group_2(self):
        """Test local NOVA calculation for group 2."""
        product_data = {'nova_group': 2}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 75)
    
    def test_calculate_local_nova_group_3(self):
        """Test local NOVA calculation for group 3."""
        product_data = {'nova_group': 3}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 50)
    
    def test_calculate_local_nova_group_4(self):
        """Test local NOVA calculation for group 4."""
        product_data = {'nova_group': 4}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 25)
    
    def test_calculate_local_nova_invalid_value(self):
        """Test local NOVA calculation with invalid value."""
        product_data = {'nova_group': 'invalid'}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 50)  # Default fallback
    
    def test_calculate_local_nova_no_value(self):
        """Test local NOVA calculation with no value."""
        product_data = {}
        result = self.calculator.calculate_local_nova(product_data)
        self.assertEqual(result, 50)  # Default fallback
    
    def test_calculate_with_api_nova(self):
        """Test calculation when API returns NOVA group."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product'
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=2):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 80)  # NOVA group 2 maps to 80
            self.assertEqual(source, 'api')
    
    def test_calculate_fallback_to_local(self):
        """Test calculation falls back to local method when API fails."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product',
            'nova_group': 3
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 50)  # NOVA group 3 maps to 50
            self.assertEqual(source, 'local')
    
    def test_calculate_no_barcode_or_name(self):
        """Test calculation when no barcode or name is provided."""
        product_data = {
            'nova_group': 1
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 100)  # NOVA group 1 maps to 100
            self.assertEqual(source, 'local')
    
    def test_calculate_api_unknown_nova_group(self):
        """Test calculation when API returns unknown NOVA group."""
        product_data = {
            'barcode': '1234567890123',
            'name': 'Test Product'
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=5):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 50)  # Unknown group defaults to 50
            self.assertEqual(source, 'api')
    
    def test_calculate_string_nova_group(self):
        """Test calculation with string NOVA group value."""
        product_data = {
            'nova_group': '2'
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 75)  # String '2' should be converted to int
            self.assertEqual(source, 'local')
    
    def test_calculate_edge_cases(self):
        """Test calculation with edge cases."""
        # Test with None values
        product_data = {
            'barcode': None,
            'name': None,
            'nova_group': None
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 50)  # Default fallback
            self.assertEqual(source, 'local')
        
        # Test with empty string values
        product_data = {
            'barcode': '',
            'name': '',
            'nova_group': ''
        }
        
        with patch.object(self.calculator, 'fetch_nova_from_off', return_value=None):
            result, source = self.calculator.calculate(product_data)
            self.assertEqual(result, 50)  # Default fallback
            self.assertEqual(source, 'local')


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests() 