#!/usr/bin/env python3
"""
Test script for SupabaseIngredientsChecker functionality with AI fallback.
"""

import sys
import unittest
import os
from unittest.mock import patch, Mock
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).resolve().parents[3]))
from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker


class TestSupabaseIngredientsChecker(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock Supabase response data
        self.mock_ingredients_data = [
            {'id': 1, 'name': 'milk', 'ro_name': 'lapte', 'nova_score': 1},
            {'id': 2, 'name': 'sugar', 'ro_name': 'zahăr', 'nova_score': 2},
            {'id': 3, 'name': 'salt', 'ro_name': 'sare', 'nova_score': 2},
            {'id': 4, 'name': 'flour', 'ro_name': 'făină', 'nova_score': 2},
            {'id': 5, 'name': 'eggs', 'ro_name': 'ouă', 'nova_score': 1},
            {'id': 6, 'name': 'butter', 'ro_name': 'unt', 'nova_score': 2},
            {'id': 7, 'name': 'yeast', 'ro_name': 'drojdie', 'nova_score': 1},
            {'id': 8, 'name': 'water', 'ro_name': 'apă', 'nova_score': 1},
        ]
        
        # Mock Supabase client
        self.mock_supabase = Mock()
        mock_result = Mock()
        mock_result.data = self.mock_ingredients_data
        mock_result.error = None
        self.mock_supabase.table.return_value.select.return_value.execute.return_value = mock_result
        
        # Mock AI parser
        self.mock_ai_parser = Mock()
        self.mock_ai_parser.parse_ingredients_from_name.return_value = {
            'extracted_ingredients': ['făină', 'apă', 'sare', 'drojdie'],
            'ai_generated': True,
            'source': 'ai_parser'
        }
        self.mock_ai_parser.get_stats.return_value = {
            'ai_requests_made': 1,
            'ai_requests_successful': 1,
            'ai_requests_failed': 0,
            'ingredients_extracted': 4
        }
        self.mock_ai_parser.reset_stats.return_value = None

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_init_without_ai(self, mock_create_client):
        """Test initialization without AI fallback."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        self.assertFalse(checker.use_ai_fallback)
        self.assertIsNone(checker.ai_parser)
        self.assertEqual(len(checker.ingredients_data), 16)  # 8 ingredients * 2 (EN + RO)
        
        # Check stats initialization
        expected_stats = {
            'products_processed': 0,
            'products_with_ingredients': 0,
            'products_with_ai_ingredients': 0,
            'total_ingredients_found': 0,
            'ingredients_matched': 0,
            'ingredients_not_matched': 0,
            'nova_scores': {1: 0, 2: 0, 3: 0, 4: 0},
            'ai_stats': {}
        }
        self.assertEqual(checker.get_stats(), expected_stats)

    @patch('ingredients.supabase_ingredients_checker.create_client')
    @patch('ingredients.supabase_ingredients_checker.AIIngredientsParser')
    def test_init_with_ai(self, mock_ai_class, mock_create_client):
        """Test initialization with AI fallback."""
        mock_create_client.return_value = self.mock_supabase
        mock_ai_class.return_value = self.mock_ai_parser
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=True)
        
        self.assertTrue(checker.use_ai_fallback)
        self.assertEqual(checker.ai_parser, self.mock_ai_parser)
        mock_ai_class.assert_called_once_with(model="gpt-3.5-turbo")

    @patch('ingredients.supabase_ingredients_checker.create_client')
    @patch('ingredients.supabase_ingredients_checker.AIIngredientsParser')
    def test_init_ai_failure(self, mock_ai_class, mock_create_client):
        """Test initialization when AI parser fails."""
        mock_create_client.return_value = self.mock_supabase
        mock_ai_class.side_effect = Exception("API key not found")
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=True)
        
        self.assertFalse(checker.use_ai_fallback)
        self.assertIsNone(checker.ai_parser)

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_check_product_with_ingredients(self, mock_create_client):
        """Test checking product that has ingredients in specifications."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        product = {
            'name': 'Lapte UHT 3.5% grăsime',
            'specifications': {'ingredients': 'lapte, vitamina d3'}
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['product_name'], 'Lapte UHT 3.5% grăsime')
        self.assertEqual(result['source'], 'specifications')
        self.assertIn('lapte', result['extracted_ingredients'])
        self.assertIn('vitamina d3', result['extracted_ingredients'])
        self.assertTrue(len(result['matches']) > 0)  # Should match 'lapte'
        self.assertFalse(result['ai_generated'])
        
        # Check stats
        stats = checker.get_stats()
        self.assertEqual(stats['products_processed'], 1)
        self.assertEqual(stats['products_with_ingredients'], 1)
        self.assertEqual(stats['products_with_ai_ingredients'], 0)

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_check_product_without_ingredients_no_ai(self, mock_create_client):
        """Test checking product without ingredients and no AI fallback."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        product = {
            'name': 'Pâine albă Auchan',
            'specifications': {'ingredients': ''}
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['product_name'], 'Pâine albă Auchan')
        self.assertEqual(result['source'], 'none')
        self.assertEqual(result['extracted_ingredients'], [])
        self.assertEqual(result['matches'], [])
        self.assertFalse(result['ai_generated'])

    @patch('ingredients.supabase_ingredients_checker.create_client')
    @patch('ingredients.supabase_ingredients_checker.AIIngredientsParser')
    def test_check_product_with_ai_fallback(self, mock_ai_class, mock_create_client):
        """Test checking product with AI fallback when no ingredients found."""
        mock_create_client.return_value = self.mock_supabase
        mock_ai_class.return_value = self.mock_ai_parser
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=True)
        
        product = {
            'name': 'Pâine albă Auchan',
            'specifications': {'ingredients': ''}
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['product_name'], 'Pâine albă Auchan')
        self.assertEqual(result['source'], 'ai_parser')
        self.assertEqual(result['extracted_ingredients'], ['făină', 'apă', 'sare', 'drojdie'])
        self.assertTrue(result['ai_generated'])
        self.assertEqual(len(result['matches']), 4)  # All AI ingredients should match
        
        # Verify AI was called
        self.mock_ai_parser.parse_ingredients_from_name.assert_called_once_with(
            'Pâine albă Auchan', ''
        )
        
        # Check stats
        stats = checker.get_stats()
        self.assertEqual(stats['products_processed'], 1)
        self.assertEqual(stats['products_with_ingredients'], 0)
        self.assertEqual(stats['products_with_ai_ingredients'], 1)

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_check_product_with_string_specifications(self, mock_create_client):
        """Test checking product with string specifications that need JSON parsing."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        product = {
            'name': 'Test Product',
            'specifications': '{"ingredients": "lapte, zahăr"}'
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['source'], 'specifications')
        self.assertIn('lapte', result['extracted_ingredients'])
        self.assertIn('zahăr', result['extracted_ingredients'])

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_check_product_with_invalid_specifications(self, mock_create_client):
        """Test checking product with invalid specifications JSON."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        product = {
            'name': 'Test Product',
            'specifications': 'invalid json'
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['source'], 'none')
        self.assertEqual(result['extracted_ingredients'], [])

    @patch('ingredients.supabase_ingredients_checker.create_client')
    @patch('ingredients.supabase_ingredients_checker.AIIngredientsParser')
    def test_ai_fallback_with_description(self, mock_ai_class, mock_create_client):
        """Test AI fallback using product description."""
        mock_create_client.return_value = self.mock_supabase
        mock_ai_class.return_value = self.mock_ai_parser
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=True)
        
        product = {
            'name': 'Branză de vaci 200g',
            'specifications': {},
            'description': 'Fresh cow cheese made from milk'
        }
        
        result = checker.check_product_ingredients(product)
        
        # Verify AI was called with description
        self.mock_ai_parser.parse_ingredients_from_name.assert_called_once_with(
            'Branză de vaci 200g', 'Fresh cow cheese made from milk'
        )

    @patch('ingredients.supabase_ingredients_checker.create_client')
    @patch('ingredients.supabase_ingredients_checker.AIIngredientsParser')
    def test_ai_fallback_failure(self, mock_ai_class, mock_create_client):
        """Test AI fallback when AI parser fails."""
        mock_create_client.return_value = self.mock_supabase
        mock_ai_parser = Mock()
        mock_ai_parser.parse_ingredients_from_name.return_value = {
            'extracted_ingredients': [],
            'ai_generated': False,
            'source': 'ai_parser_failed'
        }
        mock_ai_class.return_value = mock_ai_parser
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=True)
        
        product = {
            'name': 'Unknown Product',
            'specifications': {'ingredients': ''}
        }
        
        result = checker.check_product_ingredients(product)
        
        self.assertEqual(result['source'], 'ai_parser')
        self.assertEqual(result['extracted_ingredients'], [])
        self.assertTrue(result['ai_generated'])  # AI was attempted, so it's AI generated

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_reset_stats(self, mock_create_client):
        """Test resetting statistics."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        # Process a product to generate some stats
        product = {
            'name': 'Test Product',
            'specifications': {'ingredients': 'lapte'}
        }
        checker.check_product_ingredients(product)
        
        # Verify stats were updated
        stats = checker.get_stats()
        self.assertEqual(stats['products_processed'], 1)
        
        # Reset stats
        checker.reset_stats()
        
        # Verify stats were reset
        stats = checker.get_stats()
        self.assertEqual(stats['products_processed'], 0)
        self.assertEqual(stats['products_with_ingredients'], 0)
        self.assertEqual(stats['products_with_ai_ingredients'], 0)

    @patch('ingredients.supabase_ingredients_checker.create_client')
    def test_fuzzy_matching_validation(self, mock_create_client):
        """Test fuzzy matching validation rules."""
        mock_create_client.return_value = self.mock_supabase
        
        checker = SupabaseIngredientsChecker(use_ai_fallback=False)
        
        # Test valid match
        self.assertTrue(checker._is_valid_match('lapte', 'lapte', 95))
        
        # Test invalid match for short ingredients
        self.assertFalse(checker._is_valid_match('la', 'lapte', 90))
        
        # Test sorbat/sorbitol validation
        self.assertFalse(checker._is_valid_match('sorbat', 'serviceberry', 90))
        self.assertFalse(checker._is_valid_match('sorbitol', 'sorb', 90))
        
        # Test lecithin validation
        self.assertFalse(checker._is_valid_match('lecitina de soia', 'soybean', 90))
        self.assertTrue(checker._is_valid_match('lecitina de soia', 'soy lecithin', 95))

    def test_extract_ingredients_from_text(self):
        """Test ingredient extraction from text."""
        # Mock the Supabase client for this test
        with patch('ingredients.supabase_ingredients_checker.create_client') as mock_create_client:
            mock_create_client.return_value = self.mock_supabase
            
            checker = SupabaseIngredientsChecker(use_ai_fallback=False)
            
            # Test Romanian ingredients
            text_ro = "Ingrediente: lapte, zahăr, sare, făină"
            ingredients = checker.extract_ingredients_from_text(text_ro)
            expected = ['lapte', 'zahăr', 'sare', 'făină']
            self.assertEqual(set(ingredients), set(expected))
            self.assertEqual(len(ingredients), len(expected))
            
            # Test English ingredients
            text_en = "Ingredients: milk, sugar, salt, flour"
            ingredients = checker.extract_ingredients_from_text(text_en)
            expected = ['milk', 'sugar', 'salt', 'flour']
            self.assertEqual(set(ingredients), set(expected))
            self.assertEqual(len(ingredients), len(expected))
            
            # Test empty text
            ingredients = checker.extract_ingredients_from_text("")
            self.assertEqual(ingredients, [])
            
            # Test None text
            ingredients = checker.extract_ingredients_from_text(None)
            self.assertEqual(ingredients, [])


if __name__ == '__main__':
    # Set up environment variables for testing
    os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
    os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'test_key'
    
    unittest.main()
