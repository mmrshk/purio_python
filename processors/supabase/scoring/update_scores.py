import os
import sys
from datetime import datetime

# Add the project root to the path for cleaner imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from processors.scoring.product_scorer import ProductScorer
from processors.scoring.types.nutri_score import NutriScoreCalculator
from processors.scoring.types.additives_score import AdditivesScoreCalculator
from processors.scoring.types.nova_score import NovaScoreCalculator
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are not set in environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_product_high_risk_additives(product_id: str) -> bool:
    """
    Check if a product has high-risk additives.
    
    Args:
        product_id: Product ID to check
        
    Returns:
        True if product has high-risk additives, False otherwise
    """
    try:
        # Get additives relations for this product
        result = supabase.table('product_additives_relations').select('additive_id').eq('product_id', product_id).execute()
        
        if hasattr(result, 'error') and result.error:
            return False
        
        additive_ids = [relation.get('additive_id') for relation in result.data]
        
        if not additive_ids:
            return False
        
        # Check if any of these additives are high-risk
        high_risk_result = supabase.table('additives').select('id').in_('id', additive_ids).eq('is_high_risk', True).execute()
        
        if hasattr(high_risk_result, 'error') and high_risk_result.error:
            return False
        
        return len(high_risk_result.data) > 0
        
    except Exception as e:
        return False

def log_and_print(message, log_file):
    """Print to console and write to log file"""
    print(message)
    log_file.write(message + '\n')
    log_file.flush()  # Ensure immediate write to file

def update_all_scores(imported_at_timestamp=None):
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"scoring_results_{timestamp}.log"
    
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_and_print(f"Health Scoring Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_file)
        log_and_print("="*80, log_file)
        
        # Fetch products from Supabase that need scoring
        if imported_at_timestamp:
            # Get products with specific imported_at timestamp that are missing final_score
            result = supabase.table('products').select('*').eq('imported_at', imported_at_timestamp).is_('final_score', 'null').execute()
            log_and_print(f"Filtering by imported_at timestamp: {imported_at_timestamp}", log_file)
        else:
            # Get all products missing final_score (original behavior)
            result = supabase.table('products').select('*').is_('final_score', 'null').execute()
            log_and_print("Processing all products missing final_score", log_file)
        if hasattr(result, 'error') and result.error:
            error_msg = f"Error fetching products: {result.error}"
            log_and_print(error_msg, log_file)
            return
        products = result.data
        
        if imported_at_timestamp:
            log_and_print(f"Found {len(products)} products to analyze (imported_at: {imported_at_timestamp}, missing final_score)", log_file)
        else:
            log_and_print(f"Found {len(products)} products to analyze (missing final_score)", log_file)
        log_and_print("", log_file)

        # Initialize ProductScorer (with auto_save_to_db=False since we handle DB updates ourselves)
        scorer = ProductScorer(
            dry_run=False,
            supabase_client=supabase,
            auto_insert_new_ingredients=True,
            auto_save_to_db=False  # We handle DB updates manually in this script
        )
        
        # Also initialize individual calculators for detailed logging
        nutri_calc = NutriScoreCalculator()
        additives_calc = AdditivesScoreCalculator()
        nova_calc = NovaScoreCalculator()

        # Track statistics
        successful_updates = 0
        failed_updates = 0
        skipped_products = 0

        for i, product in enumerate(products, 1):
            product_data = product  # Use the full product dict for scoring
            product_name = product.get('name', 'Unknown')
            product_id = product.get('id', 'N/A')
            
            log_and_print(f"\n{'='*80}", log_file)
            log_and_print(f"PRODUCT {i}/{len(products)}: {product_name} (ID: {product_id})", log_file)
            log_and_print(f"{'='*80}", log_file)
            
            # Use ProductScorer to calculate all scores (handles extracted > matched check)
            scores = scorer.calculate_health_scores(product_data)
            
            # Extract scores for logging
            nutri_score = scores.get('nutri_score')
            nutri_source = scores.get('nutri_source')
            additives_score = scores.get('additives_score')
            nova_score = scores.get('nova_score')
            nova_source = scores.get('nova_source')
            final_score = scores.get('final_score')
            display_score = scores.get('display_score')
            
            # Calculate NutriScore with detailed breakdown (for logging)
            log_and_print(f"\n📊 NUTRI-SCORE CALCULATION:", log_file)
            log_and_print(f"{'-'*50}", log_file)
            nutri_result = nutri_calc.calculate(product_data)
            if isinstance(nutri_result, tuple):
                detailed_nutri_score, detailed_nutri_source = nutri_result
            else:
                detailed_nutri_score, detailed_nutri_source = nutri_result, 'unknown'
            
            # Use detailed scores for logging (ProductScorer already calculated them correctly)
            nutri_score = detailed_nutri_score
            nutri_source = detailed_nutri_source
            
            log_and_print(f"  Source: {nutri_source}", log_file)
            
            # Show detailed calculation for local NutriScore
            if nutri_source == 'local':
                # Get nutritional and specifications data
                nutritional_data = product_data.get('nutritional', {})
                specifications_data = product_data.get('specifications', {})
                
                if isinstance(nutritional_data, str):
                    try:
                        import json
                        nutritional_data = json.loads(nutritional_data)
                    except:
                        nutritional_data = {}
                
                if isinstance(specifications_data, str):
                    try:
                        import json
                        specifications_data = json.loads(specifications_data)
                    except:
                        specifications_data = {}
                
                # Calculate negative points (N)
                n_points = nutri_calc.calculate_negative_points(nutritional_data)
                log_and_print(f"  Negative Points (N): {n_points}", log_file)
                
                # Show breakdown of negative points
                if nutritional_data:
                    log_and_print(f"    Breakdown:", log_file)
                    
                    # Energy
                    energy_kcal = nutri_calc.extract_nutritional_value(nutritional_data, 'calories_per_100g_or_100ml')
                    if energy_kcal > 0:
                        energy_kj = energy_kcal * 4.184
                        energy_points = nutri_calc.get_points_for_value(energy_kj, nutri_calc.NEGATIVE_POINTS_THRESHOLDS['energy'])
                        log_and_print(f"      Energy: {energy_kcal} kcal ({energy_kj:.1f} kJ) → {energy_points} points", log_file)
                    
                    # Sugars
                    sugars = nutri_calc.extract_nutritional_value(nutritional_data, 'sugar')
                    if sugars > 0:
                        sugar_points = nutri_calc.get_points_for_value(sugars, nutri_calc.NEGATIVE_POINTS_THRESHOLDS['sugars'])
                        log_and_print(f"      Sugars: {sugars}g → {sugar_points} points", log_file)
                    
                    # Fat (approximated as saturated fat)
                    fat = nutri_calc.extract_nutritional_value(nutritional_data, 'fat')
                    if fat > 0:
                        saturated_fat = fat * 0.3
                        fat_points = nutri_calc.get_points_for_value(saturated_fat, nutri_calc.NEGATIVE_POINTS_THRESHOLDS['saturated_fat'])
                        log_and_print(f"      Saturated Fat: {saturated_fat:.1f}g (from {fat}g total fat) → {fat_points} points", log_file)
                    
                    # Sodium (not available in current data)
                    log_and_print(f"      Sodium: 0g (not available) → 0 points", log_file)
                
                # Calculate positive points (P)
                p_points = nutri_calc.calculate_positive_points(nutritional_data, specifications_data)
                log_and_print(f"  Positive Points (P): {p_points}", log_file)
                
                # Show breakdown of positive points
                log_and_print(f"    Breakdown:", log_file)
                
                # Fiber
                fiber = nutri_calc.extract_specification_value(specifications_data, 'fiber')
                if fiber > 0:
                    fiber_points = nutri_calc.get_points_for_value(fiber, nutri_calc.POSITIVE_POINTS_THRESHOLDS['fiber'])
                    log_and_print(f"      Fiber: {fiber}g → {fiber_points} points", log_file)
                else:
                    log_and_print(f"      Fiber: 0g → 0 points", log_file)
                
                # Protein
                protein = nutri_calc.extract_nutritional_value(nutritional_data, 'protein')
                if protein > 0:
                    protein_points = nutri_calc.get_points_for_value(protein, nutri_calc.POSITIVE_POINTS_THRESHOLDS['protein'])
                    log_and_print(f"      Protein: {protein}g → {protein_points} points", log_file)
                else:
                    log_and_print(f"      Protein: 0g → 0 points", log_file)
                
                # Calculate final NutriScore grade
                final_grade = nutri_calc.calculate_final_nutriscore(n_points, p_points)
                log_and_print(f"  Final Calculation: N({n_points}) - P({p_points}) = {n_points - p_points} → Grade: {final_grade.upper()}", log_file)
                log_and_print(f"  Grade Mapping: {final_grade.upper()} → {nutri_score} points", log_file)
            
            elif nutri_source == 'special_case':
                log_and_print(f"  Special Case: Water/natural product with no nutritional data", log_file)
                log_and_print(f"  Assigned: Grade A → 100 points", log_file)
            
            log_and_print(f"  Final Score: {nutri_score}", log_file)
            
            # Show nutritional data used for calculation
            nutritional_data = product_data.get('nutritional', {})
            if isinstance(nutritional_data, str):
                try:
                    import json
                    nutritional_data = json.loads(nutritional_data)
                except:
                    nutritional_data = {}
            
            if nutritional_data:
                log_and_print(f"  Nutritional Data Used:", log_file)
                for key, value in nutritional_data.items():
                    if value and key in ['calories_per_100g_or_100ml', 'sugar', 'fat', 'protein']:
                        log_and_print(f"    {key}: {value}", log_file)
            
            # Calculate AdditivesScore with detailed breakdown (for logging)
            log_and_print(f"\n🧪 ADDITIVES SCORE CALCULATION:", log_file)
            log_and_print(f"{'-'*50}", log_file)
            additives_result = additives_calc.calculate_from_product_additives(product_id) if product_id != 'N/A' else None
            
            if additives_result:
                additives_score = additives_result['score']
                additives_found = additives_result['additives_found']
                risk_breakdown = additives_result['risk_breakdown']
                high_risk_additives = additives_result['high_risk_additives']
                
                log_and_print(f"  Additives Found: {additives_found}", log_file)
                log_and_print(f"  Risk Breakdown:", log_file)
                log_and_print(f"    Free risk: {risk_breakdown['free']}", log_file)
                log_and_print(f"    Low risk: {risk_breakdown['low']}", log_file)
                log_and_print(f"    Moderate risk: {risk_breakdown['moderate']}", log_file)
                log_and_print(f"    High risk: {risk_breakdown['high']}", log_file)
                
                if high_risk_additives:
                    log_and_print(f"  High Risk Additives:", log_file)
                    for additive in high_risk_additives:
                        log_and_print(f"    - {additive['code']} ({additive['name']}): {additive['risk_level']}", log_file)
                
                log_and_print(f"  Final Score: {additives_score}", log_file)
            else:
                additives_score = scores.get('additives_score')  # Use from ProductScorer
                log_and_print(f"  Could not calculate additives score (no product_id or unknown risk levels)", log_file)
            
            # Calculate NovaScore with detailed breakdown (for logging)
            log_and_print(f"\n🌱 NOVA SCORE CALCULATION:", log_file)
            log_and_print(f"{'-'*50}", log_file)
            nova_result = nova_calc.calculate(product_data)
            if isinstance(nova_result, tuple):
                nova_score, nova_source = nova_result
            else:
                nova_score, nova_source = nova_result, 'unknown'
            
            log_and_print(f"  Source: {nova_source}", log_file)
            
            # Show special case handling
            if nova_source == 'special_case':
                product_name_lower = product_name.lower() if product_name else ""
                
                # Check for water/natural products
                if any(keyword in product_name_lower for keyword in ['water', 'apa', 'mineral', 'spring']):
                    log_and_print(f"  Special Case: Water/natural product with no ingredients", log_file)
                    log_and_print(f"  Assigned: NOVA 1 (Unprocessed) → 100 points", log_file)
                
                # Check for alcoholic beverages
                elif any(keyword in product_name_lower for keyword in ['beer', 'bere', 'wine', 'vin', 'spirit', 'vodka', 'whiskey', 'rum', 'gin', 'liqueur', 'cocktail']):
                    log_and_print(f"  Special Case: Alcoholic beverage with no ingredients", log_file)
                    log_and_print(f"  Assigned: NOVA 3 (Processed) → 50 points", log_file)
            
            # Show ingredients analysis if using local calculation
            elif nova_source == 'local':
                specs = product_data.get('specifications', {})
                if isinstance(specs, str):
                    try:
                        import json
                        specs = json.loads(specs)
                    except:
                        specs = {}
                
                ingredients = specs.get('ingredients', '')
                if ingredients:
                    log_and_print(f"  Ingredients Analyzed: {ingredients[:100]}{'...' if len(ingredients) > 100 else ''}", log_file)
                    
                    # Get NOVA distribution from ingredients
                    nova_distribution = nova_calc.get_nova_distribution_from_ingredients(product_data)
                    if nova_distribution:
                        log_and_print(f"  NOVA Distribution:", log_file)
                        nova_counts = {1: 0, 2: 0, 3: 0, 4: 0}
                        for score in nova_distribution:
                            if score in nova_counts:
                                nova_counts[score] += 1
                        
                        for nova_group, count in nova_counts.items():
                            if count > 0:
                                group_names = {1: 'Unprocessed', 2: 'Culinary Ingredients', 3: 'Processed', 4: 'Ultra-processed'}
                                log_and_print(f"    NOVA {nova_group} ({group_names[nova_group]}): {count} ingredients", log_file)
            
            elif nova_source is None:
                log_and_print(f"  No ingredients data available and no special case match", log_file)
                log_and_print(f"  Cannot determine NOVA classification", log_file)
            
            log_and_print(f"  Final Score: {nova_score}", log_file)
            
            # Calculate final health score (using ProductScorer results which already check extracted > matched)
            log_and_print(f"\n🏆 FINAL HEALTH SCORE CALCULATION:", log_file)
            log_and_print(f"{'-'*50}", log_file)
            
            # Check if ingredients were extracted but not all matched (ProductScorer already did this)
            specs = product_data.get('specifications', {})
            if isinstance(specs, str):
                try:
                    import json
                    specs = json.loads(specs)
                except:
                    specs = {}
            
            parsed_ingredients = specs.get('parsed_ingredients', {})
            if isinstance(parsed_ingredients, dict):
                extracted_count = len(parsed_ingredients.get('extracted_ingredients', []))
                matched_count = len(parsed_ingredients.get('matches', []))
                
                if extracted_count > 0 and extracted_count > matched_count:
                    log_and_print(f"  ⚠️  Cannot calculate final score: {extracted_count} ingredients extracted but only {matched_count} matched", log_file)
                    log_and_print(f"  ⚠️  Missing ingredient data would make score inaccurate", log_file)
                    final_score = None
                    display_score = None
                else:
                    # Use scores from ProductScorer (already calculated with all checks)
                    final_score = scores.get('final_score')
                    display_score = scores.get('display_score')
            else:
                # Use scores from ProductScorer (already calculated)
                final_score = scores.get('final_score')
                display_score = scores.get('display_score')
            
            # Log which scores we're using
            log_and_print(f"  NutriScore: {nutri_score} (weight: 40%)", log_file)
            log_and_print(f"  AdditivesScore: {additives_score} (weight: 30%)", log_file)
            log_and_print(f"  NovaScore: {nova_score} (weight: 30%)", log_file)

            if final_score is not None:
                log_and_print(f"  Formula: ({nutri_score} × 0.4) + ({additives_score} × 0.3) + ({nova_score} × 0.3) = {final_score}", log_file)
                log_and_print(f"  ✅ Final Health Score: {final_score}", log_file)
                
                # Display score calculation (from ProductScorer)
                log_and_print(f"\n📱 DISPLAY SCORE CALCULATION:", log_file)
                log_and_print(f"{'-'*50}", log_file)
                
                has_high_risk_additives = check_product_high_risk_additives(product_id)
                
                log_and_print(f"  High-risk additives detected: {has_high_risk_additives}", log_file)
                log_and_print(f"  Display Score: {display_score}", log_file)
                
                if has_high_risk_additives and final_score > 49:
                    log_and_print(f"  ⚠️  Score capped at 49 due to high-risk additives", log_file)
                elif has_high_risk_additives and final_score <= 49:
                    log_and_print(f"  ℹ️  Score unchanged (≤49) despite high-risk additives", log_file)
                else:
                    log_and_print(f"  ✅ Score unchanged (no high-risk additives)", log_file)
            else:
                log_and_print(f"  ❌ Final Health Score: Cannot calculate (missing individual scores or incomplete ingredient data)", log_file)

            try:
                update_data = { 'updated_at': datetime.now().isoformat() }
                
                # Use scores from ProductScorer (which includes extracted > matched check)
                if final_score is not None:
                    update_data['final_score'] = final_score
                    if display_score is not None:
                    update_data['display_score'] = display_score
                if nutri_score is not None:
                    update_data['nutri_score'] = nutri_score
                    update_data['nutri_score_set_by'] = nutri_source
                if additives_score is not None:
                    update_data['additives_score'] = additives_score
                    update_data['additives_score_set_by'] = 'local'
                if nova_score is not None:
                    update_data['nova_score'] = nova_score
                    update_data['nova_score_set_by'] = nova_source
                
                # Remove None values to avoid database errors
                update_data = {k: v for k, v in update_data.items() if v is not None}
                
                log_and_print(f"  🔄 Updating database with: {update_data}", log_file)
                
                result = supabase.table('products').update(update_data).eq('id', product_id).execute()
                
                if hasattr(result, 'error') and result.error:
                    log_and_print(f"  ❌ Database update failed: {result.error}", log_file)
                    failed_updates += 1
                else:
                    log_and_print(f"  ✅ Database updated successfully", log_file)
                    successful_updates += 1
                    
            except Exception as e:
                log_and_print(f"  ❌ Database update error: {str(e)}", log_file)
                failed_updates += 1

            
            log_and_print(f"\n{'='*80}\n", log_file)
        
        # Summary at the end
        log_and_print(f"\n{'='*80}", log_file)
        log_and_print(f"ANALYSIS COMPLETE - {len(products)} products processed", log_file)
        log_and_print(f"✅ Successful updates: {successful_updates}", log_file)
        log_and_print(f"❌ Failed updates: {failed_updates}", log_file)
        log_and_print(f"⚠️  Skipped products: {skipped_products}", log_file)
        log_and_print(f"Log file saved as: {log_filename}", log_file)
        log_and_print(f"{'='*80}", log_file)
    
    print(f"\n✅ Analysis complete! Results saved to: {log_filename}")
    print(f"📊 Summary: {successful_updates} updated, {failed_updates} failed, {skipped_products} skipped")

if __name__ == "__main__":
    update_all_scores() 