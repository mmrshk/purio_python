#!/usr/bin/env python3
"""
Test script for AdditivesScoreCalculator functionality.
"""

import sys
import unittest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))
from processors.scoring.types.additives_score import AdditivesScoreCalculator


class TestAdditivesScoreCalculator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            # Mock Supabase client
            with patch('processors.scoring.types.additives_score.create_client') as mock_create_client:
                self.mock_supabase = Mock()
                mock_create_client.return_value = self.mock_supabase
                self.calculator = AdditivesScoreCalculator()
                
                # Set up the mock chain for Supabase queries
                self.mock_table = Mock()
                self.mock_select = Mock()
                self.mock_eq = Mock()
                self.mock_execute = Mock()
                
                # Set up the chain properly
                self.mock_supabase.table.return_value = self.mock_table
                self.mock_table.select.return_value = self.mock_select
                self.mock_select.eq.return_value = self.mock_eq
                self.mock_eq.execute.return_value = self.mock_execute
    
    def test_init_success(self):
        """Test successful initialization."""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            with patch('processors.scoring.types.additives_score.create_client') as mock_create_client:
                mock_supabase = Mock()
                mock_create_client.return_value = mock_supabase
                calculator = AdditivesScoreCalculator()
                
                self.assertEqual(calculator.risk_scores, {
                    'Free risk': 100,
                    'Low risk': 75,
                    'Moderate risk': 50,
                    'High risk': 0,
                })
    
    def test_get_additive_risk_score_valid_risk_levels(self):
        """Test getting risk scores for valid risk levels."""
        test_cases = [
            ({'risk_level': 'Free risk'}, 100),
            ({'risk_level': 'Low risk'}, 75),
            ({'risk_level': 'Moderate risk'}, 50),
            ({'risk_level': 'High risk'}, 0),
        ]
        
        for additive, expected_score in test_cases:
            with self.subTest(risk_level=additive['risk_level']):
                score = self.calculator.get_additive_risk_score(additive)
                self.assertEqual(score, expected_score)
    
    def test_get_additive_risk_score_unknown_risk_level(self):
        """Test getting risk score for unknown risk level raises error."""
        additive = {'risk_level': 'Unknown risk'}
        
        with self.assertRaises(ValueError) as context:
            self.calculator.get_additive_risk_score(additive)
        self.assertIn("Unknown risk level: Unknown risk", str(context.exception))
    
    def test_get_additive_risk_score_none_risk_level(self):
        """Test getting risk score for None risk level raises error."""
        additive = {'risk_level': None}
        
        with self.assertRaises(ValueError) as context:
            self.calculator.get_additive_risk_score(additive)
        self.assertIn("Unknown risk level: None", str(context.exception))
    
    def test_calculate_from_product_additives_no_additives(self):
        """Test calculation when product has no additives."""
        # Mock Supabase response for product with no additives
        mock_result = Mock()
        mock_result.data = []
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Test perfect score for products with no additives
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['additives_found'], 0)
        self.assertEqual(len(result['high_risk_additives']), 0)
        
        # Test risk breakdown for no additives
        expected_breakdown = {'free': 0, 'low': 0, 'moderate': 0, 'high': 0}
        self.assertEqual(result['risk_breakdown'], expected_breakdown)
        
        # Verify perfect score logic
        self.assertEqual(result['score'], 100)  # No additives = perfect score
    
    def test_calculate_from_product_additives_with_valid_additives(self):
        """Test calculation with valid additives."""
        # Mock Supabase response for product with additives
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E100',
                    'name': 'Curcumin',
                    'risk_level': 'Free risk'
                }
            },
            {
                'additive_id': 2,
                'additives': {
                    'code': 'E250',
                    'name': 'Sodium Nitrite',
                    'risk_level': 'High risk'
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Expected: (100 + 0) / 2 = 50, but capped at 49 due to high-risk additive
        self.assertEqual(result['score'], 49)
        self.assertEqual(result['additives_found'], 2)
        self.assertEqual(len(result['high_risk_additives']), 1)
        self.assertEqual(result['high_risk_additives'][0]['code'], 'E250')
    
    def test_calculate_from_product_additives_with_null_risk_level(self):
        """Test calculation skips product when additive has NULL risk level."""
        # Mock Supabase response with NULL risk level
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E999',
                    'name': 'Unknown Additive',
                    'risk_level': None
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        self.assertIsNone(result)
    
    def test_calculate_from_product_additives_with_empty_risk_level(self):
        """Test calculation skips product when additive has empty risk level."""
        # Mock Supabase response with empty risk level
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E999',
                    'name': 'Unknown Additive',
                    'risk_level': ''
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        self.assertIsNone(result)
    
    def test_calculate_from_product_additives_supabase_error(self):
        """Test calculation handles Supabase errors."""
        # Mock Supabase error
        mock_result = Mock()
        mock_result.error = "Database connection failed"
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        self.assertIsNone(result)
    
    def test_calculate_from_product_additives_exception(self):
        """Test calculation handles exceptions."""
        # Mock exception
        self.mock_execute.side_effect = Exception("Test exception")
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = self.mock_execute
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        self.assertIsNone(result)
    
    def test_calculate_with_product_id_success(self):
        """Test main calculate method with valid product ID."""
        product_data = {'id': 'test-product-id'}
        
        # Mock the calculate_from_product_additives method
        with patch.object(self.calculator, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = {'score': 75, 'additives_found': 2, 'high_risk_additives': [], 'risk_breakdown': {'free': 1, 'low': 1, 'moderate': 0, 'high': 0}}
            
            result = self.calculator.calculate(product_data)
            
            self.assertEqual(result, 75)
            mock_calc.assert_called_once_with('test-product-id')
    
    def test_calculate_with_product_id_skipped(self):
        """Test main calculate method when product is skipped."""
        product_data = {'id': 'test-product-id'}
        
        # Mock the calculate_from_product_additives method to return None
        with patch.object(self.calculator, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = None
            
            result = self.calculator.calculate(product_data)
            
            self.assertIsNone(result)
    
    def test_calculate_without_product_id(self):
        """Test main calculate method without product ID."""
        product_data = {'name': 'Test Product'}
        
        result = self.calculator.calculate(product_data)
        
        self.assertIsNone(result)
    
    def test_calculate_with_empty_product_data(self):
        """Test main calculate method with empty product data."""
        product_data = {}
        
        result = self.calculator.calculate(product_data)
        
        self.assertIsNone(result)
    
    def test_risk_breakdown_calculation(self):
        """Test risk breakdown calculation."""
        # Mock Supabase response with various risk levels
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E100',
                    'name': 'Curcumin',
                    'risk_level': 'Free risk'
                }
            },
            {
                'additive_id': 2,
                'additives': {
                    'code': 'E250',
                    'name': 'Sodium Nitrite',
                    'risk_level': 'High risk'
                }
            },
            {
                'additive_id': 3,
                'additives': {
                    'code': 'E300',
                    'name': 'Ascorbic Acid',
                    'risk_level': 'Low risk'
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Test risk breakdown counts
        expected_breakdown = {'free': 1, 'low': 1, 'moderate': 0, 'high': 1}
        self.assertEqual(result['risk_breakdown'], expected_breakdown)
        
        # Test additives found count
        self.assertEqual(result['additives_found'], 3)
        
        # Test high-risk additives list
        self.assertEqual(len(result['high_risk_additives']), 1)
        self.assertEqual(result['high_risk_additives'][0]['code'], 'E250')
        self.assertEqual(result['high_risk_additives'][0]['name'], 'Sodium Nitrite')
        self.assertEqual(result['high_risk_additives'][0]['risk_level'], 'High risk')
        
        # Test final score calculation
        # Expected: (100 + 0 + 75) / 3 = 58.33, but capped at 49 due to high-risk additive
        self.assertEqual(result['score'], 49)
        
        # Test that the score is capped due to high-risk additive
        self.assertTrue(len(result['high_risk_additives']) > 0)
        self.assertEqual(result['score'], 49)  # Confirms high-risk cap is applied
    
    def test_high_risk_cap_logic(self):
        """Test that high-risk additives cap the final score at 49."""
        # Mock Supabase response with mixed risk levels
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E100',
                    'name': 'Curcumin',
                    'risk_level': 'Free risk'
                }
            },
            {
                'additive_id': 2,
                'additives': {
                    'code': 'E250',
                    'name': 'Sodium Nitrite',
                    'risk_level': 'High risk'
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Expected: (100 + 0) / 2 = 50, but capped at 49 due to high-risk additive
        self.assertEqual(result['score'], 49)
        self.assertEqual(len(result['high_risk_additives']), 1)
    
    def test_no_high_risk_no_cap(self):
        """Test that products without high-risk additives are not capped."""
        # Mock Supabase response with only low-risk additives
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E100',
                    'name': 'Curcumin',
                    'risk_level': 'Free risk'
                }
            },
            {
                'additive_id': 2,
                'additives': {
                    'code': 'E300',
                    'name': 'Ascorbic Acid',
                    'risk_level': 'Low risk'
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Test risk breakdown counts
        expected_breakdown = {'free': 1, 'low': 1, 'moderate': 0, 'high': 0}
        self.assertEqual(result['risk_breakdown'], expected_breakdown)
        
        # Test additives found count
        self.assertEqual(result['additives_found'], 2)
        
        # Test no high-risk additives
        self.assertEqual(len(result['high_risk_additives']), 0)
        
        # Test final score calculation
        # Expected: (100 + 75) / 2 = 87.5, rounded to 87
        # No high-risk additives, so no cap applied
        self.assertEqual(result['score'], 87)

    def test_multiple_high_risk_additives(self):
        """Test calculation with multiple high-risk additives."""
        # Mock Supabase response with multiple high-risk additives
        mock_result = Mock()
        mock_result.data = [
            {
                'additive_id': 1,
                'additives': {
                    'code': 'E250',
                    'name': 'Sodium Nitrite',
                    'risk_level': 'High risk'
                }
            },
            {
                'additive_id': 2,
                'additives': {
                    'code': 'E251',
                    'name': 'Sodium Nitrate',
                    'risk_level': 'High risk'
                }
            },
            {
                'additive_id': 3,
                'additives': {
                    'code': 'E100',
                    'name': 'Curcumin',
                    'risk_level': 'Free risk'
                }
            }
        ]
        mock_result.error = None
        self.mock_execute.return_value = mock_result
        
        # Ensure the mock chain is properly configured
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.eq.return_value = self.mock_eq
        self.mock_eq.execute.return_value = mock_result
        
        result = self.calculator.calculate_from_product_additives('test-product-id')
        
        # Test risk breakdown counts
        expected_breakdown = {'free': 1, 'low': 0, 'moderate': 0, 'high': 2}
        self.assertEqual(result['risk_breakdown'], expected_breakdown)
        
        # Test additives found count
        self.assertEqual(result['additives_found'], 3)
        
        # Test high-risk additives list
        self.assertEqual(len(result['high_risk_additives']), 2)
        self.assertEqual(result['high_risk_additives'][0]['code'], 'E250')
        self.assertEqual(result['high_risk_additives'][1]['code'], 'E251')
        
        # Test final score calculation
        # Expected: (0 + 0 + 100) / 3 = 33.33, but capped at 49 due to high-risk additives
        self.assertEqual(result['score'], 33)



def run_tests():
    """Run the test suite."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests() 