import pandas as pd
import os
from pathlib import Path

SPECIFICATIONS_MAPPINGS = {
    'Acizi grasi saturati (g sau ml)': 'saturated_fat',
    'Alergeni': 'allergens',
    'Aroma': 'aroma',
    'Avertismente': 'warnings',
    'Cantitate': 'quantity',
    'Cantitate / pachet': 'quantity_per_packet',
    'Caracteristici speciale': 'special_features',
    'Conditii de pastrare': 'storage_conditions',
    'Continut alcool (% vol)': 'alcohol_content',
    'Continut cafeina': 'caffeine_content',
    'Culoare': 'color',
    'Destinat pentru': 'intended_for',
    'Dieta si lifestyle': 'diet_and_lifestyle',
    'Fibre (g sau ml)': 'fiber',
    'Greutate': 'weight',
    'Ingrediente': 'ingredients',
    'Intensitate': 'intensity',
    'KJ pe 100g sau 100ml': 'kj_per_100g_or_100ml',
    'Minerale': 'minerals',
    'Mod de ambalare': 'packaging_mod',
    'Mod de preparare': 'preparation_mod',
    'Nivel prajire': 'roasting_level',
    'Pentru': 'for',
    'Precautii': 'precautions',
    'Procent grasime (%)': 'fat_percentage',
    'Sare (g sau ml)': 'salt',
    'Tara de origine': 'origin_country',
    'Termen de valabilitate': 'expiration_date',
    'Tip Produs': 'product_type',
    'Tip ambalaj': 'packaging_type',
    'Tip cafea': 'coffee_type',
    'Vitamine': 'vitamins',
    'Volum (l)': 'volume',
}

NUTRITIONAL_INFO_MAPPINGS = {
    'Glucide (g sau ml)': 'carbohydrates',
    'Grasimi (g sau ml)': 'fat',
    'Kcal pe 100g sau 100ml': 'calories_per_100g_or_100ml',
    'Proteine (g sau ml)': 'protein',
    'Zaharuri (g sau ml)': 'sugar',
}


def process_csv_columns(csv_path):
    """
    Process a CSV file by mapping the keys within specifications and nutritional_info dictionaries.
    Keeps the original column structure but updates the dictionary keys.
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        tuple: (pd.DataFrame with mapped dictionary keys, list of unmapped columns)
    """
    # Read the CSV file
    df = pd.read_csv(csv_path)
    unmapped_columns = []
    
    # Check if required columns exist
    required_columns = ['specifications', 'nutritional_info']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"WARNING: Missing required columns in {csv_path}: {missing_columns}")
        return df, missing_columns

    # Process specifications column
    if 'specifications' in df.columns:
        try:
            # Convert string representation of dict to actual dict
            df['specifications'] = df['specifications'].apply(eval)
            
            # Update dictionary keys in specifications
            for idx, row in df.iterrows():
                specs = row['specifications']
                if isinstance(specs, dict):
                    new_specs = {}
                    for key, value in specs.items():
                        if key in SPECIFICATIONS_MAPPINGS:
                            new_specs[SPECIFICATIONS_MAPPINGS[key]] = value
                        else:
                            unmapped_columns.append(f"specifications.{key}")
                            new_specs[key] = value
                    df.at[idx, 'specifications'] = new_specs
        except Exception as e:
            print(f"Error processing specifications in {csv_path}: {str(e)}")
            unmapped_columns.append("specifications")

    # Process nutritional_info column
    if 'nutritional_info' in df.columns:
        try:
            # Convert string representation of dict to actual dict
            df['nutritional_info'] = df['nutritional_info'].apply(eval)
            
            # Update dictionary keys in nutritional_info
            for idx, row in df.iterrows():
                nutr_info = row['nutritional_info']
                if isinstance(nutr_info, dict):
                    new_nutr_info = {}
                    for key, value in nutr_info.items():
                        if key in NUTRITIONAL_INFO_MAPPINGS:
                            new_nutr_info[NUTRITIONAL_INFO_MAPPINGS[key]] = value
                        else:
                            unmapped_columns.append(f"nutritional_info.{key}")
                            new_nutr_info[key] = value
                    df.at[idx, 'nutritional_info'] = new_nutr_info
        except Exception as e:
            print(f"Error processing nutritional_info in {csv_path}: {str(e)}")
            unmapped_columns.append("nutritional_info")

    return df, unmapped_columns

def process_all_processed_csvs(base_dir):
    """
    Process all CSV files ending with '_processed' in the given directory and its subdirectories.
    Updates the files in place with mapped column names.
    Reverts changes if any columns could not be mapped.
    
    Args:
        base_dir (str): Base directory to search for CSV files
    """
    base_path = Path(base_dir)
    
    # Find all CSV files ending with '_processed'
    processed_csvs = list(base_path.rglob("*_processed.csv"))
    
    for csv_path in processed_csvs:
        print(f"Processing {csv_path}")
        
        try:
            # Read original file for backup
            original_df = pd.read_csv(csv_path)
            
            # Process the CSV
            df, unmapped_columns = process_csv_columns(csv_path)
            
            # Check if there are any unmapped columns
            if unmapped_columns:
                print(f"WARNING: Found unmapped columns in {csv_path}:")
                for col in unmapped_columns:
                    print(f"  - {col}")
                print("Reverting changes...")
                # Save back the original data
                original_df.to_csv(csv_path, index=False)
                print(f"Reverted changes in {csv_path}")
            else:
                # Save the mapped version
                df.to_csv(csv_path, index=False)
                print(f"Updated {csv_path} with mapped column names")
            
        except Exception as e:
            print(f"Error processing {csv_path}: {str(e)}")
            # In case of any error, try to revert to original
            try:
                original_df.to_csv(csv_path, index=False)
                print(f"Reverted changes in {csv_path} due to error")
            except:
                print(f"Failed to revert changes in {csv_path}")

# Example usage:
if __name__ == "__main__":
    # Get the current script's directory and navigate to the auchan folder
    current_dir = Path(__file__).parent.parent.parent
    base_directory = current_dir / "auchan"
    process_all_processed_csvs(base_directory)