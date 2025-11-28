#!/usr/bin/env python3
"""
Health Score Filler for CSV files.

This module provides functionality to calculate health scores for products in CSV files
using the existing scoring system (Nova, Nutri, and Additives scores).
"""

import pandas as pd
import os
import sys
from pathlib import Path

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from processors.scoring.types.nutri_score import NutriScoreCalculator
from processors.scoring.types.additives_score import AdditivesScoreCalculator
from processors.scoring.types.nova_score import NovaScoreCalculator

def calculate_final_health_score(nutri, additives, nova):
    """
    Calculate final health score using the same formula as the main system.
    
    Args:
        nutri: Nutri score (0-100)
        additives: Additives score (0-100)
        nova: Nova score (0-100)
        
    Returns:
        Final health score (0-100) or None if any score is missing
    """
    if nutri is None or additives is None or nova is None:
        return None
    
    return int(round(nutri * 0.4 + additives * 0.3 + nova * 0.3))

def fill_health_scores_in_csv(csv_path):
    """
    Calculate and add health scores to a CSV file.
    
    Args:
        csv_path (str): Path to the CSV file to process
    """
    print(f"\n🏥 Calculating health scores for {csv_path}")
    print("=" * 60)
    
    # Read the CSV file
    try:
        df = pd.read_csv(csv_path)
        print(f"📊 Loaded {len(df)} products from CSV")
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return
    
    # Initialize calculators
    nutri_calc = NutriScoreCalculator()
    additives_calc = AdditivesScoreCalculator()
    nova_calc = NovaScoreCalculator()
    
    # Add health score columns if they don't exist
    if 'health_score' not in df.columns:
        df['health_score'] = None
    if 'nutri_score' not in df.columns:
        df['nutri_score'] = None
    if 'additives_score' not in df.columns:
        df['additives_score'] = None
    if 'nova_score' not in df.columns:
        df['nova_score'] = None
    if 'final_score' not in df.columns:
        df['final_score'] = None
    
    # Track statistics
    processed_count = 0
    successful_count = 0
    failed_count = 0
    
    print(f"\n🔄 Processing products...")
    
    for idx, (_, row) in enumerate(df.iterrows()):
        product_name = row.get('name', f'Product {idx + 1}')
        print(f"\n[{idx + 1}/{len(df)}] Processing: {product_name}")
        
        try:
            # Prepare product data for scoring
            product_data = {
                'name': row.get('name'),
                'barcode': row.get('barcode'),
                'specifications': row.get('specifications', {}),
                'nutritional': row.get('nutritional', {}),
                'ingredients': row.get('ingredients', '')
            }
            
            # Calculate individual scores
            nutri_score = None
            additives_score = None
            nova_score = None
            
            # Calculate Nutri Score
            try:
                nutri_score = nutri_calc.calculate(product_data)
                if nutri_score:
                    print(f"  🍎 Nutri Score: {nutri_score}")
                else:
                    print(f"  🍎 Nutri Score: Not available")
            except Exception as e:
                print(f"  🍎 Nutri Score: Error - {e}")
            
            # Calculate Additives Score
            try:
                additives_score = additives_calc.calculate(product_data)
                if additives_score:
                    print(f"  ⚠️  Additives Score: {additives_score}")
                else:
                    print(f"  ⚠️  Additives Score: Not available")
            except Exception as e:
                print(f"  ⚠️  Additives Score: Error - {e}")
            
            # Calculate Nova Score
            try:
                nova_score = nova_calc.calculate(product_data)
                if nova_score:
                    print(f"  🥗 Nova Score: {nova_score}")
                else:
                    print(f"  🥗 Nova Score: Not available")
            except Exception as e:
                print(f"  🥗 Nova Score: Error - {e}")
            
            # Calculate final health score
            final_score = calculate_final_health_score(nutri_score, additives_score, nova_score)
            
            if final_score is not None:
                print(f"  🏆 Final Health Score: {final_score}")
                successful_count += 1
            else:
                print(f"  🏆 Final Health Score: Cannot calculate (missing scores)")
                failed_count += 1
            
            # Update the dataframe
            df.at[idx, 'nutri_score'] = nutri_score
            df.at[idx, 'additives_score'] = additives_score
            df.at[idx, 'nova_score'] = nova_score
            df.at[idx, 'final_score'] = final_score
            df.at[idx, 'health_score'] = final_score  # For backward compatibility
            
            processed_count += 1
            
        except Exception as e:
            print(f"  ❌ Error processing product: {e}")
            failed_count += 1
            continue
    
    # Save the updated CSV
    try:
        df.to_csv(csv_path, index=False)
        print(f"\n✅ Successfully saved updated CSV to {csv_path}")
    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        return
    
    # Print summary
    print(f"\n📈 Health Scoring Summary:")
    print(f"  Total products processed: {processed_count}")
    print(f"  Successfully scored: {successful_count}")
    print(f"  Failed to score: {failed_count}")
    print(f"  Success rate: {(successful_count / processed_count * 100):.1f}%" if processed_count > 0 else "N/A")
    
    if successful_count > 0:
        # Show score distribution
        final_scores = df['final_score'].dropna()
        if len(final_scores) > 0:
            print(f"\n📊 Score Distribution:")
            print(f"  Average score: {final_scores.mean():.1f}")
            print(f"  Highest score: {final_scores.max()}")
            print(f"  Lowest score: {final_scores.min()}")
            
            # Score ranges
            excellent = len(final_scores[final_scores >= 80])
            good = len(final_scores[(final_scores >= 60) & (final_scores < 80)])
            fair = len(final_scores[(final_scores >= 40) & (final_scores < 60)])
            poor = len(final_scores[final_scores < 40])
            
            print(f"\n🎯 Score Ranges:")
            print(f"  Excellent (80-100): {excellent} products")
            print(f"  Good (60-79): {good} products")
            print(f"  Fair (40-59): {fair} products")
            print(f"  Poor (0-39): {poor} products")

def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Calculate health scores for products in a CSV file')
    parser.add_argument('csv_path', help='Path to the CSV file to process')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_path):
        print(f"❌ Error: CSV file not found: {args.csv_path}")
        return
    
    fill_health_scores_in_csv(args.csv_path)

if __name__ == "__main__":
    main()
