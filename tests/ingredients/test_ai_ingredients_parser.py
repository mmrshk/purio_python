#!/usr/bin/env python3
"""
Test script for AI ingredients parser functionality.

This script tests the AI ingredients parser as a fallback when no ingredients 
are found in product specifications.
"""

import os
import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).resolve().parents[3]))
from ingredients.ai_ingredients_parser import AIIngredientsParser


class TestAIIngredientsParser(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variable
        os.environ['OPENAI_API_KEY'] = 'test_key'
        
        # Mock OpenAI client
        self.mock_openai_client = Mock()
        self.mock_response = Mock()
        self.mock_response.choices = [Mock()]
        self.mock_response.choices[0].message.content = '["făină", "apă", "sare", "drojdie"]'
        self.mock_openai_client.chat.completions.create.return_value = self.mock_response
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variable
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_init_success(self, mock_openai_class):
        """Test successful initialization of AI parser."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        self.assertEqual(parser.model, "gpt-3.5-turbo")
        self.assertEqual(parser.max_tokens, 500)
        self.assertEqual(parser.client, self.mock_openai_client)
        self.assertFalse(parser.auto_insert_ingredients)
        self.assertIsNone(parser.ingredients_inserter)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_init_with_custom_model(self, mock_openai_class):
        """Test initialization with custom model."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser(model="gpt-4", max_tokens=1000)
        
        self.assertEqual(parser.model, "gpt-4")
        self.assertEqual(parser.max_tokens, 1000)

    def test_init_missing_api_key(self):
        """Test initialization failure when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                AIIngredientsParser()
            
            self.assertIn("OPENAI_API_KEY environment variable is not set", str(context.exception))

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_success(self, mock_openai_class):
        """Test successful ingredient parsing."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Pâine albă Auchan")
        
        self.assertEqual(result['extracted_ingredients'], ['făină', 'apă', 'sare', 'drojdie'])
        self.assertTrue(result['ai_generated'])
        self.assertEqual(result['source'], 'ai_parser')
        self.assertIn('AI-generated from product name', result['ingredients_text'])
        
        # Verify OpenAI was called correctly
        self.mock_openai_client.chat.completions.create.assert_called_once()
        call_args = self.mock_openai_client.chat.completions.create.call_args
        self.assertEqual(call_args[1]['model'], 'gpt-3.5-turbo')
        self.assertEqual(call_args[1]['max_tokens'], 500)
        self.assertEqual(call_args[1]['temperature'], 0.3)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_with_description(self, mock_openai_class):
        """Test ingredient parsing with product description."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name(
            "Branză de vaci 200g", 
            "Fresh cow cheese made from milk"
        )
        
        self.assertEqual(result['extracted_ingredients'], ['făină', 'apă', 'sare', 'drojdie'])
        self.assertTrue(result['ai_generated'])
        
        # Verify the prompt includes description
        call_args = self.mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        user_message = messages[1]['content']
        self.assertIn('Branză de vaci 200g', user_message)
        self.assertIn('Fresh cow cheese made from milk', user_message)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_api_failure(self, mock_openai_class):
        """Test ingredient parsing when API call fails."""
        mock_openai_class.return_value = self.mock_openai_client
        self.mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        self.assertEqual(result['extracted_ingredients'], [])
        self.assertFalse(result['ai_generated'])
        self.assertEqual(result['source'], 'ai_parser_failed')

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_invalid_json_response(self, mock_openai_class):
        """Test ingredient parsing with invalid JSON response."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock invalid JSON response
        self.mock_response.choices[0].message.content = 'Invalid JSON response'
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        # Should fallback to regex extraction
        self.assertIsInstance(result['extracted_ingredients'], list)
        self.assertTrue(result['ai_generated'])

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_markdown_response(self, mock_openai_class):
        """Test ingredient parsing with markdown formatted response."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock markdown JSON response
        self.mock_response.choices[0].message.content = '```json\n["făină", "apă", "sare"]\n```'
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        self.assertEqual(result['extracted_ingredients'], ['făină', 'apă', 'sare'])
        self.assertTrue(result['ai_generated'])

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_empty_response(self, mock_openai_class):
        """Test ingredient parsing with empty response."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock empty response
        self.mock_response.choices[0].message.content = '[]'
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        self.assertEqual(result['extracted_ingredients'], [])
        self.assertTrue(result['ai_generated'])

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_non_list_response(self, mock_openai_class):
        """Test ingredient parsing with non-list JSON response."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock non-list response
        self.mock_response.choices[0].message.content = '{"ingredients": ["făină", "apă"]}'
        
        parser = AIIngredientsParser()
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        self.assertEqual(result['extracted_ingredients'], [])
        self.assertTrue(result['ai_generated'])

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_create_ingredient_prompt(self, mock_openai_class):
        """Test prompt creation for ingredient extraction."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        prompt = parser._create_ingredient_prompt("Pâine albă Auchan")
        
        self.assertIn("food ingredient expert", prompt)
        self.assertIn("Pâine albă Auchan", prompt)
        self.assertIn("JSON array", prompt)
        self.assertIn("ingredient names", prompt)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_extract_ingredients_fallback(self, mock_openai_class):
        """Test fallback ingredient extraction from malformed response."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        # Test quoted strings extraction
        ingredients = parser._extract_ingredients_fallback('"făină", "apă", "sare"')
        expected = ['făină', 'apă', 'sare']
        self.assertEqual(ingredients, expected)
        
        # Test comma-separated extraction
        ingredients = parser._extract_ingredients_fallback('făină, apă, sare')
        expected = ['făină', 'apă', 'sare']
        self.assertEqual(ingredients, expected)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_get_stats(self, mock_openai_class):
        """Test statistics retrieval."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        # Process some ingredients to generate stats
        parser.stats['ai_requests_made'] = 5
        parser.stats['ai_requests_successful'] = 4
        parser.stats['ai_requests_failed'] = 1
        parser.stats['ingredients_extracted'] = 20
        
        stats = parser.get_stats()
        
        expected_stats = {
            'ai_requests_made': 5,
            'ai_requests_successful': 4,
            'ai_requests_failed': 1,
            'ingredients_extracted': 20,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }
        self.assertEqual(stats, expected_stats)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_reset_stats(self, mock_openai_class):
        """Test statistics reset."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        # Set some stats
        parser.stats['ai_requests_made'] = 5
        parser.stats['ingredients_extracted'] = 20
        
        # Reset stats
        parser.reset_stats()
        
        expected_stats = {
            'ai_requests_made': 0,
            'ai_requests_successful': 0,
            'ai_requests_failed': 0,
            'ingredients_extracted': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }
        self.assertEqual(parser.stats, expected_stats)
    
    @patch('ingredients.ai_ingredients_parser.IngredientsInserter')
    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_init_with_auto_insertion(self, mock_openai_class, mock_inserter_class):
        """Test initialization with auto-insertion enabled."""
        mock_openai_class.return_value = self.mock_openai_client
        mock_inserter = Mock()
        mock_inserter_class.return_value = mock_inserter
        
        parser = AIIngredientsParser(auto_insert_ingredients=True)
        
        self.assertTrue(parser.auto_insert_ingredients)
        self.assertEqual(parser.ingredients_inserter, mock_inserter)
        mock_inserter_class.assert_called_once()
    
    @patch('ingredients.ai_ingredients_parser.IngredientsInserter')
    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_init_with_auto_insertion_failure(self, mock_openai_class, mock_inserter_class):
        """Test initialization when auto-insertion fails to initialize."""
        mock_openai_class.return_value = self.mock_openai_client
        mock_inserter_class.side_effect = Exception("Supabase connection failed")
        
        parser = AIIngredientsParser(auto_insert_ingredients=True)
        
        self.assertFalse(parser.auto_insert_ingredients)
        self.assertIsNone(parser.ingredients_inserter)
    
    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_with_auto_insertion(self, mock_openai_class):
        """Test ingredient parsing with auto-insertion enabled."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock successful AI response
        self.mock_response.choices[0].message.content = '["flour", "water", "salt"]'
        
        # Mock ingredients inserter
        mock_inserter = Mock()
        mock_inserter.insert_ingredient.side_effect = [
            {'success': True, 'action': 'inserted', 'ingredient_id': 1},
            {'success': True, 'action': 'skipped', 'ingredient_id': 2},
            {'success': False, 'action': 'error', 'message': 'Database error'}
        ]
        
        parser = AIIngredientsParser(auto_insert_ingredients=True)
        parser.ingredients_inserter = mock_inserter
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        # Verify AI parsing worked
        self.assertEqual(result['extracted_ingredients'], ['flour', 'water', 'salt'])
        self.assertTrue(result['ai_generated'])
        
        # Verify insertion results
        self.assertIn('insertion_results', result)
        self.assertEqual(len(result['insertion_results']), 3)
        
        # Verify inserter was called for each ingredient
        self.assertEqual(mock_inserter.insert_ingredient.call_count, 3)
        
        # Check stats
        stats = parser.get_stats()
        self.assertEqual(stats['ingredients_extracted'], 3)
        self.assertEqual(stats['ingredients_inserted'], 1)
        self.assertEqual(stats['ingredients_skipped'], 1)
        self.assertEqual(stats['ingredients_errors'], 1)
    
    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_without_auto_insertion(self, mock_openai_class):
        """Test ingredient parsing without auto-insertion."""
        mock_openai_class.return_value = self.mock_openai_client
        
        # Mock successful AI response
        self.mock_response.choices[0].message.content = '["flour", "water", "salt"]'
        
        parser = AIIngredientsParser(auto_insert_ingredients=False)
        
        result = parser.parse_ingredients_from_name("Test Product")
        
        # Verify AI parsing worked
        self.assertEqual(result['extracted_ingredients'], ['flour', 'water', 'salt'])
        self.assertTrue(result['ai_generated'])
        
        # Verify insertion results is empty (not None)
        self.assertIn('insertion_results', result)
        self.assertEqual(result['insertion_results'], [])
        
        # Check stats
        stats = parser.get_stats()
        self.assertEqual(stats['ingredients_extracted'], 3)
        self.assertEqual(stats['ingredients_inserted'], 0)
        self.assertEqual(stats['ingredients_skipped'], 0)
        self.assertEqual(stats['ingredients_errors'], 0)

    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_parse_ingredients_stats_update(self, mock_openai_class):
        """Test that statistics are updated during parsing."""
        mock_openai_class.return_value = self.mock_openai_client
        
        parser = AIIngredientsParser()
        
        # Initial stats should be zero
        initial_stats = parser.get_stats()
        self.assertEqual(initial_stats['ai_requests_made'], 0)
        self.assertEqual(initial_stats['ai_requests_successful'], 0)
        
        # Parse ingredients
        result = parser.parse_ingredients_from_name("Test Product")
        
        # Stats should be updated
        updated_stats = parser.get_stats()
        self.assertEqual(updated_stats['ai_requests_made'], 1)
        self.assertEqual(updated_stats['ai_requests_successful'], 1)
        self.assertEqual(updated_stats['ingredients_extracted'], 4)  # 4 ingredients from mock


class TestAIIngredientsParserIntegration(unittest.TestCase):
    """Integration tests for AI ingredients parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables for testing
        os.environ['OPENAI_API_KEY'] = 'test_key'
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variable
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
    
    @patch('ingredients.ai_ingredients_parser.OpenAI')
    def test_full_workflow(self, mock_openai_class):
        """Test the complete workflow from initialization to parsing."""
        # Mock successful API response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '["făină", "apă", "sare", "drojdie"]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Test products
        test_products = [
            "Pâine albă Auchan",
            "Lapte UHT 3.5% grăsime",
            "Branză de vaci 200g",
            "Coca-Cola 2L",
            "Chipsuri cu sare"
        ]
        
        parser = AIIngredientsParser()
        
        for product in test_products:
            result = parser.parse_ingredients_from_name(product)
            
            # Verify basic structure
            self.assertIn('extracted_ingredients', result)
            self.assertIn('ai_generated', result)
            self.assertIn('source', result)
            self.assertIn('ingredients_text', result)
            
            # Verify AI generated flag
            self.assertTrue(result['ai_generated'])
            self.assertEqual(result['source'], 'ai_parser')
            
            # Verify ingredients were extracted
            self.assertIsInstance(result['extracted_ingredients'], list)
            self.assertGreater(len(result['extracted_ingredients']), 0)
        
        # Verify stats were updated
        stats = parser.get_stats()
        self.assertEqual(stats['ai_requests_made'], len(test_products))
        self.assertEqual(stats['ai_requests_successful'], len(test_products))


if __name__ == '__main__':
    # Set up environment variables for testing
    os.environ['OPENAI_API_KEY'] = 'test_key'
    
    unittest.main()
