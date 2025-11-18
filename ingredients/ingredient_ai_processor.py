#!/usr/bin/env python3
"""
Ingredient AI processor for validating and enriching candidate ingredients before database insertion.

This module centralizes the logic for:
- Verifying that a candidate string represents a real ingredient
- Obtaining an English translation for the ingredient name
- Generating short multilingual descriptions
- Requesting optional risk level and NOVA score classifications

The processor is designed to be reusable by different ingestion flows so the validation/enrichment
logic stays in one place. If a future parser wants to re-process existing records, it can instantiate
this processor and call `process_ingredient` for each candidate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI  # type: ignore[import]

load_dotenv()


@dataclass
class IngredientAIResult:
    """Container for AI-derived ingredient metadata."""

    input_name: str
    is_ingredient: bool
    name: Optional[str]
    ro_name: Optional[str]
    description: Optional[str]
    ro_description: Optional[str]
    risk_level: Optional[str]
    nova_score: Optional[int]
    confidence: Optional[float]
    reason: Optional[str]
    raw_payload: Optional[Dict[str, Any]]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_name": self.input_name,
            "is_ingredient": self.is_ingredient,
            "name": self.name,
            "ro_name": self.ro_name,
            "description": self.description,
            "ro_description": self.ro_description,
            "risk_level": self.risk_level,
            "nova_score": self.nova_score,
            "confidence": self.confidence,
            "reason": self.reason,
            "raw_payload": self.raw_payload,
            "error": self.error,
        }


class IngredientAIProcessor:
    """Facade around OpenAI for ingredient validation and enrichment."""

    VALID_RISK_LEVELS = {
        "free": "free",
        "low": "low",
        "moderate": "moderate",
        "high": "high",
    }

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tokens: int = 600,
        temperature: float = 0.2,
        client: Optional[OpenAI] = None,
    ):
        """
        Args:
            model: OpenAI model to use for enrichment prompts.
            max_tokens: Maximum tokens to allow in responses.
            temperature: Sampling temperature for the completion.
            client: Optional preconfigured OpenAI client (primarily for testing).
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if client is None:
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set.")
            client = OpenAI(api_key=api_key)

        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def process_ingredient(
        self,
        ingredient_name: str,
        *,
        context: Optional[str] = None,
        source_language: str = "ro",
    ) -> IngredientAIResult:
        """
        Validate and enrich an ingredient candidate.

        Args:
            ingredient_name: Candidate ingredient string (typically Romanian).
            context: Optional text that helps the AI understand the ingredient (e.g., product info).
            source_language: Expected language of the candidate (default Romanian).

        Returns:
            IngredientAIResult with structured AI guidance.
        """
        if not ingredient_name or not ingredient_name.strip():
            return IngredientAIResult(
                input_name=ingredient_name,
                is_ingredient=False,
                name=None,
                ro_name=None,
                description=None,
                ro_description=None,
                risk_level=None,
                nova_score=None,
                confidence=None,
                reason="Empty ingredient name",
                raw_payload=None,
                error="missing_input",
            )

        prompt = self._build_prompt(ingredient_name.strip(), context=context, source_language=source_language)
        raw_response = self._make_request(prompt)

        if raw_response is None:
            return IngredientAIResult(
                input_name=ingredient_name,
                is_ingredient=False,
                name=None,
                ro_name=None,
                description=None,
                ro_description=None,
                risk_level=None,
                nova_score=None,
                confidence=None,
                reason="AI request failed",
                raw_payload=None,
                error="request_failed",
            )

        parsed_payload = self._parse_response(raw_response)
        if parsed_payload is None:
            return IngredientAIResult(
                input_name=ingredient_name,
                is_ingredient=False,
                name=None,
                ro_name=None,
                description=None,
                ro_description=None,
                risk_level=None,
                nova_score=None,
                confidence=None,
                reason="Unable to parse AI response",
                raw_payload=None,
                error="parse_failed",
            )

        normalized = self._normalize_payload(parsed_payload, fallback_ro=ingredient_name.strip())

        return IngredientAIResult(
            input_name=ingredient_name,
            is_ingredient=normalized["is_ingredient"],
            name=normalized["name"],
            ro_name=normalized["ro_name"],
            description=normalized["description"],
            ro_description=normalized["ro_description"],
            risk_level=normalized["risk_level"],
            nova_score=normalized["nova_score"],
            confidence=normalized["confidence"],
            reason=normalized["reason"],
            raw_payload=parsed_payload,
            error=None,
        )

    def process_batch(
        self,
        ingredients: List[str],
        *,
        context: Optional[str] = None,
        source_language: str = "ro",
    ) -> List[IngredientAIResult]:
        """
        Convenience helper to process several ingredients sequentially.
        """
        results: List[IngredientAIResult] = []
        for ing in ingredients:
            result = self.process_ingredient(ing, context=context, source_language=source_language)
            results.append(result)
        return results

    def _build_prompt(self, ingredient_name: str, *, context: Optional[str], source_language: str) -> str:
        context_block = f"\nContext: {context.strip()}" if context else ""
        return f"""You are an experienced food scientist helping curate a structured ingredients database.

Candidate ingredient (language: {source_language}): {ingredient_name}{context_block}

Tasks:
1. Decide if the candidate is a real edible ingredient or approved food additive. If it is not, set `is_ingredient` to false and explain why in `reason`.
2. If it is an ingredient, translate the ingredient name to English (keep it concise) and output it in the `name` field.
3. Provide the Romanian name in the `ro_name` field (keep original wording if already Romanian).
4. Provide a short English description (max 2 sentences) and a short Romanian description (max 2 sentences).
5. Suggest the NOVA score (1-4) if you are confident; otherwise set it to null.
6. Suggest the ingredient's risk level using ONLY one of these values when you are confident: "free", "low", "moderate", "high". If you are uncertain, set it to null.

⭐ HOW PURIO DEFINES RISK LEVEL

Risk is assigned to the ingredient itself, not to the food category. Risk levels are based on:
- level of processing
- presence of additives
- scientific evidence of harm
- nutritional quality
- how commonly the ingredient appears in ultra-processed products

✅ FREE RISK (0) - "free"
Definition: Natural, minimally processed ingredients with no known harmful effects.
Examples: herbs & spices (oregano, parsley, dill), fresh fruits & vegetables, nuts & seeds, natural fibers (acacia fiber), teas, natural extracts without additives.
Why: No processing, no additives, no known health risks.

🟢 LOW RISK (1) - "low"
Definition: Ingredients that are processed minimally, or naturally derived but concentrated.
Examples: cocoa powder (non-alkalized, defatted), vanilla extract, dried vegetables, natural oils (olive, sunflower, coconut), natural stabilizers (pectin, guar gum).
Why: Still natural, but sometimes processed or used in higher doses.

🟡 MODERATE RISK (2) - "moderate"
Definition: Processed ingredients, extracted components, or ingredients commonly found in processed foods, but not clearly harmful.
Examples: isolate proteins (soy isolate, pea protein), whey protein, sugar alcohols (trehalose, mannitol), hydrolyzed proteins, palm oil, some sweeteners (stevia extract).
Why: Moderate processing, often used in UPFs, but no strong evidence of direct harm.

🔴 HIGH RISK (3) - "high"
Definition: Ingredients linked to negative health effects or strongly associated with ultra-processed foods.
Examples: artificial flavors, artificial sweeteners (acesulfame-K, sucralose), emulsifiers linked to gut issues (polysorbates, carrageenan), processed meat products (salami, pepperoni), glazes, coatings, industrial chocolate toppings.
Why: Heavily processed, often harmful, common in UPFs.

⭐ NOVA SCORE — measures degree of processing (NOT health, completely independent from risk_level):

• NOVA 1: Unprocessed or minimally processed foods (e.g., fruits, vegetables, nuts, herbs, eggs, meat, fresh milk)
• NOVA 2: Processed culinary ingredients (e.g., oils, flour, sugar, starches, tomato paste, butter, salt)
• NOVA 3: Processed foods (simple combinations of ingredients such as cheese, bread, bacon, canned foods, smoked fish)
• NOVA 4: Ultra-processed ingredients or additives (e.g., emulsifiers, colorants, sweeteners, stabilizers, protein isolates, hydrolyzed proteins, modified starches)

CRITICAL: NOVA score measures PROCESSING LEVEL. Risk level measures HEALTH IMPACT. They are completely independent scales. A NOVA 4 ingredient can be "low" risk if it's safe, and a NOVA 1 ingredient can be "high" risk if it has known health concerns.

⭐ HOW PURIO DECIDES INGREDIENT vs PRODUCT vs CATEGORY

This is extremely important for database cleanliness. Use these three simple rules:

✔️ INGREDIENT: "Can this appear EXACTLY like this on an ingredient label?"
If YES → it is an ingredient.
Examples that ARE ingredients: "dried tomatoes", "black pepper", "sunflower seed oil", "grape juice", "hydrolyzed vegetable protein", "soy fiber", "hazelnut pieces", "whey powder"
Characteristics: specific substance, commonly used in food manufacturing, not a final product, can be listed as a component inside another product.

❌ PRODUCT: "Is this already a finished food that people buy and eat as-is?"
If YES → it is NOT an ingredient.
Examples (NOT ingredients): "bread", "pepperoni", "tofu", "apricot jam", "pickled cucumbers", "yogurt", "pale lager", "chocolate sauce"
Why not: These are products, not ingredient substances. They contain their own ingredient list and cannot appear as a single-line ingredient.

❌ CATEGORY / NON-SPECIFIC TERM: "Is this too vague to appear as a real ingredient?"
If YES → it is NOT an ingredient.
Examples: "wild berry", "tea flower", "semi-skimmed" (incomplete), "cereal flakes", "fruit puree" (must specify fruit)
Why: Labels require specificity (regulations). Manufacturers cannot legally list vague or generic categories.
Example: ❌ "fruit puree" → ✔️ "apple puree", "banana puree", "mango puree"

⭐ PURIO CLASSIFICATION RULES (Simple & Strict):

Rule 1 — If it cannot appear EXACTLY like this on an ingredient label → NOT an ingredient
Rule 2 — If it's a finished product → NOT an ingredient
Rule 3 — If it's a mixture or preparation → NOT an ingredient
Rule 4 — If it represents a category, not a specific component → NOT an ingredient
Rule 5 — Ingredients must be SINGLE SUBSTANCES (even if processed — OK, as long as they're a single component)

Summary: An ingredient is a single, specific substance that can legally appear exactly as written on an ingredient list. A product is a combination of ingredients. A category is a generic term that does not meet labeling regulations.

DO NOT create ingredients for the following generic categories, mixtures, processing roles, additives, or placeholders. If the candidate matches any of these, set `is_ingredient` to false and provide a brief `reason`:
- organs; seafood; fish roe; fruit mix; vanilla-flavored cream; carob gum; Roshen biscuits; invert sugar; palmier; humectant; spice extract; gum arabic; capsicum extract; proteins from; plant broth; peanut filling; Red 17; dextrin; sorbitol syrup; sponge cake; animal protein; whipped cream; carmine; Beetroot Red; emulsifiers; vanilla pasta; animal proteins; spice extracts; wafers; smoke flavor; thickeners; vegetable fats; dehydrated vegetables; Brilliant Blue FCF; tomato pasta; peel; pork cracklings; liver; whipped cream powder; protein from; vegetable fiber.
- compound salt/acid salts when only roles are specified (e.g., sodium polyphosphates, diphosphates, potassium citrates, sodium acetate, potassium chloride, calcium carbonate, calcium lactate, sodium lactate, sodium erythorbate, ammonium bicarbonate).
- named extracts/colors/flavors used as roles without a specific food identity (e.g., anthocyanin, curcumin, carotene, beta-carotene, processed Eucheuma seaweed).
- additives in general (roles such as emulsifier, stabilizer, colorant, sweetener, preservative, flavoring, raising agent), including E-number additives (e.g., E100–E999). These should NOT be created as standalone ingredients; mark `is_ingredient` = false and give reason "additive".

Respond with a single JSON object using this schema and NO extra text:
{{
  "is_ingredient": boolean,
  "reason": string or null,
  "name": string or null,
  "ro_name": string or null,
  "description": string or null,
  "ro_description": string or null,
  "risk_level": "free" | "low" | "moderate" | "high" | null,
  "nova_score": 1 | 2 | 3 | 4 | null,
  "confidence": number between 0 and 1 or null
}}

If the item is not an ingredient, still include a brief reason and set the other fields to null."""

    def _make_request(self, prompt: str) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a meticulous food scientist. Always return STRICT JSON with the exact schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print(f"   ❌ IngredientAIProcessor request error: {exc}")
            return None

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        try:
            data: Dict[str, Any] = json.loads(cleaned)
            return data
        except json.JSONDecodeError:
            print(f"   ⚠️ Unable to decode AI response as JSON: {cleaned[:120]}...")
            return None

    def _normalize_payload(self, payload: Dict[str, Any], *, fallback_ro: str) -> Dict[str, Any]:
        def _normalize_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "yes", "1"}
            return False

        def _normalize_str(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, str):
                stripped = value.strip()
                return stripped or None
            return None

        def _normalize_risk(value: Any) -> Optional[str]:
            text = _normalize_str(value)
            if not text:
                return None
            key = text.lower()
            return self.VALID_RISK_LEVELS.get(key)

        def _normalize_nova(value: Any) -> Optional[int]:
            if isinstance(value, int):
                return value if 1 <= value <= 4 else None
            if isinstance(value, str) and value.strip().isdigit():
                int_val = int(value.strip())
                return int_val if 1 <= int_val <= 4 else None
            return None

        def _normalize_confidence(value: Any) -> Optional[float]:
            if isinstance(value, (int, float)):
                return max(0.0, min(1.0, float(value)))
            if isinstance(value, str):
                try:
                    parsed = float(value)
                    return max(0.0, min(1.0, parsed))
                except ValueError:
                    return None
            return None

        normalized_payload = {
            "is_ingredient": _normalize_bool(payload.get("is_ingredient")),
            "name": _normalize_str(payload.get("name")),
            "ro_name": _normalize_str(payload.get("ro_name")) or fallback_ro,
            "description": _normalize_str(payload.get("description")),
            "ro_description": _normalize_str(payload.get("ro_description")),
            "risk_level": _normalize_risk(payload.get("risk_level")),
            "nova_score": _normalize_nova(payload.get("nova_score")),
            "confidence": _normalize_confidence(payload.get("confidence")),
            "reason": _normalize_str(payload.get("reason")),
        }

        if not normalized_payload["is_ingredient"]:
            normalized_payload["name"] = None
            normalized_payload["description"] = None
            normalized_payload["ro_description"] = None
            normalized_payload["risk_level"] = None
            normalized_payload["nova_score"] = None
            normalized_payload["ro_name"] = fallback_ro

        return normalized_payload


