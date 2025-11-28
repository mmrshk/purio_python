#!/usr/bin/env python3
"""
Comprehensive test for the health scoring system.
Tests all three components: Nova Score, Nutri-Score, and Additives Score.
"""

import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

sys.path.append('.')
from processors.scoring.types.nutri_score import NutriScoreCalculator
from processors.scoring.types.additives_score import AdditivesScoreCalculator
from processors.scoring.types.nova_score import NovaScoreCalculator


class TestHealthScoring(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables for Supabase
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            # Mock Supabase client
            with patch('processors.scoring.types.additives_score.create_client') as mock_create_client:
                self.mock_supabase = Mock()
                mock_create_client.return_value = self.mock_supabase
                
                # Initialize calculators
                self.nutri_calc = NutriScoreCalculator()
                self.additives_calc = AdditivesScoreCalculator()
                self.nova_calc = NovaScoreCalculator()
    
    def calculate_final_health_score(self, nutri, additives, nova):
        """Calculate final health score using the same formula as the main system."""
        # If any score is None, return None (cannot calculate final score)
        if nutri is None or additives is None or nova is None:
            return None
        return int(round(nutri * 0.4 + additives * 0.3 + nova * 0.3))
    
    def test_health_scoring_complete_product(self):
        """Test health scoring with a complete product that has all data."""
        # Mock product data with all components
        product_data = {
            'id': 'test-product-1',
            'name': 'Organic Apple Juice',
            'barcode': '1234567890123',
            'nutritional': {
                'fat': '0.1',
                'sugar': '10.5',
                'protein': '0.3',
                'carbohydrates': '11.2',
                'fiber': '0.5',
                'sodium': '5'
            },
            'ingredients': 'Organic apple juice, vitamin C'
        }
        
        # Mock the additives calculation to return a valid score
        with patch.object(self.additives_calc, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = {
                'score': 75,
                'additives_found': 1,
                'high_risk_additives': [],
                'risk_breakdown': {'free': 1, 'low': 0, 'moderate': 0, 'high': 0}
            }
            
            # Mock Supabase response for additives
            mock_result = Mock()
            mock_result.data = [
                {
                    'additive_id': 1,
                    'additives': {
                        'code': 'E300',
                        'name': 'Ascorbic Acid',
                        'risk_level': 'Low risk'
                    }
                }
            ]
            mock_result.error = None
            self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            # Calculate individual scores
            nutri_result = self.nutri_calc.calculate(product_data)
            additives_score = self.additives_calc.calculate(product_data)
            nova_result = self.nova_calc.calculate(product_data)
            
            # Extract scores from tuples
            nutri_score = nutri_result[0] if isinstance(nutri_result, tuple) else nutri_result
            nova_score = nova_result[0] if isinstance(nova_result, tuple) else nova_result
            
            final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            # Verify individual scores
            self.assertIsNotNone(nutri_score)
            self.assertIsNotNone(additives_score)
            # Nova score is None since no Nova data is available in our product data
            self.assertIsNone(nova_score)
            # Final score should be None when Nova data is missing
            self.assertIsNone(final_score)
            
            # Verify score ranges
            self.assertGreaterEqual(nutri_score, 0)
            self.assertLessEqual(nutri_score, 100)
            self.assertGreaterEqual(additives_score, 0)
            self.assertLessEqual(additives_score, 100)
            # Nova score is None since no Nova data is available
            self.assertIsNone(nova_score)
            # Final score is None when Nova data is missing
            self.assertIsNone(final_score)
            
            print(f"\n✅ Complete Product Test:")
            print(f"  Nutri-Score: {nutri_score}")
            print(f"  Additives Score: {additives_score}")
            print(f"  Nova Score: {nova_score}")
            print(f"  Final Health Score: {final_score}")
    
    def test_health_scoring_missing_additives_data(self):
        """Test health scoring when additives data is missing (returns None)."""
        product_data = {
            'id': 'test-product-2',
            'name': 'Product Without Additives Data',
            'barcode': '1234567890124',
            'nutritional': {
                'fat': '2.0',
                'sugar': '15.0',
                'protein': '1.0'
            },
            'ingredients': 'Water, sugar, flavoring'
        }
        
        # Mock additives calculation to return None (no additives data)
        with patch.object(self.additives_calc, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = None
            
            # Mock Supabase response with no additives
            mock_result = Mock()
            mock_result.data = []
            mock_result.error = None
            self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            # Calculate individual scores
            nutri_result = self.nutri_calc.calculate(product_data)
            additives_score = self.additives_calc.calculate(product_data)
            nova_result = self.nova_calc.calculate(product_data)
            
            # Extract scores from tuples
            nutri_score = nutri_result[0] if isinstance(nutri_result, tuple) else nutri_result
            nova_score = nova_result[0] if isinstance(nova_result, tuple) else nova_result
            
            final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            # Verify that final score is None when additives data is missing
            self.assertIsNotNone(nutri_score)
            # Nova score is None since no Nova data is available
            self.assertIsNone(nova_score)
            self.assertIsNone(additives_score)
            self.assertIsNone(final_score)
            
            print(f"\n⚠️  Missing Additives Data Test:")
            print(f"  Nutri-Score: {nutri_score}")
            print(f"  Additives Score: {additives_score}")
            print(f"  Nova Score: {nova_score}")
            print(f"  Final Health Score: {final_score}")
    
    def test_health_scoring_high_risk_additives(self):
        """Test health scoring with high-risk additives."""
        product_data = {
            'id': 'test-product-3',
            'name': 'Product with High-Risk Additives',
            'barcode': '1234567890125',
            'nutritional': {
                'fat': '5.0',
                'sugar': '20.0',
                'protein': '2.0'
            },
            'ingredients': 'Sugar, artificial colors, preservatives'
        }
        
        # Mock additives calculation with high-risk additives
        with patch.object(self.additives_calc, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = {
                'score': 49,  # Capped due to high-risk additives
                'additives_found': 2,
                'high_risk_additives': [
                    {'code': 'E250', 'name': 'Sodium Nitrite', 'risk_level': 'High risk'}
                ],
                'risk_breakdown': {'free': 0, 'low': 0, 'moderate': 0, 'high': 1}
            }
            
            # Mock Supabase response with high-risk additive
            mock_result = Mock()
            mock_result.data = [
                {
                    'additive_id': 1,
                    'additives': {
                        'code': 'E250',
                        'name': 'Sodium Nitrite',
                        'risk_level': 'High risk'
                    }
                }
            ]
            mock_result.error = None
            self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            # Calculate individual scores
            nutri_result = self.nutri_calc.calculate(product_data)
            additives_score = self.additives_calc.calculate(product_data)
            nova_result = self.nova_calc.calculate(product_data)
            
            # Extract scores from tuples
            nutri_score = nutri_result[0] if isinstance(nutri_result, tuple) else nutri_result
            nova_score = nova_result[0] if isinstance(nova_result, tuple) else nova_result
            
            final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            # Verify scores
            self.assertIsNotNone(nutri_score)
            self.assertIsNotNone(additives_score)
            # Nova score is None since no Nova data is available
            self.assertIsNone(nova_score)
            # Final score should be None when Nova data is missing
            self.assertIsNone(final_score)
            
            # Verify that additives score is capped at 49
            self.assertEqual(additives_score, 49)
            
            print(f"\n🔴 High-Risk Additives Test:")
            print(f"  Nutri-Score: {nutri_score}")
            print(f"  Additives Score: {additives_score} (capped due to high-risk)")
            print(f"  Nova Score: {nova_score}")
            print(f"  Final Health Score: {final_score}")
    
    def test_health_scoring_perfect_product(self):
        """Test health scoring with a perfect product (high scores)."""
        product_data = {
            'id': 'test-product-4',
            'name': 'Perfect Health Product',
            'barcode': '1234567890126',
            'nutritional': {
                'fat': '0.1',
                'sugar': '2.0',
                'protein': '8.0',
                'fiber': '5.0',
                'sodium': '10'
            },
            'ingredients': 'Organic whole grain oats, organic honey, natural flavors'
        }
        
        # Mock additives calculation with perfect score
        with patch.object(self.additives_calc, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = {
                'score': 100,  # Perfect additives score
                'additives_found': 0,
                'high_risk_additives': [],
                'risk_breakdown': {'free': 0, 'low': 0, 'moderate': 0, 'high': 0}
            }
            
            # Mock Supabase response with no additives
            mock_result = Mock()
            mock_result.data = []
            mock_result.error = None
            self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            # Calculate individual scores
            nutri_result = self.nutri_calc.calculate(product_data)
            additives_score = self.additives_calc.calculate(product_data)
            nova_result = self.nova_calc.calculate(product_data)
            
            # Extract scores from tuples
            nutri_score = nutri_result[0] if isinstance(nutri_result, tuple) else nutri_result
            nova_score = nova_result[0] if isinstance(nova_result, tuple) else nova_result
            
            final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            # Verify scores
            self.assertIsNotNone(nutri_score)
            self.assertIsNotNone(additives_score)
            # Nova score is None since no Nova data is available
            self.assertIsNone(nova_score)
            # Final score should be None when Nova data is missing
            self.assertIsNone(final_score)
            
            # Verify perfect additives score
            self.assertEqual(additives_score, 100)
            
            print(f"\n🟢 Perfect Product Test:")
            print(f"  Nutri-Score: {nutri_score}")
            print(f"  Additives Score: {additives_score} (perfect)")
            print(f"  Nova Score: {nova_score}")
            print(f"  Final Health Score: {final_score}")
    
    def test_health_scoring_weighted_calculation(self):
        """Test that the weighted calculation formula works correctly."""
        # Test the weighted calculation with known values
        nutri_score = 80
        additives_score = 60
        nova_score = 70
        
        final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
        
        # Expected: (80 * 0.4) + (60 * 0.3) + (70 * 0.3) = 32 + 18 + 21 = 71
        expected_score = int(round(nutri_score * 0.4 + additives_score * 0.3 + nova_score * 0.3))
        
        self.assertEqual(final_score, expected_score)
        self.assertEqual(final_score, 71)
        
        print(f"\n📊 Weighted Calculation Test:")
        print(f"  Nutri-Score: {nutri_score} (weight: 0.4)")
        print(f"  Additives Score: {additives_score} (weight: 0.3)")
        print(f"  Nova Score: {nova_score} (weight: 0.3)")
        print(f"  Final Health Score: {final_score}")
        print(f"  Calculation: ({nutri_score} × 0.4) + ({additives_score} × 0.3) + ({nova_score} × 0.3) = {final_score}")
    
    def test_health_scoring_null_handling(self):
        """Test that None values are handled correctly in final calculation."""
        # Test with one None component
        nutri_score = 80
        additives_score = None
        nova_score = 70
        
        final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
        
        # Should return None when any component is None
        self.assertIsNone(final_score)
        
        print(f"\n❌ Null Handling Test:")
        print(f"  Nutri-Score: {nutri_score}")
        print(f"  Additives Score: {additives_score}")
        print(f"  Nova Score: {nova_score}")
        print(f"  Final Health Score: {final_score} (None due to missing data)")
    
    def test_health_scoring_nova_none(self):
        """Test health scoring when Nova score is None (no Nova data available)."""
        product_data = {
            'id': 'test-product-5',
            'name': 'Product Without Nova Data',
            'barcode': '1234567890127',
            'nutritional': {
                'fat': '2.0',
                'sugar': '15.0',
                'protein': '1.0'
            },
            'ingredients': 'Water, sugar, flavoring'
        }
        
        # Mock additives calculation to return a valid score
        with patch.object(self.additives_calc, 'calculate_from_product_additives') as mock_calc:
            mock_calc.return_value = {
                'score': 75,
                'additives_found': 1,
                'high_risk_additives': [],
                'risk_breakdown': {'free': 1, 'low': 0, 'moderate': 0, 'high': 0}
            }
            
            # Mock Supabase response for additives
            mock_result = Mock()
            mock_result.data = [
                {
                    'additive_id': 1,
                    'additives': {
                        'code': 'E300',
                        'name': 'Ascorbic Acid',
                        'risk_level': 'Low risk'
                    }
                }
            ]
            mock_result.error = None
            self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            
            # Calculate individual scores
            nutri_result = self.nutri_calc.calculate(product_data)
            additives_score = self.additives_calc.calculate(product_data)
            nova_result = self.nova_calc.calculate(product_data)
            
            # Extract scores from tuples
            nutri_score = nutri_result[0] if isinstance(nutri_result, tuple) else nutri_result
            nova_score = nova_result[0] if isinstance(nova_result, tuple) else nova_result
            
            final_score = self.calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            # Verify that final score is None when Nova data is missing
            self.assertIsNotNone(nutri_score)
            self.assertIsNotNone(additives_score)
            self.assertIsNone(nova_score)
            self.assertIsNone(final_score)
            
            print(f"\n⚠️  Nova None Test:")
            print(f"  Nutri-Score: {nutri_score}")
            print(f"  Additives Score: {additives_score}")
            print(f"  Nova Score: {nova_score}")
            print(f"  Final Health Score: {final_score} (None due to missing Nova data)")


def run_tests():
    """Run the test suite."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests() 