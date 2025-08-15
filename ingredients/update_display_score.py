#!/usr/bin/env python3
"""
Script to update display_score field based on high-risk additives logic.
display_score = min(final_score, 49) if has high-risk additives else final_score
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")

supabase: Client = create_client(supabase_url, supabase_key)

def log_and_print(message: str, log_file):
    """Log message to file and print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    log_file.write(formatted_message + "\n")
    log_file.flush()

def check_product_high_risk_additives(product_id: str) -> bool:
    """
    Check if a product has any high-risk additives.
    
    Args:
        product_id: Product ID to check
        
    Returns:
        True if product has high-risk additives, False otherwise
    """
    try:
        # Query product_additives table with join to additives
        result = supabase.table('product_additives').select(
            'additive_id, additives!inner(*)'
        ).eq('product_id', product_id).execute()
        
        if hasattr(result, 'error') and result.error:
            print(f"Error querying product additives: {result.error}")
            return False
        
        additives = result.data
        if not additives:
            return False
        
        # Check each additive for high risk
        for relation in additives:
            additive = relation.get('additives', {})
            if additive:
                risk_level = additive.get('risk_level')
                if risk_level == 'High risk':
                    return True
        
        return False
        
    except Exception as e:
        print(f"Error checking high-risk additives for product {product_id}: {e}")
        return False

def calculate_display_score(final_score: int, has_high_risk_additive: bool) -> int:
    """
    Calculate display_score based on final_score and high-risk additives.
    
    Args:
        final_score: The calculated final health score
        has_high_risk_additive: Whether the product has high-risk additives
        
    Returns:
        The display score (capped at 49 if high-risk additives present)
    """
    if has_high_risk_additive:
        return min(final_score, 49)
    else:
        return final_score

def update_display_scores():
    """Update display_score field for all products based on final_score and high-risk additives."""
    
    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"display_score_update_{timestamp}.log"
    
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_and_print("="*80, log_file)
        log_and_print("DISPLAY SCORE UPDATE - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log_file)
        log_and_print("="*80, log_file)
        
        # Fetch all products with final_score
        log_and_print("📖 Fetching products with final_score from Supabase...", log_file)
        
        try:
            result = supabase.table('products').select('id, name, final_score').not_.is_('final_score', 'null').execute()
            if hasattr(result, 'error') and result.error:
                log_and_print(f"❌ Error fetching products: {result.error}", log_file)
                return
            
            products = result.data
            log_and_print(f"✅ Fetched {len(products)} products with final_score from Supabase", log_file)
            
        except Exception as e:
            log_and_print(f"❌ Error connecting to Supabase: {e}", log_file)
            return
        
        # Process each product
        updated_count = 0
        capped_count = 0
        unchanged_count = 0
        error_count = 0
        
        log_and_print(f"\n🔄 Processing products for display_score calculation...", log_file)
        log_and_print(f"{'-'*60}", log_file)
        
        for i, product in enumerate(products, 1):
            product_id = product.get('id')
            product_name = product.get('name', 'Unknown')
            final_score = product.get('final_score')
            
            try:
                # Check for high-risk additives
                has_high_risk = check_product_high_risk_additives(product_id)
                
                # Calculate display score
                display_score = calculate_display_score(final_score, has_high_risk)
                
                # Update the product in Supabase
                try:
                    update_result = supabase.table('products').update({
                        'display_score': display_score,
                        'updated_at': datetime.now().isoformat()
                    }).eq('id', product_id).execute()
                    
                    if hasattr(update_result, 'error') and update_result.error:
                        log_and_print(f"  {i:3d}. ❌ Error updating {product_name}: {update_result.error}", log_file)
                        error_count += 1
                    else:
                        updated_count += 1
                        
                        if has_high_risk and final_score > 49:
                            capped_count += 1
                            log_and_print(f"  {i:3d}. ✅ {product_name} - CAPPED: {final_score} → {display_score} (High-risk additives)", log_file)
                        elif has_high_risk and final_score <= 49:
                            unchanged_count += 1
                            log_and_print(f"  {i:3d}. ✅ {product_name} - UNCHANGED: {final_score} (High-risk additives, already ≤49)", log_file)
                        else:
                            unchanged_count += 1
                            log_and_print(f"  {i:3d}. ✅ {product_name} - UNCHANGED: {final_score} (No high-risk additives)", log_file)
                    
                    # Small delay to avoid overwhelming the database
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    log_and_print(f"  {i:3d}. ❌ Exception updating {product_name}: {e}", log_file)
                    error_count += 1
                    
            except Exception as e:
                log_and_print(f"  {i:3d}. ❌ Exception processing {product_name}: {e}", log_file)
                error_count += 1
        
        # Print summary
        log_and_print(f"\n{'='*60}", log_file)
        log_and_print("SUMMARY", log_file)
        log_and_print(f"{'='*60}", log_file)
        log_and_print(f"Total products processed: {len(products)}", log_file)
        log_and_print(f"Successfully updated: {updated_count}", log_file)
        log_and_print(f"Products with capped scores (high-risk additives): {capped_count}", log_file)
        log_and_print(f"Products with unchanged scores: {unchanged_count}", log_file)
        log_and_print(f"Errors: {error_count}", log_file)
        log_and_print(f"Log file: {log_filename}", log_file)

def main():
    """Main function to run the display score update."""
    print("Starting display score update...")
    update_display_scores()
    print("Display score update completed!")

if __name__ == "__main__":
    main()
