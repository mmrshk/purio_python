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
    'stabilizator', 'stabilizatori', 'stabilizers', 'stabilizer',
    'acidifianti', 'acidity regulators', 'acidity regulator',
    'deacidification agent', 'decaffeination agent',
    'antioxidant', 'antioxidants',
    'sweeteners', 'sweetener',
    'flavorings', 'flavoring', 'aroma', 'arome', 'gust fin',
    'gust natural', 'gust echilibrat',
    'smoke flavoring',
    'blend', 'blend special', 'mix', 'seafood', 'seafood mix',
    'atmosfera protectoare',

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
    'tchibo exclusive medium roast',

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
    'burta de vita', 'burtă de vită', 'gat de vita', 'gât de vită',
    'carne vita 100% romaneasca',
    'ficat de rata', 'inimi',
    'pipote',
    'ciocolata alba', 'white chocolate', 'ciocolata', 'ruby chocolate', 'giandu',
    'triticale',
    'afine',
    'pipote de rata', 'pipote de rață',
    'roinita',
    'maghiran',
    'passiflora',
    "st. john's wort aerial parts", "st john's wort aerial parts",
    'musculatura', 'spinari', 'spinări', 'aripi', 'aripioare', 'copanele', 'copănele', 'ciocanele', 'ciocănele',
    'din ue', 'din u.e.',
    'piele', 'skin',
    'folie termosudata', 'folie termosudată',
    'asian ginseng root', 'ginseng root',
    'rata',
    'rata afumata', 'rata afumată', 'smoked duck',
    'manzat', 'snitel de manzat', 'șnițel de mânzat',
    'vita', 'burta de vita',
    'muschi maturat de vita', 'muşchi maturat de vită', 'muschiu maturat de vita', 'aged beef loin',
    'grau',
    'menta nana',
    'arahide prajite',
    'fried seaweed',
    'femur',
    'os',
    'sticla', 'sticlă',
    'jambon',
    'nalba',
    'smarties white',
    'smarties',
    'pulpă de căpșuni', 'pulpa de capsuni',
    'valoare energetica', 'valoare energetică',
    'aditivi',
    'mezire',
    'ulei',
    'president beurre tendre',
    'eticheta de calitate ecologica', 'eticheta de calitate ecologică',
    'algae',
    'substante nutritive', 'substanțe nutritive',
    'macinate', 'măcinate',
    'pedra',
    'intensitate',
    'regiuni agricole',
    'puiul fermierului agricola',
    'crema de vanilie', 'cremă de vanilie',
    'pasta', 'pastă',
    'pulpa', 'pulpă',
    'cola',
    'caserola', 'caserolă',
    'austria bio',
    'tartinabil', 'tartinabilă',
    'fructe', 'fructe cu coaja', 'fructe cu coajă',
    'multicolor',
    'carnati', 'cârnați',
    'gama ecologica', 'gamă ecologică',
    'bio',
    'somonat',
    'slănină', 'slanina',
    'alfredo', 'alfredo sauce',
    'corsicane', 'corsicana', 'corsicană',
    'timp 11 luni', 'timp de 11 luni',
    'maturat 11 luni', 'maturat 12 luni',
    'a de piersici', 'a de piersic', 'a de piersică',
    'a de fructe',
    'regulator de aciditate', 'regulator aciditate', 'acidity regulator', 'acid regulator',
    'culori din natura', 'culori din natură',
    'tchibo privat kaffee brazil mild', 'tchibo privat caffe brazil mild',
    '4 foi / 25 sushi',
    'vopsit', 'vopsita', 'vopsită',
    'marcata de un gust', 'marcata de un gust aparte', 'marcată de un gust', 'marcată de un gust aparte',
    'aer si soare', 'aer și soare',
    'jambon crud', 'jambon crud uscat', 'jambon uscat',
    'o delicatese speciala', 'o delicatese specială', 'delicatese speciala', 'delicatese specială',
    'delicatesa speciala', 'delicatesa specială', 'delicatesă specială', 'delicatesă speciala',
    'smoothie', 'smoothie mix', 'smoothie bowl',
    'da o nota distincta', 'dă o notă distinctă',
    'productia sa tinand cont de cele trei principii importante: sare',
    'inspectii regulate', 'inspecții regulate',
    'tehnologie unica de crestere', 'tehnologie unică de creștere',
    'incalzire', 'încălzire',
    'picante',
    'a naturala de cola',
    'a natural', 'a naturala', 'a naturală',
    'a de ciocolata', 'a de ciocolată',
    'a de capsuni', 'a de căpșuni',
    'prajire', 'prăjire', 'prajire tipic vieneza', 'prăjire tipic vieneza', 'prajire tipic vieneză', 'prăjire tipic vieneză',
    'norme reglementate',
    'seara', 'seară',
    'cultivate in mod natural', 'cultivate în mod natural',
    'regiunea dorsolombosacrala', 'regiunea dorso-lombosacrală',
    'certificat ecologic',
    'ate',
    'nesarat', 'nesărat',
    'vietnam',
    'melasa', 'melasă',
    'ngroșare', 'ingrosare', 'îngroșare',

    # Nutritional information labels
    'alte valori nutritionale', 'valori nutritionale', 'nutritional values',
    'alte valori',
    'alte valori nutritionale: fosfor: 315mg/100g',

    # Allergen warnings
    'oua', 'ou', 'eggs',

    # Other non-ingredients
    'coffee', 'tea', 'ceai',

    # User-provided non-ingredients / categories / mixtures to never create as standalone ingredients
    'organs',
    'seafood',
    'sodium polyphosphates',
    'propylene glycol',
    'anthocyanin',
    'fish roe',
    'fruit mix',
    'vanilla-flavored cream',
    'carob gum',
    'calcium carbonate',
    'roshen biscuits',
    'diphosphates',
    'invert sugar',
    'palmier',
    'processed eucheuma seaweed',
    'humectant',
    'curcumin',
    'polyglycerol esters of fatty acids',
    'sodium acetate',
    'spice extract',
    'gum arabic',
    'capsicum extract',
    'acetic acid esters',
    'proteins from',
    'carotene',
    'beta-carotene',
    'potassium citrates',
    'leavening agents',
    'ammonium bicarbonate',
    'plant broth',
    'peanut filling',
    'red 17',
    'dextrin',
    'sodium lactate',
    'sorbitol syrup',
    'sponge cake',
    'potassium chloride',
    'calcium lactate',
    'animal protein',
    'whipped cream',
    'carmine',
    'beetroot red',
    'emulsifiers',
    'vanilla pasta',
    'animal proteins',
    'spice extracts',
    'wafers',
    'sodium erythorbate',
    'smoke flavor',
    'thickeners',
    'vegetable fats',
    'dehydrated vegetables',
    'brilliant blue fcf',
    'tomato pasta',
    'peel',
    'pork cracklings',
    'liver',
    'whipped cream powder',
    'protein from',
    'vegetable fiber',
    'pandispan', 'pandișpan',
    'biscuits', 'biscuiti',
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
    r'^timp\s+\d+',
    r'^maturat',
    r'^maturare',
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
    r'^regulator',
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
    r'^\d+\s+foi',
    r'^wine$',
    r'^vin$',
    r'^water$',
    r'^oua$',
    r'^ou$',
    r'^rata$',
    r'^vita$',
    r'^manzat$',
    r'.*\bproteins?\s+from\b',
    r'.*\bprotein\s+from\b',
]

# Invalid phrases that indicate non-ingredients (substring matching)
INVALID_PHRASES = [
    'contine', 'nu contine', 'poate contine',
    'produs', 'origine', 'tara de',
    'obtinut', 'purificat', 'concentrat',
    'culoarea', 'nuante', 'continut',
    'in special', 'valori nutritionale',
    'delicatese', 'delicatesa',
    'corsicane',
    'timp', 'maturat',
    'aer si soare', 'aer și soare',
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

