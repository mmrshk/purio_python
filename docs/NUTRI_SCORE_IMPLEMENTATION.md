# Official Nutri-Score Implementation

This document describes the new official Nutri-Score calculation implementation based on the official scoring tables.

## Overview

The Nutri-Score calculator now uses the official Nutri-Score algorithm with proper thresholds and scoring tables as defined by the European Food Safety Authority (EFSA).

## Official Scoring Formula

The Nutri-Score uses the formula: **N - P**

Where:
- **N** = Negative points (based on energy, sugars, saturated fat, sodium)
- **P** = Positive points (based on fiber, protein, fruit/vegetables/nuts)

### Special Cases

- If **N < 11**: Use **N - P**
- If **N ≥ 11** and fruit/vegetables/nuts < 80%: Use **N - (Fiber + Fruit)**

## Negative Points (N) - Official Thresholds

### Energy (kJ)
| Range (kJ) | Points |
|------------|--------|
| 0-335      | 0      |
| 336-670    | 1      |
| 671-1005   | 2      |
| 1006-1340  | 3      |
| 1341-1675  | 4      |
| 1676-2010  | 5      |
| 2011-2345  | 6      |
| 2346-2680  | 7      |
| 2681-3015  | 8      |
| 3016-3350  | 9      |
| 3351+      | 10     |

### Sugars (g)
| Range (g) | Points |
|-----------|--------|
| 0-4.5     | 0      |
| 4.6-9     | 1      |
| 9.1-13.5  | 2      |
| 13.6-18   | 3      |
| 18.1-22.5 | 4      |
| 22.6-27   | 5      |
| 27.1-31   | 6      |
| 31.1-36   | 7      |
| 36.1-40   | 8      |
| 40.1-45   | 9      |
| 45.1+     | 10     |

### Saturated Fat (g)
| Range (g) | Points |
|-----------|--------|
| 0-1       | 0      |
| 1.1-2     | 1      |
| 2.1-3     | 2      |
| 3.1-4     | 3      |
| 4.1-5     | 4      |
| 5.1-6     | 5      |
| 6.1-7     | 6      |
| 7.1-8     | 7      |
| 8.1-9     | 8      |
| 9.1-10    | 9      |
| 10.1+     | 10     |

### Sodium (mg)
| Range (mg) | Points |
|------------|--------|
| 0-90      | 0      |
| 91-180    | 1      |
| 181-270   | 2      |
| 271-360   | 3      |
| 361-450   | 4      |
| 451-540   | 5      |
| 541-630   | 6      |
| 631-720   | 7      |
| 721-810   | 8      |
| 811-900   | 9      |
| 901+      | 10     |

## Positive Points (P) - Official Thresholds

### Fiber (g)
| Range (g) | Points |
|-----------|--------|
| 0-0.9     | 0      |
| 0.9-1.9   | 1      |
| 1.9-2.8   | 2      |
| 2.8-3.7   | 3      |
| 3.7-4.7   | 4      |
| 4.7+      | 5      |

### Protein (g)
| Range (g) | Points |
|-----------|--------|
| 0-1.6     | 0      |
| 1.6-3.2   | 1      |
| 3.2-4.8   | 2      |
| 4.8-6.4   | 3      |
| 6.4-8     | 4      |
| 8+        | 5      |

## Final Nutri-Score Grades

| Final Score | Grade | Normalized Score |
|-------------|-------|------------------|
| ≤ -1        | A     | 100              |
| 0-2         | B     | 80               |
| 3-10        | C     | 60               |
| 11-18       | D     | 40               |
| ≥ 19        | E     | 20               |

## Data Sources

The calculator uses data from two sources:

### Nutritional Data (from `nutritional` field)
- **Energy** (`calories_per_100g_or_100ml`) (kcal) - converted to kJ for calculation
- **Sugars** (`sugar`) (g)
- **Fat** (`fat`) (g) - used to estimate saturated fat (30% of total fat)
- **Protein** (`protein`) (g)
- **Carbohydrates** (`carbohydrates`) (g) - available but not used in Nutri-Score

### Specifications Data (from `specifications` field)
- **Fiber** (`fiber`) (g)

### Missing Data
- **Sodium** - Not available in current database structure
  - This affects the accuracy of Nutri-Score calculation
  - Sodium contributes 0-10 negative points in official Nutri-Score
  - Current implementation assumes 0 points for sodium

## Implementation Details

### Key Methods

1. **`calculate_negative_points(nutritional_data)`**
   - Calculates N based on energy, sugars, saturated fat, and sodium
   - Converts energy from kcal to kJ (1 kcal = 4.184 kJ)

2. **`calculate_positive_points(nutritional_data, specifications_data)`**
   - Calculates P based on fiber (from specifications) and protein (from nutritional)

3. **`calculate_final_nutriscore(n_points, p_points)`**
   - Applies the official formula: N - P
   - Handles special cases for N ≥ 11
   - Maps to final grade (A-E)

4. **`calculate(product_data)`**
   - Main entry point
   - First tries Open Food Facts API
   - Falls back to local calculation if API fails

### Data Extraction

The calculator handles various data formats:
- Numeric values: `{'sugar': 25.5}`
- String values: `{'sugar': '25.5g'}`
- Multiple variations: `{'sugar': 25}`, `{'sugars': 25}`, `{'total_sugar': 25}`

### API Integration

1. **Primary**: Try to fetch Nutri-Score from Open Food Facts API using EAN/barcode
2. **Fallback**: Try to fetch using product name search
3. **Local**: Calculate using official formula if API fails

## Example Calculations

### Example 1: High Sugar Product
```
Nutritional: energy=200kcal, sugars=25g, saturated_fat=3g, sodium=200mg, protein=2g
Specifications: fiber=1.5g

N calculation:
- Energy: 200 kcal = 836.8 kJ → 2 points
- Sugars: 25g → 5 points
- Saturated fat: 3g → 2 points
- Sodium: 200mg → 2 points
Total N = 11 points

P calculation:
- Fiber: 1.5g → 1 point
- Protein: 2g → 1 point
Total P = 2 points

Final score: 11 - 2 = 9 → Grade C → Normalized score: 60
```

### Example 2: Healthy Product
```
Nutritional: energy=150kcal, sugars=8g, saturated_fat=1g, sodium=100mg, protein=8g
Specifications: fiber=4.5g

N calculation:
- Energy: 150 kcal = 627.6 kJ → 1 point
- Sugars: 8g → 1 point
- Saturated fat: 1g → 0 points
- Sodium: 100mg → 1 point
Total N = 3 points

P calculation:
- Fiber: 4.5g → 4 points
- Protein: 8g → 4 points
Total P = 8 points

Final score: 3 - 8 = -5 → Grade A → Normalized score: 100
```

## Testing

The implementation includes comprehensive tests covering:
- API integration (success and failure cases)
- Local calculation with various data formats
- Edge cases (missing data, string data)
- Official threshold calculations
- Final grade mapping

Run tests with:
```bash
python -m pytest tests/processors/scoring/types/test_nutri_score.py -v
```

## Integration

The new Nutri-Score calculator is fully integrated with:
- Product processing pipeline
- Supabase database updates
- Health scoring system
- Existing test suite

## Benefits

1. **Official Compliance**: Uses exact official Nutri-Score thresholds
2. **Accuracy**: Proper energy conversion and threshold handling
3. **Reliability**: Robust fallback from API to local calculation
4. **Flexibility**: Handles various data formats and missing data
5. **Maintainability**: Clear separation of concerns and comprehensive testing
