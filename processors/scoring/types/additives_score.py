import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

class AdditivesScoreCalculator:
    def __init__(self):
        """Initialize the additives score calculator with database connection."""
        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Risk level scoring
        self.risk_scores = {
            'Free risk': 100,
            'Low risk': 75,
            'Moderate risk': 50,
            'High risk': 0,
        }
    
    def get_additive_risk_score(self, additive: Dict[str, Any]) -> int:
        risk_level = additive.get('risk_level')
        score = self.risk_scores.get(risk_level)

        if score is None:
            raise ValueError(f"Unknown risk level: {risk_level}")
        return score
    
    
    def calculate_from_product_additives(self, product_id: str) -> Dict[str, Any]:
        """
        Calculate additives score by querying product_additives table.
        Skip products with any additives that have "Unknown" risk level.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with score and details, or None if any additive has unknown risk
        """
        try:
            # Query product_additives table with join to additives
            result = self.supabase.table('product_additives').select(
                'additive_id, additives!inner(*)'
            ).eq('product_id', product_id).execute()
            
            if hasattr(result, 'error') and result.error:
                print(f"Error querying product additives: {result.error}")
                return None
            
            additives = result.data
            if not additives:
                return {'score': 100, 'additives_found': 0, 'high_risk_additives': [], 'risk_breakdown': {'free': 0, 'low': 0, 'moderate': 0, 'high': 0}}
            
            additives_found = 0
            high_risk_additives = []
            risk_breakdown = {'free': 0, 'low': 0, 'moderate': 0, 'high': 0}
            total_score = 0
            
            # Process additives for scoring, skipping additives with unknown risk
            skipped_unknown_risk = []
            for relation in additives:
                additive = relation.get('additives', {})
                if additive:
                    risk_level = additive.get('risk_level')
                    if risk_level is None or risk_level == '':
                        skipped_unknown_risk.append(additive.get('code'))
                        continue
                    
                    additives_found += 1
                    risk_score = self.get_additive_risk_score(additive)
                    total_score += risk_score
                    
                    # Track risk breakdown
                    if risk_level == 'Free risk':
                        risk_breakdown['free'] += 1
                    elif risk_level == 'Low risk':
                        risk_breakdown['low'] += 1
                    elif risk_level == 'Moderate risk':
                        risk_breakdown['moderate'] += 1
                    elif risk_level == 'High risk':
                        risk_breakdown['high'] += 1
                        high_risk_additives.append({
                            'code': additive.get('code'),
                            'name': additive.get('name'),
                            'risk_level': risk_level
                        })
            
            # Calculate average score
            if additives_found > 0:
                final_score = total_score / additives_found
            else:
                final_score = 100
            
            # Apply high-risk cap: if any high-risk additives, cap at 49
            if high_risk_additives:
                final_score = min(final_score, 49)
            
            if skipped_unknown_risk:
                printable_codes = [code for code in skipped_unknown_risk if code]
                if printable_codes:
                    print(f"⚠️  Skipped additives with unknown risk level: {', '.join(printable_codes)}")
            
            return {
                'score': int(final_score),
                'additives_found': additives_found,
                'high_risk_additives': high_risk_additives,
                'risk_breakdown': risk_breakdown,
                'skipped_unknown_risk': skipped_unknown_risk
            }
            
        except Exception as e:
            print(f"Error calculating additives score from database: {e}")
            return None
    
    def calculate(self, product_data: Dict[str, Any]) -> Optional[int]:
        """
        Calculate additives score for a product using only product_additives table.
        Returns None if any additive has unknown risk level.
        
        Args:
            product_data: Product data dictionary
            
        Returns:
            Additives score (0-100) or None if skipped due to unknown risk levels
        """
        # Get additives from product_additives table
        product_id = product_data.get('id')
        if product_id:
            result = self.calculate_from_product_additives(product_id)
            if result is None:
                return None  # Product skipped due to unknown risk levels
            return result['score']
        
        # If no product_id, return None (cannot calculate)
        print(f"Warning: No product_id found for product. Cannot calculate additives score.")
        return None