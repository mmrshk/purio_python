# Score Recalculation Script

A comprehensive script to recalculate all scoring values for products in the database.

## Features

- **Complete Recalculation**: Recalculates all scores (ingredients, additives, health scores, display scores)
- **Flexible Processing**: Single product, batch, or all products
- **Dry Run Mode**: Test without making database changes
- **Error Handling**: Robust error handling with detailed logging
- **Progress Tracking**: Real-time progress updates and statistics

## What Gets Recalculated

### 1. **Ingredients Parsing**
- Extracts ingredients from product specifications
- Matches ingredients against database
- Calculates NOVA scores for each ingredient
- Updates `parsed_ingredients` in specifications

### 2. **Additives Processing**
- Fetches additives from Open Food Facts API using barcode
- Updates `additives_tags` field
- Creates additives relations in database

### 3. **Health Scoring**
- **NutriScore**: Based on nutritional information
- **AdditivesScore**: Based on additives risk levels
- **NovaScore**: Based on ingredient processing level
- **Final Score**: Weighted combination (40% Nutri + 30% Additives + 30% Nova)
- **Display Score**: Final score capped at 49 if high-risk additives present

## Usage

### Single Product
```bash
# Recalculate a specific product
python recalculate_scores.py --product-id "29aeccc9-ad9e-4b77-9b52-bffb241d92b8"

# Dry run (no database changes)
python recalculate_scores.py --product-id "29aeccc9-ad9e-4b77-9b52-bffb241d92b8" --dry-run
```

### Batch Processing
```bash
# Process 10 products
python recalculate_scores.py --batch --batch-size 10

# Process 50 products with dry run
python recalculate_scores.py --batch --batch-size 50 --dry-run
```

### All Products
```bash
# Recalculate all products
python recalculate_scores.py --all

# Dry run for all products
python recalculate_scores.py --all --dry-run
```

## Output Example

```
🔄 RECALCULATING SCORES FOR PRODUCT: 29aeccc9-ad9e-4b77-9b52-bffb241d92b8
================================================================================
🔍 Fetching product with ID: 29aeccc9-ad9e-4b77-9b52-bffb241d92b8
✅ Found product: Esenta de cafea Dr.Oetker 38 ml
   📋 ID: 29aeccc9-ad9e-4b77-9b52-bffb241d92b8
   🏷️  Barcode: 59471998

📝 Step 1: Parsing ingredients...
🧪 Parsing ingredients...
   📋 Ingredients text: apă, propilenglicol, colorant (E 150a), etanol, arome...
   ✅ Extracted 6 ingredients
   🎯 Matched 1 ingredients
   📊 NOVA scores distribution:
      NOVA 1 (Unprocessed): 1

🧪 Step 2: Fetching additives...
🔬 Fetching additives from Open Food Facts...
   🏷️  Using barcode: 59471998
   ✅ Found 1 additives: ['e1510']

📊 Step 3: Calculating health scores...
📊 Calculating health scores...
   🍎 Calculating NutriScore...
      NutriScore: 80 (source: local)
   ⚠️  Calculating AdditivesScore...
      AdditivesScore: 100
   🥗 Calculating NovaScore...
      NovaScore: 100 (source: local)
   🏆 Calculating final health score...
      Final Score: 92
      Formula: (80 × 0.4) + (100 × 0.3) + (100 × 0.3) = 92

💾 Step 4: Updating database...
💾 Updating database with scores...
   ✅ Updated database with scores

✅ SUCCESS: All scores recalculated for product 29aeccc9-ad9e-4b77-9b52-bffb241d92b8
```

## Database Updates

The script updates the following fields in the `products` table:

- `parsed_ingredients` (in specifications JSON)
- `additives_tags`
- `nutri_score`
- `additives_score`
- `nova_score`
- `final_score`
- `display_score`
- `nutri_score_set_by`
- `nova_score_set_by`
- `updated_at`

## Error Handling

The script includes comprehensive error handling:

- **Product Not Found**: Skips and reports
- **Ingredients Parsing Errors**: Logs and continues
- **Additives Fetching Errors**: Logs and continues
- **Scoring Calculation Errors**: Logs and continues
- **Database Update Errors**: Logs and reports

## Statistics

At the end of processing, you'll see a summary:

```
================================================================================
📊 RECALCULATION SUMMARY
================================================================================
✅ Successful: 45
❌ Failed: 3
📊 Total processed: 48

❌ Errors encountered:
  - Product abc123: Database connection error
  - Product def456: No barcode found
  - Product ghi789: Invalid nutritional data
```

## When to Use

- **After Database Schema Changes**: When scoring logic is updated
- **Data Quality Issues**: When scores seem incorrect
- **New Scoring Features**: When new scoring components are added
- **Bulk Updates**: When you need to update many products at once
- **Testing**: Use `--dry-run` to test without making changes

## Performance Considerations

- **Single Product**: Fastest, use for testing or individual fixes
- **Batch Processing**: Good balance of speed and control
- **All Products**: Use for complete recalculation, may take time for large databases

## Dependencies

- `process_single_product.py`: Core processing logic
- `ingredients/supabase_ingredients_checker.py`: Ingredients parsing
- `processors/scoring/`: All scoring calculators
- `processors/helpers/additives/`: Additives processing

## Safety Features

- **Dry Run Mode**: Test without making changes
- **Error Recovery**: Continues processing even if individual products fail
- **Detailed Logging**: Full visibility into what's happening
- **Progress Tracking**: Know exactly where you are in the process
