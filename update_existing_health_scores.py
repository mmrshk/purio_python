#!/usr/bin/env python3
"""
Script to update existing products in Supabase with health scores.
This script can be run independently to add health scores to products that were already in the database.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the processors directory to the path
sys.path.append(str(Path(__file__).parent / "processors" / "helpers"))
from health_scorer import update_supabase_health_scores

def main():
    """Main function to update health scores in Supabase."""
    print("=== Updating Health Scores in Supabase ===")
    print("This will calculate and update health scores for all existing products.")
    
    # Load environment variables
    load_dotenv()
    
    # Check if required environment variables are set
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set")
        print("Please check your .env file")
        return
    
    # Confirm before proceeding
    response = input("\nThis will update all products in the database. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return
    
    try:
        update_supabase_health_scores()
        print("\n=== Health Score Update Complete ===")
    except Exception as e:
        print(f"Error updating health scores: {str(e)}")

if __name__ == "__main__":
    main() 