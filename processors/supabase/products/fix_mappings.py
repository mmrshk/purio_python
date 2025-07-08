import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import json

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not supabase_key:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")
supabase = create_client(supabase_url, supabase_key)



# Mappings from the original file
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

def map_dictionary(old_dict, mappings):
    """Map dictionary keys using the provided mappings"""
    if not isinstance(old_dict, dict):
        try:
            # Try to parse string as JSON
            old_dict = json.loads(old_dict)
        except:
            return old_dict
            
    new_dict = {}
    for key, value in old_dict.items():
        # If key is already in English format (lowercase with underscores), keep it as is
        if key.islower() and '_' in key:
            new_dict[key] = value
        # If key needs mapping, map it
        elif key in mappings:
            new_key = mappings[key]
            new_dict[new_key] = value
            print(f"Mapping: {key} -> {new_key}")
        # If key is not in mappings and not in English format, keep it as is
        else:
            new_dict[key] = value
            print(f"No mapping found for: {key}")
    return new_dict

def check_mapping_needed(old_dict, mappings):
    """Check if a dictionary needs mapping by comparing its keys with the mappings"""
    if not isinstance(old_dict, dict):
        try:
            old_dict = json.loads(old_dict)
        except:
            return False, None
            
    needs_mapping = False
    unmapped_keys = []
    
    for key in old_dict.keys():
        # If the key is in Romanian format (contains spaces or special characters)
        if ' ' in key or '(' in key or ')' in key:
            if key in mappings:
                needs_mapping = True
            else:
                unmapped_keys.append(key)
            
    return needs_mapping, unmapped_keys

def fix_mappings():
    """
    Fix the mappings in Supabase by updating the specifications and nutritional columns.
    """
    try:
        updated_count = 0
        error_count = 0
        total_processed = 0
        unmapped_keys = set()
        needs_update = 0
        
        # Start with first page
        page = 0
        page_size = 1000
        
        while True:
            # Get products with pagination
            result = supabase.table('products').select('id, name, specifications, nutritional').range(
                page * page_size, 
                (page + 1) * page_size - 1
            ).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"Error fetching products: {result.error}")
                return
            
            products = result.data
            if not products:  # No more products to process
                break
                
            print(f"\nProcessing page {page + 1} ({len(products)} products)")
            
            for product in products:
                try:
                    needs_product_update = False
                    
                    # Check specifications
                    specs = product.get('specifications', {})
                    specs_needs_update, specs_unmapped = check_mapping_needed(specs, SPECIFICATIONS_MAPPINGS)
                    if specs_needs_update:
                        needs_product_update = True
                        for key in specs_unmapped:
                            unmapped_keys.add(f"specifications.{key}")
                    
                    # Check nutritional info
                    nutr = product.get('nutritional', {})
                    nutr_needs_update, nutr_unmapped = check_mapping_needed(nutr, NUTRITIONAL_INFO_MAPPINGS)
                    if nutr_needs_update:
                        needs_product_update = True
                        for key in nutr_unmapped:
                            unmapped_keys.add(f"nutritional.{key}")
                    
                    if needs_product_update:
                        needs_update += 1
                        print(f"\nUnmapped data found in product: {product['name']}")
                        
                        # Map specifications
                        new_specs = map_dictionary(specs, SPECIFICATIONS_MAPPINGS)
                        
                        # Map nutritional info
                        new_nutr = map_dictionary(nutr, NUTRITIONAL_INFO_MAPPINGS)
                        
                        # Update the product
                        update_result = supabase.table('products').update({
                            'specifications': new_specs,
                            'nutritional': new_nutr
                        }).eq('id', product['id']).execute()
                        
                        if hasattr(update_result, 'error') and update_result.error:
                            print(f"Error updating product {product['id']}: {update_result.error}")
                            error_count += 1
                        else:
                            updated_count += 1
                            print(f"Successfully updated mappings for product: {product['name']}")
                        
                except Exception as e:
                    print(f"Error processing product {product['id']}: {str(e)}")
                    error_count += 1
                
                total_processed += 1
            
            page += 1
        
        print(f"\nSummary:")
        print(f"Total products processed: {total_processed}")
        print(f"Products needing updates: {needs_update}")
        print(f"Successfully updated: {updated_count}")
        print(f"Errors: {error_count}")
        
        if unmapped_keys:
            print("\nUnmapped keys found:")
            for key in sorted(unmapped_keys):
                print(f"  - {key}")
            
            # Save unmapped keys to a file
            with open('unmapped_keys.json', 'w', encoding='utf-8') as f:
                json.dump(list(sorted(unmapped_keys)), f, indent=2)
            print("\nSaved unmapped keys to unmapped_keys.json")
        
    except Exception as e:
        print(f"Error fixing mappings: {str(e)}")
        import traceback
        print(traceback.format_exc())

def main():
    print("Starting to fix mappings in Supabase...")
    fix_mappings()
    print("Process completed.")

if __name__ == "__main__":
    main() 