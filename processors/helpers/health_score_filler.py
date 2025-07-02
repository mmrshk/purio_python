import pandas as pd
import os
import sys
from pathlib import Path

# Add the parent directory to the path to import the health_scorer
sys.path.append(str(Path(__file__).parent))
from health_scorer import HealthScorer

def fill_health_scores_in_csv(csv_path: str, save_original: bool = True) -> str:
    """
    Fill health scores for products in a CSV file.
    
    Args:
        csv_path: Path to the CSV file
        save_original: Whether to save a backup of the original file
        
    Returns:
        str: Path to the updated CSV file
    """
    print(f"\n=== Filling Health Scores ===")
    print(f"Processing: {csv_path}")
    
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} does not exist")
        return csv_path
    
    # Create backup if requested
    if save_original:
        backup_path = csv_path.replace('.csv', '_backup.csv')
        if not os.path.exists(backup_path):
            df_original = pd.read_csv(csv_path)
            df_original.to_csv(backup_path, index=False)
            print(f"Created backup: {backup_path}")
    
    # Read the CSV
    try:
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} products")
    except Exception as e:
        print(f"Error reading CSV: {str(e)}")
        return csv_path
    
    # Check if health_score column already exists
    if 'health_score' in df.columns:
        print("Health scores already exist. Skipping...")
        return csv_path
    
    # Initialize the health scorer
    scorer = HealthScorer()
    
    # Calculate health scores
    print("Calculating health scores...")
    health_scores = []
    score_categories = []
    score_colors = []
    
    for idx, row in df.iterrows():
        if idx % 50 == 0:
            print(f"Processing product {idx + 1}/{len(df)}...")
        
        # Prepare product data
        product_data = {
            'nutritional': row.get('nutritional_info', {}),
            'ingredients': row.get('ingredients', '')
        }
        
        # Calculate score
        score = scorer.calculate_health_score(product_data)
        health_scores.append(score)
        
        # Get category and color
        score_categories.append(scorer.get_score_category(score))
        score_colors.append(scorer.get_score_color(score))
    
    # Add new columns
    df['health_score'] = health_scores
    df['score_category'] = score_categories
    df['score_color'] = score_colors
    
    # Save the updated CSV
    df.to_csv(csv_path, index=False)
    print(f"Updated CSV saved to: {csv_path}")
    
    # Print summary
    print(f"\nHealth Score Summary:")
    print(f"Total products: {len(df)}")
    print(f"Average score: {df['health_score'].mean():.1f}")
    print(f"Score distribution:")
    print(f"  Healthy choice (76-100): {len(df[df['health_score'] >= 76])}")
    print(f"  Caution (51-75): {len(df[(df['health_score'] >= 51) & (df['health_score'] < 76)])}")
    print(f"  Think twice (26-50): {len(df[(df['health_score'] >= 26) & (df['health_score'] < 51)])}")
    print(f"  High risk (0-25): {len(df[df['health_score'] < 26])}")
    
    return csv_path

def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fill health scores in CSV files')
    parser.add_argument('csv_path', help='Path to the CSV file to process')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup file')
    
    args = parser.parse_args()
    
    fill_health_scores_in_csv(args.csv_path, not args.no_backup)

if __name__ == "__main__":
    main() 