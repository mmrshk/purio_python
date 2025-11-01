# Nova Score Calculation Explanation

## Overview
The Nova score calculation follows the **NOVA classification system**, which categorizes foods into 4 groups based on their level of processing. This system helps assess the healthiness of food products by evaluating how much industrial processing they have undergone.

## Nova Score Mapping
```python
NOVA_MAP = {
    1: 100,  # Unprocessed or minimally processed foods
    2: 80,   # Processed culinary ingredients
    3: 50,   # Processed foods
    4: 20    # Ultra-processed foods
}
```

## Calculation Process

The system calculates Nova scores through a **multi-step approach**:

### 1. API First Approach
- Tries to fetch Nova score from Open Food Facts API using barcode or product name
- If available, uses the pre-calculated Nova score from the database

### 2. Special Cases Handling
- **Water and natural beverages**: Automatically assigned Nova 1 (100 points)
- **Alcoholic beverages**: Automatically assigned Nova 3 (50 points)

### 3. Ingredient Analysis (Fallback)
- Extracts ingredients from product specifications
- Matches each ingredient against a comprehensive database
- Uses fuzzy matching to handle variations in ingredient names
- Classifies each ingredient into Nova groups 1-4

## Ingredient Classification

Individual ingredients are classified into Nova groups based on a comprehensive CSV database:

### Nova 1 (100 points) - Unprocessed or Minimally Processed Foods
- **Fruits**: apple, banana, orange, grape, strawberry, etc.
- **Vegetables**: tomato, cucumber, carrot, onion, garlic, potato, etc.
- **Grains**: rice, wheat, oats, barley, quinoa, etc.
- **Meat and Fish**: chicken, beef, pork, salmon, tuna, etc.
- **Dairy**: milk, eggs, etc.
- **Nuts and Seeds**: almonds, walnuts, cashews, peanuts, etc.

### Nova 2 (80 points) - Processed Culinary Ingredients
- **Oils**: olive oil, vegetable oil, sunflower oil, coconut oil, etc.
- **Sweeteners**: sugar, honey, maple syrup, stevia, etc.
- **Seasonings**: salt, garlic powder, onion powder, spices, etc.
- **Vinegars**: apple cider vinegar, balsamic vinegar, etc.
- **Sauces**: soy sauce, fish sauce, mustard, ketchup, etc.

### Nova 3 (50 points) - Processed Foods
- **Fermented Products**: yogurt culture, kefir grains, bacteria culture
- **Enzymes**: papain, bromelain, ficin, trypsin, etc.
- **Processed Ingredients**: rennet, various enzymes used in food processing

### Nova 4 (20 points) - Ultra-Processed Ingredients
- **Artificial Sweeteners**: aspartame, saccharin, sucralose, acesulfame potassium, etc.
- **Preservatives**: sodium benzoate, potassium sorbate, calcium propionate, etc.
- **Acids and Bases**: citric acid, phosphoric acid, sodium hydroxide, etc.
- **Emulsifiers and Stabilizers**: agar, alginates, gums, cellulose derivatives, etc.
- **Flavor Enhancers**: monosodium glutamate, ribonucleotides, etc.

## Final Nova Score Rules

The system applies these **hierarchical rules** to determine the final Nova group:

### Rule 1: Ultra-Processed Override
- **If any ingredient is Nova 4 → Nova 4 (ultra-processed)**
- Any ultra-processed ingredient makes the entire product ultra-processed

### Rule 2: Processed Foods
- **If any ingredient is Nova 3 → Nova 3 (processed)**
- Processed ingredients result in a processed food classification

### Rule 3: Mixed Natural and Culinary
- **If mix of natural (Nova 1) and culinary (Nova 2) → Nova 3**
- Combining unprocessed foods with culinary ingredients results in processed classification

### Rule 4: Culinary Ingredients Only
- **If only culinary ingredients (Nova 2) → Nova 2**
- Products made only from culinary ingredients are classified as processed culinary ingredients

### Rule 5: Whole Ingredients Only
- **If only whole ingredients (Nova 1) → Nova 1**
- Products containing only unprocessed ingredients maintain their natural classification

## Key Principles

1. **Worst-case scenario**: Any ultra-processed ingredient (Nova 4) makes the entire product Nova 4
2. **Processing level hierarchy**: Higher processing levels override lower ones
3. **Mixed ingredients**: Combining natural and culinary ingredients results in Nova 3
4. **Special handling**: Products like water get Nova 1, alcoholic beverages get Nova 3
5. **Fuzzy matching**: The system uses intelligent matching to handle ingredient name variations

## Example Calculations

### Example 1: Natural Yogurt
- Ingredients: milk, yogurt culture
- Nova distribution: {1: 1, 3: 1} (milk = Nova 1, yogurt culture = Nova 3)
- Result: Nova 3 (50 points) - processed food

### Example 2: Ultra-Processed Snack
- Ingredients: corn, vegetable oil, salt, artificial flavor, preservatives
- Nova distribution: {1: 1, 2: 2, 4: 2} (corn = Nova 1, oil/salt = Nova 2, artificial ingredients = Nova 4)
- Result: Nova 4 (20 points) - ultra-processed food

### Example 3: Simple Fruit Salad
- Ingredients: apple, banana, orange
- Nova distribution: {1: 3} (all fruits = Nova 1)
- Result: Nova 1 (100 points) - unprocessed food

### Example 4: Homemade Bread
- Ingredients: flour, water, salt, yeast
- Nova distribution: {1: 2, 2: 2} (flour/water = Nova 1, salt/yeast = Nova 2)
- Result: Nova 3 (50 points) - processed food

## Implementation Details

The system uses:
- **Fuzzy matching** to identify ingredients from product labels
- **Comprehensive ingredient database** with both English and Romanian translations
- **Intelligent validation** to prevent false matches
- **Hierarchical rule application** to determine final classification
- **Point conversion** from Nova groups to numerical scores (100, 80, 50, 20)

This approach provides a robust and scientifically-based method for evaluating the processing level of food products, helping consumers make informed choices about their food consumption.
