#!/usr/bin/env python3
"""
AI-based ingredients parser for extracting ingredients from product names.

This class:
1. Uses OpenAI GPT-3.5-turbo to infer ingredients from product names
2. Acts as a fallback when no ingredients text is available
3. Returns structured results compatible with existing ingredient checking system
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

try:
    from .ingredients_inserter import IngredientsInserter
except ImportError:
    from ingredients_inserter import IngredientsInserter

load_dotenv()

class AIIngredientsParser:
    def __init__(self, model: str = "gpt-3.5-turbo", max_tokens: int = 500, 
                 auto_insert_ingredients: bool = False):
        """
        Initialize the AI ingredients parser.
        
        Args:
            model: OpenAI model to use (default: gpt-3.5-turbo)
            max_tokens: Maximum tokens for AI response
            auto_insert_ingredients: Whether to automatically insert new ingredients to Supabase
        """
        self.model = model
        self.max_tokens = max_tokens
        self.auto_insert_ingredients = auto_insert_ingredients
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
        self.client = OpenAI(api_key=api_key)
        
        # Initialize ingredients inserter if auto-insert is enabled
        self.ingredients_inserter = None
        if auto_insert_ingredients:
            try:
                self.ingredients_inserter = IngredientsInserter()
                print("🔗 Ingredients inserter initialized - new ingredients will be added to database")
            except Exception as e:
                print(f"⚠️  Failed to initialize ingredients inserter: {str(e)}")
                print("   Continuing without auto-insertion...")
                self.auto_insert_ingredients = False
        
        # Statistics
        self.stats = {
            'ai_requests_made': 0,
            'ai_requests_successful': 0,
            'ai_requests_failed': 0,
            'ingredients_extracted': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }
    
    def parse_ingredients_from_name(self, product_name: str, product_description: str = None) -> Dict[str, Any]:
        """
        Parse ingredients from product name using AI.
        
        Args:
            product_name: Name of the product
            product_description: Optional product description for additional context
            
        Returns:
            Dictionary with parsing results
        """
        try:
            print(f"🤖 Using AI to parse ingredients from: {product_name}")
            
            # Prepare context for AI
            context = product_name
            if product_description:
                context += f"\nDescription: {product_description}"
            
            # Create AI prompt
            prompt = self._create_ingredient_prompt(context)
            
            # Make AI request
            response = self._make_ai_request(prompt)
            
            if response:
                # Parse AI response
                ingredients = self._parse_ai_response(response)
                
                self.stats['ai_requests_successful'] += 1
                self.stats['ingredients_extracted'] += len(ingredients)
                
                print(f"   ✅ AI extracted {len(ingredients)} ingredients")
                
                # Auto-insert ingredients to database if enabled
                insertion_results = []
                if self.auto_insert_ingredients and self.ingredients_inserter and ingredients:
                    insertion_results = self._insert_ingredients_to_database(ingredients)
                
                return {
                    'ingredients_text': f"AI-generated from product name: {product_name}",
                    'extracted_ingredients': ingredients,
                    'ai_generated': True,
                    'source': 'ai_parser',
                    'insertion_results': insertion_results
                }
            else:
                self.stats['ai_requests_failed'] += 1
                print("   ❌ AI request failed")
                return {
                    'ingredients_text': None,
                    'extracted_ingredients': [],
                    'ai_generated': False,
                    'source': 'ai_parser_failed'
                }
                
        except Exception as e:
            print(f"   ❌ AI parsing error: {str(e)}")
            self.stats['ai_requests_failed'] += 1
            return {
                'ingredients_text': None,
                'extracted_ingredients': [],
                'ai_generated': False,
                'source': 'ai_parser_error',
                'error': str(e)
            }
    
    def _create_ingredient_prompt(self, context: str) -> str:
        """
        Create a prompt for AI to extract ingredients.
        
        Args:
            context: Product name and description
            
        Returns:
            Formatted prompt for AI
        """
        return f"""You are a food ingredient expert. Based on the product name and description, extract the most likely ingredients.

Product: {context}

Please extract ingredients that are most likely to be in this product. Consider:
1. Common ingredients for this type of product
2. Ingredients typically mentioned in product names
3. Standard ingredients for this food category

Important rules:
- Only include edible ingredients or approved food additives (e.g., E-codes), not processes or environmental factors
- Exclude non-ingredients such as: air, sun, time, heat, light, temperature, drying, curing, aging, process descriptions
- Do not infer brand slogans or preparation methods as ingredients

Return ONLY a JSON array of ingredient names, like this:
["ingredient1", "ingredient2", "ingredient3"]

Do not include explanations, just the JSON array. If you cannot determine ingredients, return an empty array: []"""
    
    def _make_ai_request(self, prompt: str) -> Optional[str]:
        """
        Make request to OpenAI API.
        
        Args:
            prompt: Formatted prompt for AI
            
        Returns:
            AI response or None if failed
        """
        try:
            self.stats['ai_requests_made'] += 1
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a food ingredient expert. Always respond with valid JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3  # Lower temperature for more consistent results
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"   ❌ OpenAI API error: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str) -> List[str]:
        """
        Parse AI response to extract ingredients list.
        
        Args:
            response: Raw AI response
            
        Returns:
            List of extracted ingredients
        """
        try:
            # Clean the response
            response = response.strip()
            
            # Remove any markdown formatting
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Parse JSON
            ingredients = json.loads(response)
            
            if not isinstance(ingredients, list):
                return []
            
            # Clean and validate ingredients
            cleaned_ingredients = []
            for ingredient in ingredients:
                if isinstance(ingredient, str):
                    ingredient = ingredient.strip()
                    if ingredient and len(ingredient) > 1:
                        cleaned_ingredients.append(ingredient)
            
            return cleaned_ingredients
            
        except json.JSONDecodeError:
            print(f"   ⚠️  Failed to parse AI response as JSON: {response[:100]}...")
            # Fallback: try to extract ingredients using regex
            return self._extract_ingredients_fallback(response)
        except Exception as e:
            print(f"   ⚠️  Error parsing AI response: {str(e)}")
            return []
    
    def _extract_ingredients_fallback(self, response: str) -> List[str]:
        """
        Fallback method to extract ingredients from malformed AI response.
        
        Args:
            response: Raw AI response
            
        Returns:
            List of extracted ingredients
        """
        # Look for quoted strings or comma-separated values
        ingredients = []
        
        # Try to find quoted strings
        quoted_matches = re.findall(r'"([^"]+)"', response)
        if quoted_matches:
            ingredients.extend(quoted_matches)
        
        # Try to find comma-separated values
        if not ingredients:
            parts = response.split(',')
            for part in parts:
                part = part.strip().strip('[]"\'')
                if part and len(part) > 1:
                    ingredients.append(part)
        
        return ingredients[:10]  # Limit to 10 ingredients max
    
    def _insert_ingredients_to_database(self, ingredients: List[str]) -> List[Dict[str, Any]]:
        """
        Insert AI-generated ingredients to the database.
        
        Args:
            ingredients: List of ingredient names to insert
            
        Returns:
            List of insertion results
        """
        if not self.ingredients_inserter:
            return []
        
        insertion_results = []
        
        for ingredient in ingredients:
            try:
                # For AI-generated ingredients, we'll use the same name for both English and Romanian
                # In a real scenario, you might want to translate or use a different approach
                result = self.ingredients_inserter.insert_ingredient(
                    name=ingredient,
                    ro_name=ingredient,  # Using same name for both languages
                    nova_score=1,  # Default NOVA score for AI-generated ingredients
                    created_by="ai_parser",
                    visible=False
                )
                
                insertion_results.append({
                    'ingredient': ingredient,
                    'result': result
                })
                
                # Update stats based on result
                if result['success']:
                    if result['action'] == 'inserted':
                        self.stats['ingredients_inserted'] += 1
                        print(f"   💾 Inserted new ingredient: {ingredient}")
                    elif result['action'] == 'skipped':
                        self.stats['ingredients_skipped'] += 1
                        print(f"   ⏭️  Skipped existing ingredient: {ingredient}")
                else:
                    self.stats['ingredients_errors'] += 1
                    print(f"   ❌ Failed to insert ingredient {ingredient}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                self.stats['ingredients_errors'] += 1
                print(f"   ❌ Exception inserting ingredient {ingredient}: {str(e)}")
                insertion_results.append({
                    'ingredient': ingredient,
                    'result': {
                        'success': False,
                        'action': 'error',
                        'reason': 'exception',
                        'error': str(e)
                    }
                })
        
        return insertion_results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get parser statistics.
        
        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset parser statistics."""
        self.stats = {
            'ai_requests_made': 0,
            'ai_requests_successful': 0,
            'ai_requests_failed': 0,
            'ingredients_extracted': 0,
            'ingredients_inserted': 0,
            'ingredients_skipped': 0,
            'ingredients_errors': 0
        }
        
        # Also reset inserter stats if available
        if self.ingredients_inserter:
            self.ingredients_inserter.reset_stats()


def main():
    """Test the AI ingredients parser with auto-insertion."""
    try:
        # Test with auto-insertion enabled
        parser = AIIngredientsParser(auto_insert_ingredients=True)
        
        # Test with sample products
        test_products = [
            "Pâine albă Auchan",
            "Lapte UHT 3.5% grăsime",
            "Branză de vaci 200g",
            "Coca-Cola 2L",
            "Chipsuri cu sare"
        ]
        
        print("🧪 Testing AI Ingredients Parser with Auto-Insertion")
        print("=" * 60)
        
        for product in test_products:
            print(f"\n📦 Product: {product}")
            result = parser.parse_ingredients_from_name(product)
            
            if result['extracted_ingredients']:
                print(f"   ✅ Ingredients: {', '.join(result['extracted_ingredients'])}")
                
                # Show insertion results if available
                if 'insertion_results' in result and result['insertion_results']:
                    print("   📊 Insertion Results:")
                    for insertion in result['insertion_results']:
                        ingredient = insertion['ingredient']
                        res = insertion['result']
                        if res['success']:
                            if res['action'] == 'inserted':
                                print(f"      💾 {ingredient}: Inserted (ID: {res.get('ingredient_id', 'N/A')})")
                            elif res['action'] == 'skipped':
                                print(f"      ⏭️  {ingredient}: Skipped (already exists)")
                        else:
                            print(f"      ❌ {ingredient}: Failed - {res.get('message', 'Unknown error')}")
            else:
                print("   ❌ No ingredients extracted")
        
        print(f"\n📊 Parser Statistics: {parser.get_stats()}")
        
        # Show inserter statistics if available
        if parser.ingredients_inserter:
            print(f"📊 Inserter Statistics: {parser.ingredients_inserter.get_stats()}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure to set OPENAI_API_KEY and Supabase credentials environment variables.")


if __name__ == "__main__":
    main()
