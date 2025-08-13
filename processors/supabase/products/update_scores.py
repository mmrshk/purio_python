import os
from processors.helpers.scoring.types.nutri_score import NutriScoreCalculator
from processors.helpers.scoring.types.additives_score import AdditivesScoreCalculator
from processors.helpers.scoring.types.nova_score import NovaScoreCalculator
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are not set in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_final_health_score(nutri, additives, nova):
    # If any score is None, return None (cannot calculate final score)
    if nutri is None or additives is None or nova is None:
        return None

    return int(round(nutri * 0.4 + additives * 0.3 + nova * 0.3))

def update_all_scores():
    # Fetch all products from Supabase
    result = supabase.table('products').select('*').execute()
    if hasattr(result, 'error') and result.error:
        print(f"Error fetching products: {result.error}")
        return
    products = result.data

    nutri_calc = NutriScoreCalculator()
    additives_calc = AdditivesScoreCalculator()
    nova_calc = NovaScoreCalculator()

    for product in products:
        product_data = product  # Use the full product dict for scoring
        nutri_score = nutri_calc.calculate(product_data)
        additives_score = additives_calc.calculate(product_data)
        nova_score = nova_calc.calculate(product_data)
        final_score = calculate_final_health_score(nutri_score, additives_score, nova_score)
        
        print(f"Product: {product.get('name', 'Unknown')} (ID: {product.get('id', 'N/A')})")
        print(f"  NutriScore: {nutri_score}")
        print(f"  AdditivesScore: {additives_score}")
        print(f"  NovaScore: {nova_score}")
        print(f"  Final Health Score: {final_score}")
        
        if final_score is None:
            print("  ⚠️  Skipped: Cannot calculate final score (missing data)")
        else:
            print("  ✅ Score calculated successfully")
        print("---")
        # Here you would update the DB with these values

if __name__ == "__main__":
    update_all_scores() 