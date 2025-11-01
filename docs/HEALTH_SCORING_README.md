# Health Scoring System

This health scoring system is based on the methodology from the Purio Flutter app and provides a comprehensive way to evaluate the healthiness of food products.

## Overview

The health scoring system analyzes products based on:
- **Nutritional values** (fiber, protein, saturated fat, sugar, sodium, etc.)
- **Ingredient quality** (harmful additives vs. healthy ingredients)
- **Overall composition**

## Scoring Ranges

- **76-100**: Healthy choice (Green) 🟢
- **51-75**: Caution (Yellow) 🟡
- **26-50**: Think twice (Orange) 🟠
- **0-25**: High risk (Red) 🔴

## Files Created

### Core Files
- `processors/helpers/health_scorer.py` - Main health scoring logic
- `processors/helpers/health_score_filler.py` - CSV processing integration
- `update_existing_health_scores.py` - Update existing Supabase products
- `test_health_scoring.py` - Test script with sample data

### Updated Files
- `process_category.py` - Added health scoring to the pipeline
- `processors/supabase/products/create.py` - Added health_score field support

## Usage

### 1. Test the Health Scoring System

```bash
python test_health_scoring.py
```

This will run sample products through the scoring system to demonstrate how it works.

### 2. Process a New Category (with health scoring)

```bash
python process_category.py "https://www.auchan.ro/bauturi-si-tutun/apa/apa-plata/c" --category-id "your_category_id"
```

The health scoring is now automatically included in the processing pipeline.

### 3. Add Health Scores to Existing CSV Files

```bash
python processors/helpers/health_score_filler.py path/to/your/file.csv
```

This will add health scores to an existing CSV file.

### 4. Update Existing Products in Supabase

```bash
python update_existing_health_scores.py
```

This will calculate and update health scores for all existing products in your Supabase database.

## Scoring Methodology

### Nutritional Scoring

The system evaluates nutritional values with different weights:

**Positive Factors:**
- Fiber: +2 points per 10g
- Protein: +1 point per 10g

**Negative Factors:**
- Saturated Fat: -2 points per 10g
- Sugar: -2 points per 10g
- Salt/Sodium: -3 points per 10g

### Ingredient Analysis

**Harmful Ingredients (-3 points each):**
- Artificial sweeteners (aspartame, saccharin, sucralose)
- High fructose corn syrup
- Hydrogenated oils
- Trans fats
- MSG
- Artificial colors (Red 40, Yellow 5, etc.)
- Preservatives (BHA, BHT, etc.)

**Healthy Ingredients (+1 point each):**
- Whole grain
- Organic
- Natural ingredients
- Real fruit/vegetables
- Antioxidants
- Omega-3
- Probiotics/prebiotics

### Base Score

All products start with a base score of 50 points, which represents a neutral starting point.

## Database Schema

The health scoring adds the following fields to your products:

```sql
health_score INTEGER,      -- Score from 0-100
score_category TEXT,       -- "Healthy choice", "Caution", "Think twice", "High risk"
score_color TEXT          -- "green", "yellow", "orange", "red"
```

## Customization

You can customize the scoring system by modifying the `scoring_config` in `health_scorer.py`:

```python
self.scoring_config = {
    'nutrients': {
        'saturated_fat': {'weight': -2, 'max_score': 20, 'unit': 'g'},
        # Add or modify nutrient weights
    },
    'ingredients': {
        'harmful_additives': {
            'weight': -3,
            'keywords': [
                # Add or modify harmful ingredient keywords
            ]
        },
        'healthy_ingredients': {
            'weight': 1,
            'keywords': [
                # Add or modify healthy ingredient keywords
            ]
        }
    },
    'base_score': 50  # Modify starting score
}
```

## Integration with Flutter App

The health scores are compatible with the Purio Flutter app structure:

```dart
class ProductRow {
  int? get healthScore => getField<int>('health_score');
  // ... other fields
}
```

## Example Output

When processing a CSV file, you'll see output like:

```
=== Filling Health Scores ===
Processing: auchan/beverages/water/water_processed.csv
Loaded 45 products
Calculating health scores...
Processing product 1/45...
Processing product 45/45...

Health Score Summary:
Total products: 45
Average score: 67.3
Score distribution:
  Healthy choice (76-100): 12
  Caution (51-75): 18
  Think twice (26-50): 10
  High risk (0-25): 5
```

## Troubleshooting

### Common Issues

1. **Missing nutritional data**: Products without nutritional information will receive the base score
2. **Invalid ingredient format**: The system handles various ingredient list formats
3. **Supabase connection**: Ensure your `.env` file has the correct Supabase credentials

### Debug Mode

To see detailed scoring calculations, you can modify the `health_scorer.py` file to add debug prints:

```python
def calculate_health_score(self, product_data):
    # Add debug prints
    print(f"Processing product: {product_data.get('name', 'Unknown')}")
    print(f"Nutritional data: {product_data.get('nutritional', {})}")
    print(f"Ingredients: {product_data.get('ingredients', '')}")
    # ... rest of the method
```

## Contributing

To improve the health scoring system:

1. Add new nutritional factors
2. Update ingredient keywords
3. Adjust scoring weights
4. Add new health indicators

The system is designed to be easily extensible and maintainable. 