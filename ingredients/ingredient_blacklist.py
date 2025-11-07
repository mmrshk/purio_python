#!/usr/bin/env python3
"""
Blacklist of non-ingredient terms that should never be created as ingredients.

This module contains:
1. A set of exact blacklist terms
2. A list of regex patterns for matching blacklisted terms
3. A list of invalid phrases that indicate non-ingredients
"""

# Exact blacklist terms (case-insensitive matching will be used)
# This list contains terms that should never be created as ingredients
BLACKLIST_TERMS = {
    # Process descriptions
    'prajita', 'prajite', 'praji', 'fried', 'pasteurizat', 'pasteurize',
    'obtinut', 'obtinute', 'presare', 'presat', 'presate',
    'concentrat', 'concentrate', 'concentrated',
    'purificat', 'purificata', 'purified', 'purificata prin osmoza inversa',
    'obtinut din', 'obtinut prin', 'nu este obtinut din',
    
    # Product descriptions and labels
    'nu contine alergeni', 'poate contine urme de', 'poate contine urme',
    'poate contine urme de ou',
    'produs in', 'produs pasteurizat', 'produs in ue',
    'origine din', 'origine din ue si din afara ue',
    'tara de provenienta', 'tara de provenienta a ingredientului principal',
    'tara de provenienta a ingredientului principal: china',
    'in special a', 'in special',
    'in special a florilor de hibiscus si a fructelor de maces',
    'nuante', 'nuante de', 'culoarea', 'culoarea rosie', 'culoarea naturala',
    'culoarea rosie a ceaiului', 'culoarea naturala a ingredientelor sale',
    'continut de fructe', 'continut',
    
    # Packaging and non-food materials
    'hartie', 'paie', 'plase', 'packaging', 'ambalaj',
    
    # Generic categories (too broad)
    'cereale', 'cereale integrale', 'legume', 'minerale', 'minerals', 'vitamine',
    'vitamin e', 'vitamin', 'vitamins',
    'fructe cu coaja lemnoasa',  # Too generic, should be specific fruits
    
    # Minerals (when extracted from nutritional info, not ingredient lists)
    'magneziu', 'magnesium', 'zinc', 'fier', 'iron', 'fosfor', 'phosphorus',
    '9mg',  # Quantity-only
    
    # Additives (generic terms, not specific E-codes)
    'coloranti', 'colorants', 'colorant', 'vopsea', 'vopsele',
    'emulsifiant', 'emulsifianti', 'emulsifiers',
    'agent de ingrosare', 'agent de umezare', 'agent',
    'foaming agent', 'foaming agent: nitrogen',
    'corector de aciditate', 'corector',
    'conservant', 'conservanti', 'preservatives', 'preservative', 'nitrogen',
    
    # Preparation methods
    'tulbure natural obtinut prin presare la rece',
    'tulbure', 'tulbure natural',
    
    # Water (too generic, should be specific like "mineral water")
    'apa', 'apa potabila', 'apa potabila purificata prin osmoza inversa',
    'water',
    
    # Wine/alcohol (too generic)
    'wine', 'vin',
    
    # Coffee bean types (should be just "coffee" or "coffee beans")
    'boabe robusta', 'boabe arabica', 'boabe prajite',
    'robusta', 'arabica', 'coffee beans', 'robusta coffee beans',
    
    # Compound descriptions that need extraction
    'flori de tei', 'flori de hibiscus', 'flori de musetel',
    'flori de lavanda', 'flori din soc',
    'frunze si flori de paducel', 'frunze de paducel',
    'rosemary leaves',
    'radacina de lemn dulce', 'liquiritiae radix',
    'sambuci flos', 'hibisci flos',
    'ierburi de provence',
    'crupe de ovaz', 'fulgi de ovaz',
    'faina integrala de grau', 'faina integrala de secara',
    'faina de grau', 'faina',
    'grƒÉsime vegetalƒÉ de palmier', 'grasime vegetala de palmier',
    'grfésime vegetalfé de palmier',  # Encoding variant
    'nectar de piersici', 'nectar',
    'suc de mandarine', 'suc',
    'multifruit concentrate',
    'pulpa de vita', 'carnea de vita', 'carne vita',
    'carne vita 100% romaneasca',
    'ficat de rata', 'inimi',
    'ciocolata alba', 'white chocolate', 'ciocolata', 'ruby chocolate', 'giandu',
    'triticale',
    'afine',
    'pipote',
    'roinita',
    'maghiran',
    'passiflora',
    'asian ginseng root', 'ginseng root',
    'rata',
    'manzat',
    'vita',
    'grau',
    'menta nana',
    'arahide prajite',
    'fried seaweed',
    
    # Nutritional information labels
    'alte valori nutritionale', 'valori nutritionale', 'nutritional values',
    'alte valori',
    'alte valori nutritionale: fosfor: 315mg/100g',
    
    # Allergen warnings
    'oua', 'ou', 'eggs',
    
    # Other non-ingredients
    'coffee', 'tea', 'ceai',
}

# Regex patterns that indicate non-ingredients
BLACKLIST_PATTERNS = [
    r'^poate contine',
    r'^nu contine',
    r'^produs in',
    r'^origine',
    r'^tara de',
    r'^in special',
    r'^culoarea',
    r'^continut de',
    r'^obtinut',
    r'^purificat',
    r'^concentrat',
    r'^presare',
    r'^pasteurizat',
    r'^prajit',
    r'^flori de',
    r'^frunze',
    r'^radacina de',
    r'^boabe',
    r'^crupe de',
    r'^fulgi de',
    r'^faina',
    r'^grasime',
    r'^nectar de',
    r'^suc de',
    r'^pulpa de',
    r'^pasta de',
    r'^carnea de',
    r'^carne',
    r'^ficat de',
    r'^ciocolata',
    r'^agent de',
    r'^corector de',
    r'^vitamin',
    r'^minerale',
    r'^cereale',
    r'^legume',
    r'^colorant',
    r'^emulsifiant',
    r'^conservant',
    r'^preservativ',
    r'^vopsea',
    r'^hartie',
    r'^paie',
    r'^plase',
    r'^apa potabila',
    r'^wine$',
    r'^vin$',
    r'^water$',
    r'^oua$',
    r'^ou$',
    r'^rata$',
    r'^vita$',
    r'^manzat$',
]

# Invalid phrases that indicate non-ingredients (substring matching)
INVALID_PHRASES = [
    'contine', 'nu contine', 'poate contine',
    'produs', 'origine', 'tara de',
    'obtinut', 'purificat', 'concentrat',
    'culoarea', 'nuante', 'continut',
    'in special', 'valori nutritionale',
]


def is_blacklisted(ingredient: str) -> bool:
    """
    Check if an ingredient is blacklisted (exact match or pattern match).
    
    Args:
        ingredient: Ingredient name to check
        
    Returns:
        True if the ingredient is blacklisted, False otherwise
    """
    if not ingredient:
        return True
    
    ingredient_lower = ingredient.lower().strip()
    
    # Check exact blacklist match
    if ingredient_lower in BLACKLIST_TERMS:
        return True
    
    # Check blacklist patterns
    import re
    for pattern in BLACKLIST_PATTERNS:
        if re.match(pattern, ingredient_lower, re.IGNORECASE):
            return True
    
    # Check invalid phrases
    for phrase in INVALID_PHRASES:
        if phrase in ingredient_lower:
            return True
    
    return False


def get_blacklist() -> dict:
    """
    Get the blacklist data structure for backward compatibility.
    
    Returns:
        Dictionary with 'terms', 'patterns', and 'phrases' keys
    """
    return {
        'terms': BLACKLIST_TERMS,
        'patterns': BLACKLIST_PATTERNS,
        'phrases': INVALID_PHRASES,
    }

