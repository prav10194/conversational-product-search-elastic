"""Step 1 of every search: turn the shopper's sentence into a structured plan.

This is the job an NLU service (e.g. Watson) did in the original pattern: intent + entities. Here Claude does it,
returning JSON that matches the QueryPlan model below. If there is no API key,
a small rule-based parser does the same job less well, so the app still works.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app import config

DIET_TAGS = ["gluten-free", "vegan", "vegetarian", "organic", "dairy-free", "keto",
             "low-sodium", "nut-free", "high-protein", "sugar-free"]
CATEGORIES = ["pasta", "sauces", "dairy", "snacks", "breakfast", "frozen", "bakery", "produce",
              "beverages", "rice & grains", "meat & seafood", "plant protein"]
BRANDS = ["Harvest Lane", "Golden Field", "Pure Pantry", "Green Valley", "Ocean Bay", "Sunny Acres",
          "Morning Mill", "Nonna's Table", "Simply Fresh", "Peak Nutrition"]


class QueryPlan(BaseModel):
    intent: Literal["find_product", "store_info", "other"] = Field(
        description="find_product for anything about products; store_info for hours/location; other for chit-chat")
    search_text: str = Field(description="Words to search product names and descriptions with. "
                                         "No prices, diets or brands here; empty string if none.")
    diet_tags: list[str] = Field(default_factory=list, description="Only values from the allowed diet list")
    category: Optional[str] = Field(default=None, description="One allowed category, only if clearly implied")
    brand: Optional[str] = Field(default=None, description="One allowed brand, only if named")
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    in_stock_only: bool = Field(default=True, description="False only if the shopper says stock doesn't matter")


SYSTEM_PROMPT = f"""You turn grocery shoppers' messages into a search plan for a product catalog.
Allowed diet tags: {", ".join(DIET_TAGS)}.
Allowed categories: {", ".join(CATEGORIES)}.
Allowed brands: {", ".join(BRANDS)}.
Rules:
- Put hard constraints (diet, price, brand, category) in their fields, not in search_text.
- Map synonyms: "no gluten"/"celiac" -> gluten-free, "plant-based" -> vegan, "lactose free" -> dairy-free,
  "under $5"/"less than 5 dollars" -> max_price 5.
- Only use values from the allowed lists. If nothing fits, leave the field empty.
- search_text keeps the product words, e.g. "pasta", "greek yogurt", "snack for kids"."""


def understand(message: str) -> tuple[QueryPlan, str, list[str]]:
    """Returns (plan, source, trace). source is 'claude' or 'rules'; trace explains each step in plain words."""
    if config.ANTHROPIC_API_KEY:
        try:
            plan, trace = _with_claude(message)
            return plan, "claude", trace
        except Exception as exc:  # network, quota, bad key: fall back rather than fail the search
            print(f"Claude call failed, using rules: {exc}")
            trace = [f"Claude call failed ({type(exc).__name__}), falling back to rules"]
            plan = rule_based(message, trace)
            return plan, "rules", trace
    trace = ["No ANTHROPIC_API_KEY set, so the built-in rules parse the sentence"]
    return rule_based(message, trace), "rules", trace


def _with_claude(message: str) -> tuple[QueryPlan, list[str]]:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
        output_format=QueryPlan,
    )
    trace = [f"Sent the sentence to {config.CLAUDE_MODEL} with the catalog vocabulary in the system prompt",
             "Claude returned JSON matching the QueryPlan schema (structured output)"]
    return clean(response.parsed_output, trace), trace


def clean(plan: QueryPlan, trace: list | None = None) -> QueryPlan:
    """Never trust model output blindly: drop any value that isn't in the catalog vocabulary."""
    trace = trace if trace is not None else []
    bad = [t for t in plan.diet_tags if t not in DIET_TAGS]
    plan.diet_tags = [t for t in plan.diet_tags if t in DIET_TAGS]
    if plan.category not in CATEGORIES and plan.category is not None:
        bad.append(plan.category)
        plan.category = None
    if plan.brand not in BRANDS and plan.brand is not None:
        bad.append(plan.brand)
        plan.brand = None
    trace.append(f"Validation dropped values not in the catalog: {', '.join(bad)}" if bad
                 else "Validation: every value is in the catalog vocabulary")
    return plan


SYNONYMS = {"no gluten": "gluten-free", "gluten free": "gluten-free", "celiac": "gluten-free",
            "plant-based": "vegan", "plant based": "vegan", "lactose free": "dairy-free",
            "dairy free": "dairy-free", "sugar free": "sugar-free", "low sodium": "low-sodium",
            "nut free": "nut-free", "high protein": "high-protein"}
STOP_WORDS = {"i", "need", "want", "show", "me", "find", "some", "any", "a", "an", "the", "for",
              "under", "below", "less", "than", "cheaper", "with", "and", "please", "do", "you",
              "have", "is", "there", "looking", "get", "that", "are", "of", "dollars", "bucks"}


def rule_based(message: str, trace: list | None = None) -> QueryPlan:
    trace = trace if trace is not None else []
    text = message.lower()
    trace.append(f'Lowercased: "{text}"')
    if re.search(r"\b(hours|open|close|location|address)\b", text) and not re.search(r"\$|\d", text):
        trace.append("Saw a store word (hours/open/location), so intent = store_info, no product search")
        return QueryPlan(intent="store_info", search_text="")
    tags = set()
    for phrase, tag in SYNONYMS.items():
        if phrase in text:
            tags.add(tag)
            text = text.replace(phrase, " ")
            trace.append(f'Synonym "{phrase}" → diet tag {tag}')
    for tag in DIET_TAGS:
        if tag in text:
            tags.add(tag)
            text = text.replace(tag, " ")
            trace.append(f'Exact diet tag "{tag}" found')
    max_price = None
    m = re.search(r"(?:under|below|less than|cheaper than|max|<)\s*\$?\s*(\d+(?:\.\d+)?)", text)
    if m:
        max_price = float(m.group(1))
        text = text.replace(m.group(0), " ")
        trace.append(f'Price pattern "{m.group(0).strip()}" → max_price {max_price:g}')
    brand = next((b for b in BRANDS if b.lower() in text), None)
    if brand:
        text = text.replace(brand.lower(), " ")
        trace.append(f'Known brand "{brand}" found')
    raw = re.findall(r"[a-z']+", text)
    dropped = [w for w in raw if w in STOP_WORDS]
    words = [w for w in raw if w not in STOP_WORDS]
    if dropped:
        trace.append(f"Dropped filler words: {', '.join(dropped)}")
    joined = " ".join(words)
    trace.append(f'Leftover words become search_text: "{joined}"' if words
                 else "No product words left, so search_text is empty (match all, filters only)")
    return QueryPlan(intent="find_product", search_text=" ".join(words), diet_tags=sorted(tags),
                     brand=brand, max_price=max_price)
