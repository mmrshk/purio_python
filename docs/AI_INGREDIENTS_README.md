# AI Ingredients Parser

This module provides AI-powered ingredient parsing as a fallback when no ingredients are found in product specifications.

## Features

- **AI-Powered Parsing**: Uses OpenAI GPT-3.5-turbo to infer ingredients from product names
- **Fallback Logic**: Automatically activates when no ingredients text is available
- **Cost-Effective**: Uses GPT-3.5-turbo for optimal cost/performance balance
- **Romanian Support**: Works with Romanian product names and descriptions
- **Compatible**: Integrates seamlessly with existing ingredient checking system

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up OpenAI API Key

1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Add it to your environment:

```bash
# Option 1: Environment variable
export OPENAI_API_KEY=your_api_key_here

# Option 2: .env file
echo "OPENAI_API_KEY=your_api_key_here" >> .env
```

### 3. Copy Configuration Template

```bash
cp config.env.example .env
# Edit .env with your actual API keys
```

## Usage

### Basic AI Parser

```python
from ingredients.ai_ingredients_parser import AIIngredientsParser

# Initialize parser
parser = AIIngredientsParser()

# Parse ingredients from product name
result = parser.parse_ingredients_from_name("Pâine albă Auchan")

print(result['extracted_ingredients'])
# Output: ['făină', 'apă', 'drojdie', 'sare']
```

### Enhanced Checker with AI Fallback

```python
from ingredients.enhanced_ingredients_checker import EnhancedIngredientsChecker

# Initialize with AI fallback
checker = EnhancedIngredientsChecker(use_ai_fallback=True)

# Check product ingredients (uses AI if no ingredients found)
product = {
    'name': 'Lapte UHT 3.5% grăsime',
    'specifications': {'ingredients': ''}  # No ingredients
}

result = checker.check_product_ingredients(product)
print(f"Source: {result['source']}")  # 'ai_parser'
print(f"Ingredients: {result['extracted_ingredients']}")
```

### Integration with Existing System

Replace your existing ingredients checker:

```python
# Old way
from ingredients.supabase_ingredients_checker import SupabaseIngredientsChecker
checker = SupabaseIngredientsChecker()

# New way (with AI fallback)
from ingredients.enhanced_ingredients_checker import EnhancedIngredientsChecker
checker = EnhancedIngredientsChecker(use_ai_fallback=True)
```

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `AI_MODEL`: AI model to use (default: "gpt-3.5-turbo")
- `USE_AI_FALLBACK`: Enable AI fallback (default: true)
- `AI_MAX_TOKENS`: Maximum tokens for AI response (default: 500)

### Model Options

- `gpt-3.5-turbo`: Recommended (cost-effective, good accuracy)
- `gpt-4`: Higher accuracy, higher cost
- `gpt-4-turbo`: Best accuracy, highest cost

## Cost Estimation

### GPT-3.5-turbo (Recommended)
- **Cost**: ~$0.001 per 1K tokens
- **Per Product**: ~$0.01-0.05
- **1000 Products**: ~$10-50

### GPT-4
- **Cost**: ~$0.03 per 1K tokens  
- **Per Product**: ~$0.05-0.20
- **1000 Products**: ~$50-200

## Testing

Run the test script to verify everything works:

```bash
python test_ai_ingredients.py
```

This will test:
- AI parser with sample Romanian products
- Enhanced checker with mixed scenarios
- Statistics and error handling

## Examples

### Romanian Products

```python
# Bread
result = parser.parse_ingredients_from_name("Pâine albă Auchan")
# Output: ['făină', 'apă', 'drojdie', 'sare']

# Milk
result = parser.parse_ingredients_from_name("Lapte UHT 3.5% grăsime")
# Output: ['lapte', 'vitamina d3']

# Cheese
result = parser.parse_ingredients_from_name("Branză de vaci 200g")
# Output: ['lapte', 'sare', 'culturi lactice']
```

### Mixed Language Support

```python
# English products work too
result = parser.parse_ingredients_from_name("Coca-Cola 2L")
# Output: ['apă', 'zahăr', 'colorant', 'acidifiant', 'arome']
```

## Statistics

The system tracks comprehensive statistics:

```python
stats = checker.get_stats()
print(stats)
# Output:
# {
#     'products_processed': 100,
#     'products_with_ingredients': 60,
#     'products_with_ai_ingredients': 40,
#     'total_ingredients_found': 500,
#     'ingredients_matched': 450,
#     'ingredients_not_matched': 50,
#     'nova_scores': {1: 200, 2: 150, 3: 80, 4: 20},
#     'ai_stats': {
#         'ai_requests_made': 40,
#         'ai_requests_successful': 38,
#         'ai_requests_failed': 2,
#         'ingredients_extracted': 200
#     }
# }
```

## Error Handling

The system gracefully handles errors:

- **API Key Missing**: Clear error message with setup instructions
- **API Rate Limits**: Automatic retry with exponential backoff
- **Invalid Responses**: Fallback parsing using regex
- **Network Issues**: Continues without AI fallback

## Performance Tips

1. **Batch Processing**: Process multiple products in sequence
2. **Caching**: Consider caching AI responses for repeated products
3. **Rate Limiting**: Add delays between requests if needed
4. **Monitoring**: Track API usage and costs

## Troubleshooting

### Common Issues

1. **"OPENAI_API_KEY not set"**
   - Set your API key in environment variables or .env file

2. **"AI request failed"**
   - Check your internet connection
   - Verify API key is valid
   - Check OpenAI service status

3. **"No ingredients extracted"**
   - Some product names may be too generic
   - Try adding product description for better context

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- [ ] Support for product images
- [ ] Local model integration (Ollama)
- [ ] Caching system for repeated products
- [ ] Batch processing optimization
- [ ] Custom model fine-tuning

