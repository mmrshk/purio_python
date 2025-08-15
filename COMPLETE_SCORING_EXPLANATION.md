# Complete Health Scoring System - User Guide

## 🎯 What is the Health Score?

The Health Score is a comprehensive rating system that evaluates how healthy a food product is based on **three key factors**:

1. **Nova Score** - How processed the food is
2. **Nutri Score** - Nutritional quality 
3. **Additives Score** - Safety of food additives

Each product gets a **final score from 0 to 100**, where:
- **80-100**: Excellent - Very healthy choice
- **60-79**: Good - Healthy choice
- **40-59**: Fair - Moderate choice
- **20-39**: Poor - Unhealthy choice
- **0-19**: Very Poor - Avoid

---

## 📊 How the Final Score is Calculated

The final health score combines all three scores using this formula:

```
Final Score = (Nutri Score × 40%) + (Additives Score × 30%) + (Nova Score × 30%)
```

### Why These Weights?
- **Nutri Score (40%)**: Most important - directly measures nutritional value
- **Additives Score (30%)**: Important - affects long-term health
- **Nova Score (30%)**: Important - processing level impacts health

---

## 🥗 Score 1: Nova Score (Processing Level)

**What it measures**: How much industrial processing the food has undergone

### Nova Score Scale:
- **100 points**: Unprocessed foods (fruits, vegetables, fresh meat)
- **80 points**: Culinary ingredients (oil, sugar, salt, spices)
- **50 points**: Processed foods (bread, cheese, yogurt)
- **20 points**: Ultra-processed foods (packaged snacks, sodas)

### How it works:
1. **Analyzes ingredients** from the product label
2. **Classifies each ingredient** into Nova groups 1-4
3. **Applies rules** to determine final Nova group:
   - Any ultra-processed ingredient → Nova 4 (20 points)
   - Any processed ingredient → Nova 3 (50 points)
   - Mix of natural + culinary → Nova 3 (50 points)
   - Only culinary ingredients → Nova 2 (80 points)
   - Only natural ingredients → Nova 1 (100 points)

### Examples:
- **Fresh apple**: Nova 1 (100 points) - unprocessed
- **Olive oil**: Nova 2 (80 points) - culinary ingredient
- **Whole grain bread**: Nova 3 (50 points) - processed
- **Packaged cookies**: Nova 4 (20 points) - ultra-processed

---

## 🍎 Score 2: Nutri Score (Nutritional Quality)

**What it measures**: How nutritious the food is based on its nutritional content

### Nutri Score Scale:
- **100 points**: Nutri-Score A (excellent nutrition)
- **80 points**: Nutri-Score B (good nutrition)
- **60 points**: Nutri-Score C (moderate nutrition)
- **40 points**: Nutri-Score D (poor nutrition)
- **20 points**: Nutri-Score E (very poor nutrition)

### How it works:
1. **Analyzes nutritional values** (per 100g):
   - **Negative factors**: Energy, sugar, saturated fat, sodium
   - **Positive factors**: Fiber, protein, fruits/vegetables
2. **Calculates points** for each nutrient
3. **Subtracts negative points** from positive points
4. **Converts to letter grade** (A-E) and then to points (100-20)

### Examples:
- **Fresh vegetables**: Nutri-Score A (100 points) - high fiber, low calories
- **Whole grain bread**: Nutri-Score B (80 points) - good fiber, moderate calories
- **Processed meat**: Nutri-Score D (40 points) - high fat, high sodium
- **Sugary drinks**: Nutri-Score E (20 points) - high sugar, no nutrients

---

## ⚠️ Score 3: Additives Score (Additive Safety)

**What it measures**: How safe the food additives are

### Additives Score Scale:
- **100 points**: No additives or only safe additives
- **75 points**: Low-risk additives
- **50 points**: Moderate-risk additives
- **0 points**: High-risk additives

### How it works:
1. **Identifies all additives** in the ingredient list
2. **Classifies each additive** by risk level:
   - **Free risk**: Natural, safe additives (100 points each)
   - **Low risk**: Generally safe additives (75 points each)
   - **Moderate risk**: Questionable additives (50 points each)
   - **High risk**: Potentially harmful additives (0 points each)
3. **Averages the scores** of all additives found

### Examples:
- **Fresh fruit**: 100 points - no additives
- **Natural yogurt**: 100 points - only safe cultures
- **Processed cheese**: 50 points - moderate-risk preservatives
- **Artificial snacks**: 0 points - high-risk artificial colors/flavors

---

## 🏆 Final Score Calculation Examples

### Example 1: Fresh Apple
- **Nova Score**: 100 points (unprocessed)
- **Nutri Score**: 100 points (Nutri-Score A)
- **Additives Score**: 100 points (no additives)
- **Final Score**: (100 × 40%) + (100 × 30%) + (100 × 30%) = **100 points** ✅

### Example 2: Whole Grain Bread
- **Nova Score**: 50 points (processed)
- **Nutri Score**: 80 points (Nutri-Score B)
- **Additives Score**: 75 points (low-risk additives)
- **Final Score**: (80 × 40%) + (75 × 30%) + (50 × 30%) = **69 points** ✅

### Example 3: Packaged Cookies
- **Nova Score**: 20 points (ultra-processed)
- **Nutri Score**: 20 points (Nutri-Score E)
- **Additives Score**: 0 points (high-risk additives)
- **Final Score**: (20 × 40%) + (0 × 30%) + (20 × 30%) = **14 points** ❌

### Example 4: Natural Yogurt
- **Nova Score**: 50 points (processed)
- **Nutri Score**: 80 points (Nutri-Score B)
- **Additives Score**: 100 points (safe cultures only)
- **Final Score**: (80 × 40%) + (100 × 30%) + (50 × 30%) = **77 points** ✅

---

## 🚨 Special Rules

### High-Risk Additives Penalty
If a product contains **any high-risk additives**, the final display score is **capped at 49 points**, regardless of how good the other scores are.

**Why?** High-risk additives can have serious health consequences, so even nutritious foods become risky choices.

### Missing Data
If **any of the three scores is missing**, the final score cannot be calculated and will show as "Not Available."

**Why?** We need complete information to give you an accurate health assessment.

---

## 💡 How to Use This Information

### For Shopping:
- **Choose products with scores 60+** for healthy choices
- **Avoid products with scores below 40** when possible
- **Look at individual scores** to understand specific concerns
- **Compare similar products** to find the healthiest option

### Understanding Your Food:
- **High Nova Score**: Less processed = generally better
- **High Nutri Score**: More nutrients, fewer empty calories
- **High Additives Score**: Fewer artificial ingredients = safer

### Making Better Choices:
- **Fresh foods** usually score highest
- **Read ingredient lists** to understand what you're eating
- **Choose whole foods** over processed alternatives
- **Limit ultra-processed foods** in your diet

---

## 🔍 Where to Find Scores

Scores are displayed on:
- **Product detail pages**
- **Search results**
- **Shopping lists**
- **Nutritional analysis reports**

Each score includes:
- **Numerical value** (0-100)
- **Color coding** (green = good, yellow = moderate, red = poor)
- **Explanation** of what the score means
- **Tips** for making healthier choices

---

## 📈 Score Improvement Tips

### To Improve Nova Score:
- Choose fresh, unprocessed foods
- Avoid products with long ingredient lists
- Look for "whole" or "natural" ingredients
- Minimize packaged and convenience foods

### To Improve Nutri Score:
- Choose foods high in fiber and protein
- Avoid foods high in sugar, salt, and saturated fat
- Include plenty of fruits and vegetables
- Read nutrition labels carefully

### To Improve Additives Score:
- Choose products with fewer ingredients
- Avoid artificial colors, flavors, and preservatives
- Look for "no artificial additives" labels
- Prefer natural and organic options

---

This scoring system helps you make informed decisions about your food choices, leading to better health and nutrition! 🎯
