#!/usr/bin/env python3
"""
Test script for IngredientsInserter functionality.
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).resolve().parents[3]))
from ingredients.ingredients_inserter import IngredientsInserter


class TestIngredientsInserter(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables
        os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
        os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'test_key'
        
        # Mock Supabase client
        self.mock_supabase = Mock()
        
        # Mock successful insert response
        self.mock_insert_result = Mock()
        self.mock_insert_result.data = [{'id': 1, 'name': 'test_ingredient', 'ro_name': 'ingredient_test', 'nova_score': 1, 'created_by': 'ai_parser'}]
        self.mock_insert_result.error = None
        
        # Mock successful select response (no existing ingredients)
        self.mock_select_result = Mock()
        self.mock_select_result.data = []
        self.mock_select_result.error = None
        
        # Mock successful update response
        self.mock_update_result = Mock()
        self.mock_update_result.data = [{'id': 1, 'name': 'updated_ingredient', 'ro_name': 'ingredient_actualizat', 'nova_score': 2}]
        self.mock_update_result.error = None
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variables
        if 'SUPABASE_URL' in os.environ:
            del os.environ['SUPABASE_URL']
        if 'SUPABASE_SERVICE_ROLE_KEY' in os.environ:
            del os.environ['SUPABASE_SERVICE_ROLE_KEY']
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_init_success(self, mock_create_client):
        """Test successful initialization."""
        mock_create_client.return_value = self.mock_supabase
        
        inserter = IngredientsInserter()
        
        self.assertEqual(inserter.supabase, self.mock_supabase)
        
        # Check stats initialization
        expected_stats = {
            'ingredients_processed': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_updated': 0,
            'errors': 0,
            'duplicate_ingredients': 0
        }
        self.assertEqual(inserter.get_stats(), expected_stats)
    
    def test_init_missing_credentials(self):
        """Test initialization failure when credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                IngredientsInserter()
            
            self.assertIn("Supabase credentials are not set", str(context.exception))
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_insert_ingredient_success(self, mock_create_client):
        """Test successful ingredient insertion."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock no existing ingredient
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = self.mock_select_result
        
        # Mock successful insertion
        self.mock_supabase.table.return_value.insert.return_value.execute.return_value = self.mock_insert_result
        
        inserter = IngredientsInserter()
        
        result = inserter.insert_ingredient(
            name="test_ingredient",
            ro_name="ingredient_test",
            nova_score=1,
            created_by="ai_parser"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'inserted')
        self.assertEqual(result['ingredient_id'], 1)
        self.assertIn('Successfully inserted', result['message'])
        
        # Check stats
        stats = inserter.get_stats()
        self.assertEqual(stats['ingredients_processed'], 1)
        self.assertEqual(stats['ingredients_inserted'], 1)
        self.assertEqual(stats['errors'], 0)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_insert_ingredient_duplicate(self, mock_create_client):
        """Test ingredient insertion when ingredient already exists."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock existing ingredient found
        existing_ingredient = {'id': 1, 'name': 'test_ingredient', 'ro_name': 'ingredient_test'}
        mock_existing_result = Mock()
        mock_existing_result.data = [existing_ingredient]
        mock_existing_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing_result
        
        inserter = IngredientsInserter()
        
        result = inserter.insert_ingredient(
            name="test_ingredient",
            ro_name="ingredient_test",
            nova_score=1,
            created_by="ai_parser"
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['action'], 'skipped')
        self.assertEqual(result['reason'], 'duplicate')
        self.assertEqual(result['ingredient_id'], 1)
        self.assertIn('already exists', result['message'])
        
        # Check stats
        stats = inserter.get_stats()
        self.assertEqual(stats['ingredients_processed'], 1)
        self.assertEqual(stats['duplicate_ingredients'], 1)
        self.assertEqual(stats['ingredients_inserted'], 0)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_insert_ingredient_insertion_error(self, mock_create_client):
        """Test ingredient insertion when Supabase returns an error."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock no existing ingredient
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = self.mock_select_result
        
        # Mock insertion error
        mock_error_result = Mock()
        mock_error_result.data = None
        mock_error_result.error = "Database error"
        self.mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_error_result
        
        inserter = IngredientsInserter()
        
        result = inserter.insert_ingredient(
            name="test_ingredient",
            ro_name="ingredient_test",
            nova_score=1,
            created_by="ai_parser"
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['action'], 'error')
        self.assertEqual(result['reason'], 'insertion_failed')
        self.assertIn('Database error', result['error'])
        
        # Check stats
        stats = inserter.get_stats()
        self.assertEqual(stats['ingredients_processed'], 1)
        self.assertEqual(stats['errors'], 1)
        self.assertEqual(stats['ingredients_inserted'], 0)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_insert_ingredients_batch_success(self, mock_create_client):
        """Test successful batch ingredient insertion."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock no existing ingredients
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = self.mock_select_result
        
        # Mock successful insertions
        self.mock_supabase.table.return_value.insert.return_value.execute.return_value = self.mock_insert_result
        
        inserter = IngredientsInserter()
        
        test_ingredients = [
            {'name': 'flour', 'ro_name': 'făină', 'nova_score': 2, 'created_by': 'ai_parser'},
            {'name': 'sugar', 'ro_name': 'zahăr', 'nova_score': 2, 'created_by': 'ai_parser'},
            {'name': 'salt', 'ro_name': 'sare', 'nova_score': 2, 'created_by': 'ai_parser'}
        ]
        
        result = inserter.insert_ingredients_batch(test_ingredients)
        
        self.assertEqual(result['total_processed'], 3)
        self.assertEqual(result['successful_insertions'], 3)
        self.assertEqual(result['skipped_duplicates'], 0)
        self.assertEqual(result['errors'], 0)
        self.assertEqual(len(result['details']), 3)
        
        # Check stats
        stats = inserter.get_stats()
        self.assertEqual(stats['ingredients_processed'], 3)
        self.assertEqual(stats['ingredients_inserted'], 3)
        self.assertEqual(stats['errors'], 0)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_insert_ingredients_batch_with_duplicates(self, mock_create_client):
        """Test batch insertion with some duplicates."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock some existing ingredients
        existing_ingredient = {'id': 1, 'name': 'flour', 'ro_name': 'făină'}
        mock_existing_result = Mock()
        mock_existing_result.data = [existing_ingredient]
        mock_existing_result.error = None
        
        # Mock no existing for others
        mock_no_existing_result = Mock()
        mock_no_existing_result.data = []
        mock_no_existing_result.error = None
        
        # Alternate between existing and not existing
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_existing_result,  # flour exists
            mock_no_existing_result,  # sugar doesn't exist
            mock_no_existing_result   # salt doesn't exist
        ]
        
        # Mock successful insertions for new ingredients
        self.mock_supabase.table.return_value.insert.return_value.execute.return_value = self.mock_insert_result
        
        inserter = IngredientsInserter()
        
        test_ingredients = [
            {'name': 'flour', 'ro_name': 'făină', 'nova_score': 2, 'created_by': 'ai_parser'},
            {'name': 'sugar', 'ro_name': 'zahăr', 'nova_score': 2, 'created_by': 'ai_parser'},
            {'name': 'salt', 'ro_name': 'sare', 'nova_score': 2, 'created_by': 'ai_parser'}
        ]
        
        result = inserter.insert_ingredients_batch(test_ingredients)
        
        self.assertEqual(result['total_processed'], 3)
        self.assertEqual(result['successful_insertions'], 2)  # sugar and salt
        self.assertEqual(result['skipped_duplicates'], 1)     # flour
        self.assertEqual(result['errors'], 0)

    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_get_ingredient_by_name_english(self, mock_create_client):
        """Test getting ingredient by English name."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock found ingredient
        found_ingredient = {'id': 1, 'name': 'flour', 'ro_name': 'făină', 'nova_score': 2}
        mock_found_result = Mock()
        mock_found_result.data = [found_ingredient]
        mock_found_result.error = None
        
        # Mock not found for Romanian search
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_found_result,    # English search finds it
            mock_not_found_result # Romanian search not needed
        ]
        
        inserter = IngredientsInserter()
        
        result = inserter.get_ingredient_by_name('flour')
        
        self.assertEqual(result, found_ingredient)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_get_ingredient_by_name_romanian(self, mock_create_client):
        """Test getting ingredient by Romanian name."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock not found for English search
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        # Mock found for Romanian search
        found_ingredient = {'id': 1, 'name': 'flour', 'ro_name': 'făină', 'nova_score': 2}
        mock_found_result = Mock()
        mock_found_result.data = [found_ingredient]
        mock_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_not_found_result, # English search doesn't find it
            mock_found_result      # Romanian search finds it
        ]
        
        inserter = IngredientsInserter()
        
        result = inserter.get_ingredient_by_name('făină')
        
        self.assertEqual(result, found_ingredient)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_get_ingredient_by_name_not_found(self, mock_create_client):
        """Test getting ingredient by name when not found."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock not found for both searches
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_not_found_result
        
        inserter = IngredientsInserter()
        
        result = inserter.get_ingredient_by_name('nonexistent')
        
        self.assertIsNone(result)
    
    def test_validate_ingredient_data_valid(self):
        """Test ingredient data validation with valid data."""
        with patch('ingredients.ingredients_inserter.create_client') as mock_create_client:
            mock_create_client.return_value = self.mock_supabase
            
            inserter = IngredientsInserter()
            
            is_valid, message = inserter.validate_ingredient_data(
                name="flour",
                ro_name="făină",
                nova_score=2
            )
            
            self.assertTrue(is_valid)
            self.assertEqual(message, "")
    
    def test_validate_ingredient_data_invalid(self):
        """Test ingredient data validation with invalid data."""
        with patch('ingredients.ingredients_inserter.create_client') as mock_create_client:
            mock_create_client.return_value = self.mock_supabase
            
            inserter = IngredientsInserter()
            
            # Test empty name
            is_valid, message = inserter.validate_ingredient_data("", "făină", 2)
            self.assertFalse(is_valid)
            self.assertIn("English name is required", message)
            
            # Test empty Romanian name
            is_valid, message = inserter.validate_ingredient_data("flour", "", 2)
            self.assertFalse(is_valid)
            self.assertIn("Romanian name is required", message)
            
            # Test invalid NOVA score
            is_valid, message = inserter.validate_ingredient_data("flour", "făină", 5)
            self.assertFalse(is_valid)
            self.assertIn("NOVA score must be an integer between 1 and 4", message)
            
            # Test short name
            is_valid, message = inserter.validate_ingredient_data("a", "făină", 2)
            self.assertFalse(is_valid)
            self.assertIn("English name must be at least 2 characters long", message)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_reset_stats(self, mock_create_client):
        """Test statistics reset."""
        mock_create_client.return_value = self.mock_supabase
        
        inserter = IngredientsInserter()
        
        # Modify some stats
        inserter.stats['ingredients_processed'] = 5
        inserter.stats['ingredients_inserted'] = 3
        inserter.stats['errors'] = 2
        
        # Reset stats
        inserter.reset_stats()
        
        # Check stats were reset
        stats = inserter.get_stats()
        self.assertEqual(stats['ingredients_processed'], 0)
        self.assertEqual(stats['ingredients_inserted'], 0)
        self.assertEqual(stats['errors'], 0)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_check_existing_ingredient_by_english_name(self, mock_create_client):
        """Test checking existing ingredient by English name."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock found ingredient
        found_ingredient = {'id': 1, 'name': 'flour', 'ro_name': 'făină', 'nova_score': 2}
        mock_found_result = Mock()
        mock_found_result.data = [found_ingredient]
        mock_found_result.error = None
        
        # Mock not found for Romanian search
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_found_result,    # English search finds it
            mock_not_found_result # Romanian search not needed
        ]
        
        inserter = IngredientsInserter()
        
        result = inserter._check_existing_ingredient('flour', 'făină')
        
        self.assertEqual(result, found_ingredient)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_check_existing_ingredient_by_romanian_name(self, mock_create_client):
        """Test checking existing ingredient by Romanian name."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock not found for English search
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        # Mock found for Romanian search
        found_ingredient = {'id': 1, 'name': 'flour', 'ro_name': 'făină', 'nova_score': 2}
        mock_found_result = Mock()
        mock_found_result.data = [found_ingredient]
        mock_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_not_found_result, # English search doesn't find it
            mock_found_result      # Romanian search finds it
        ]
        
        inserter = IngredientsInserter()
        
        result = inserter._check_existing_ingredient('flour', 'făină')
        
        self.assertEqual(result, found_ingredient)
    
    @patch('ingredients.ingredients_inserter.create_client')
    def test_check_existing_ingredient_not_found(self, mock_create_client):
        """Test checking existing ingredient when not found."""
        mock_create_client.return_value = self.mock_supabase
        
        # Mock not found for both searches
        mock_not_found_result = Mock()
        mock_not_found_result.data = []
        mock_not_found_result.error = None
        
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_not_found_result
        
        inserter = IngredientsInserter()
        
        result = inserter._check_existing_ingredient('nonexistent', 'inexistent')
        
        self.assertIsNone(result)


if __name__ == '__main__':
    # Set up environment variables for testing
    os.environ['SUPABASE_URL'] = 'https://test.supabase.co'
    os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'test_key'
    
    unittest.main()
