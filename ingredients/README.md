# Ingredients Checking Script

This script checks products from Supabase against the ingredients CSV file using fuzzy search and Romanian translations.

## Features

- **Fetches products** from Supabase that have ingredients in specifications
- **Loads ingredients** from CSV file with Romanian translations
- **Uses fuzzy search** to match ingredients from products with the CSV
- **Direct Romanian mappings** for common ingredients
- **Prints detailed results** showing matches and NOVA scores
- **Provides statistics** on matching success rates

## Usage

### Basic Usage

```bash
cd ingredients
python check_ingredients.py
```

### With Options

```bash
# Limit to first 10 products
python check_ingredients.py --limit 10

# Use a different CSV file
python check_ingredients.py --csv-path my_ingredients.csv

# Combine options
python check_ingredients.py --limit 5 --csv-path ingredients_clean.csv
```

## Output

The script provides:

1. **Product-by-product analysis** showing:
   - Product name
   - Original ingredients text
   - Extracted ingredients
   - Matched ingredients with NOVA scores
   - Unmatched ingredients

2. **Statistics** including:
   - Total products processed
   - Match rate percentage
   - NOVA score distribution

## Example Output

```
================================================================================
INGREDIENTS CHECKING RESULTS
================================================================================

1. PRODUCT: Foi simple pentru prajituri Dr.Oetker 440 g
------------------------------------------------------------
Ingredients text: Faina alba din grau, zahar, ulei de floarea soarelui...

MATCHES FOUND:
  ✓ 'faina alba din grau' → 'wheat flour' (făină de grâu)
    NOVA Score: 2 | Similarity: 100%
  ✓ 'ulei de floarea soarelui' → 'sunflower oil' (ulei de floarea soarelui)
    NOVA Score: 2 | Similarity: 100%

  Average NOVA Score: 2.0
  NOVA Score Distribution: {2: 2}

UNMATCHED INGREDIENTS:
  ✗ zahar
  ✗ difosfat disodic)

================================================================================
STATISTICS
================================================================================
Products processed: 2
Products with ingredients: 2
Total ingredients found: 19
Ingredients matched: 15
Ingredients not matched: 4
Match rate: 78.9%

NOVA Score Distribution:
  NOVA 1: 9 ingredients
  NOVA 2: 2 ingredients
  NOVA 3: 0 ingredients
  NOVA 4: 4 ingredients
```

## Requirements

- Python 3.8+
- Required packages (install with `pip install -r requirements.txt`):
  - `fuzzywuzzy`
  - `python-Levenshtein`
  - `supabase`
  - `python-dotenv`

## Environment Variables

Make sure you have these environment variables set in your `.env` file:

```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

## CSV File Format

The ingredients CSV file should have the following format:

```csv
ingredient_name,ingredient_name_ro,nova_score
apple,măr,1
wheat flour,făină de grâu,2
aspartame,aspartam,4
```

## Matching Logic

1. **Direct Romanian Mapping**: First tries to match using predefined Romanian-to-English mappings
2. **Fuzzy Search**: Uses fuzzy string matching with a threshold of 85% similarity
3. **Ingredient Extraction**: Parses ingredient text using regex patterns for Romanian and English

## Troubleshooting

- **No matches found**: Check if the ingredients CSV file exists and has the correct format
- **Low match rate**: Consider adding more Romanian mappings or adjusting the similarity threshold
- **Connection errors**: Verify your Supabase credentials are correct
